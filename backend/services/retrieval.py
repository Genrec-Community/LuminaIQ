"""
Finding the right passages in a student's book: one pipeline for chat and every
study tool (quizzes, notes, flashcards, lessons).

    1. Rewrite: a follow-up ("explain that again") becomes a standalone question
       using the recent chat (small model). First questions are used as they are.
    2. Hybrid search: meaning (pgvector) and words (Postgres full-text), merged
       with Reciprocal Rank Fusion, so exact terms and paraphrases both count.
    3. Rerank (optional, RERANK_API_KEY): a cross-encoder reorders the top ~30.
    4. Merge: neighbouring chunks of the same document become one passage, and
       text repeated by chunk overlap appears once.
    5. Grounding: if nothing matches well, the answer may go beyond the book
       (with its "Not from your book" label) instead of citing weak passages.
Deep mode first splits a complex question into 2-4 sub-questions.
When a book has no passages yet (still processing), the documents' stored text
is searched by keyword instead.
"""

import asyncio
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from config.settings import settings
from services import reranker, vector_store
from services.embedding_service import embedding_service
from services.llm_service import llm_service
from utils.logger import logger

RRF_K = 60            # standard Reciprocal Rank Fusion constant
CANDIDATES = 30       # per search, before fusion and rerank
MAX_MERGE = 3         # chunks joined into one passage at most


@dataclass
class Passage:
    text: str
    document_id: Optional[str]
    page: Optional[int]
    heading: str = ""
    score: float = 0.0               # fused/reranked rank score (higher is better)
    similarity: float = 0.0          # best cosine similarity among its chunks (0 if found by words only)
    chunk_ids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    query: str
    passages: List[Passage]
    grounded: bool
    best_similarity: float
    sub_queries: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- query understanding

_REWRITE_PROMPT = (
    "Rewrite the student's latest message as one standalone search query for their textbook, "
    "using the conversation to resolve words like 'it', 'that' or 'the second one'. Keep the "
    "student's terms; add the topic names they refer to. Reply with the query only, no quotes."
)

_DECOMPOSE_PROMPT = (
    "Break the student's question into 2 to 4 short, standalone sub-questions that together answer "
    "it, one per line, numbered. If it is already simple, reply with it as the only line."
)


async def rewrite_query(question: str, history: Optional[List[Dict[str, str]]]) -> str:
    turns = [m for m in (history or []) if m.get("role") in ("user", "assistant") and m.get("content")]
    if not turns:
        return question
    convo = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in turns[-6:])
    try:
        out = await llm_service.chat_completion(
            [{"role": "system", "content": _REWRITE_PROMPT},
             {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest message: {question}"}],
            temperature=0, max_tokens=200, task="rewrite")
        out = (out or "").strip().strip('"').splitlines()[0].strip() if out and out.strip() else ""
        return out if 3 <= len(out) <= 400 else question
    except Exception as e:
        logger.warning(f"[Retrieval] rewrite skipped: {e}")
        return question


async def decompose(question: str) -> List[str]:
    try:
        out = await llm_service.chat_completion(
            [{"role": "system", "content": _DECOMPOSE_PROMPT}, {"role": "user", "content": question}],
            temperature=0, max_tokens=300, task="rewrite")
    except Exception as e:
        logger.warning(f"[Retrieval] decomposition skipped: {e}")
        return []
    subs = [re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", line).strip() for line in (out or "").splitlines()]
    return [s for s in subs if len(s) > 3][:4]


# --------------------------------------------------------------------------- search

async def _project_has_chunks(project_id: str) -> int:
    from db.client import async_db, get_supabase_client
    pg = get_supabase_client().pg
    rows = await async_db(lambda: pg.fetch("SELECT 1 FROM chunks WHERE project_id = %s LIMIT 1", (project_id,)))
    return len(rows)


def _rrf(ranked_lists: List[List[vector_store.Hit]]) -> List[tuple]:
    """[(hit, fused score, best similarity)] by Reciprocal Rank Fusion."""
    fused: Dict[int, list] = {}
    for hits in ranked_lists:
        for rank, h in enumerate(hits):
            entry = fused.setdefault(h.chunk_id, [h, 0.0, 0.0])
            entry[1] += 1.0 / (RRF_K + rank + 1)
    return sorted(((h, s, sim) for h, s, sim in fused.values()), key=lambda e: -e[1])


async def _search_one(project_id: str, query: str, document_ids) -> List[tuple]:
    """[("dense", hits), ("keyword", hits)] for one query; a failing search is skipped."""
    lists: List[tuple] = []
    try:
        vector = await embedding_service.generate_embedding(query)
        lists.append(("dense", await vector_store.search_dense(project_id, vector, CANDIDATES, document_ids)))
    except Exception as e:
        logger.warning(f"[Retrieval] meaning search skipped ({e}); using keyword search")
    try:
        lists.append(("keyword", await vector_store.search_keyword(project_id, query, CANDIDATES, document_ids)))
    except Exception as e:
        logger.warning(f"[Retrieval] keyword search failed: {e}")
    return lists


async def _hybrid(project_id: str, queries: List[str], document_ids) -> List[tuple]:
    """[(hit, fused score, best cosine similarity)] over every query and both search types."""
    lists: List[List[vector_store.Hit]] = []
    dense_sim: Dict[int, float] = {}
    for result in await asyncio.gather(*[_search_one(project_id, q, document_ids) for q in queries]):
        for kind, hits in result:
            lists.append(hits)
            if kind == "dense":
                for h in hits:
                    dense_sim[h.chunk_id] = max(dense_sim.get(h.chunk_id, 0.0), h.score)
    return [(h, s, dense_sim.get(h.chunk_id, 0.0)) for h, s, _ in _rrf(lists)]


def _join_without_overlap(a: str, b: str) -> str:
    """Join two consecutive chunks, dropping the text b repeats from the end of a."""
    a, b = a.strip(), b.strip()
    for size in range(min(len(a), len(b), 800), 9, -1):
        if a.endswith(b[:size]):
            return a + b[size:]
    return f"{a}\n\n{b}"


async def _merge(entries: List[tuple]) -> List[Passage]:
    """Merge chunks that sit next to each other in the same document into one passage."""
    passages: List[Passage] = []
    used = set()
    by_doc: Dict[str, Dict[int, tuple]] = {}
    for e in entries:
        by_doc.setdefault(e[0].document_id, {})[e[0].chunk_index] = e
    for h, score, sim in entries:
        if h.chunk_id in used:
            continue
        run_ = [h]
        used.add(h.chunk_id)
        doc = by_doc[h.document_id]
        # Only neighbours from the same section, a few at a time: merging across
        # chapters would mix topics and give the passage the wrong page
        same = lambda e: e[0].chunk_id not in used and e[0].heading == h.heading and len(run_) < MAX_MERGE
        nxt = h.chunk_index + 1
        while nxt in doc and same(doc[nxt]):
            run_.append(doc[nxt][0])
            used.add(doc[nxt][0].chunk_id)
            sim = max(sim, doc[nxt][2])
            nxt += 1
        prev = h.chunk_index - 1
        while prev in doc and same(doc[prev]):
            run_.insert(0, doc[prev][0])
            used.add(doc[prev][0].chunk_id)
            sim = max(sim, doc[prev][2])
            prev -= 1
        text = run_[0].content
        for c in run_[1:]:
            text = _join_without_overlap(text, c.content)
        passages.append(Passage(text=text, document_id=h.document_id, page=run_[0].page,
                                heading=run_[0].heading, score=score, similarity=sim,
                                chunk_ids=[c.chunk_id for c in run_]))
    # identical text (the same book uploaded twice in one project) appears once
    seen, unique = set(), []
    for p in passages:
        key = p.text.strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


async def retrieve(project_id: str, question: str, history: Optional[List[Dict[str, str]]] = None,
                   document_ids: Optional[List[str]] = None, top_n: int = 6, deep: bool = False) -> RetrievalResult:
    query = await rewrite_query(question, history)
    sub_queries: List[str] = []
    queries = [query]
    if deep:
        sub_queries = await decompose(query)
        queries += [q for q in sub_queries if q.lower() != query.lower()]

    fused = await _hybrid(project_id, queries, document_ids)
    candidates = fused[:CANDIDATES]
    if candidates:
        order = await reranker.rerank(query, [h.content for h, _, _ in candidates], top_n * 2)
        if order:
            candidates = [candidates[i] for i in order]
    passages = (await _merge(candidates[: top_n * 2]))[:top_n]

    best = max((p.similarity for p in passages), default=0.0)
    keyword_only = passages and best == 0.0
    grounded = bool(passages) and (best >= settings.RAG_MIN_SIMILARITY or keyword_only)
    if not grounded:
        # The book doesn't really cover it: keep only passages that are at least half-relevant,
        # so the student isn't shown citations that have nothing to do with the question
        passages = [p for p in passages if p.similarity >= settings.RAG_MIN_SIMILARITY / 2]
    return RetrievalResult(query=query, passages=passages, grounded=grounded,
                           best_similarity=best, sub_queries=sub_queries)


# --------------------------------------------------------------------------- study tools

async def search_passages(project_id: str, queries: List[str], per_query: int = 5,
                          document_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Passages for several topic queries (quizzes, notes, flashcards), as dicts with
    text, document_id, page, heading, score and chunk_id. Falls back to keyword
    search over stored text while a book has no passages yet.
    """
    queries = [q for q in queries if q and q.strip()]
    if not queries:
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    try:
        if await _project_has_chunks(project_id):
            for q in queries:
                fused = await _hybrid(project_id, [q], document_ids)
                for p in (await _merge(fused[: per_query * 2]))[:per_query]:
                    if p.text not in seen:
                        seen.add(p.text)
                        out.append({"text": p.text, "document_id": p.document_id, "page": p.page,
                                    "heading": p.heading, "score": p.score,
                                    "chunk_id": p.chunk_ids[0] if p.chunk_ids else None})
            if out:
                return out
    except Exception as e:
        logger.warning(f"[Retrieval] passage search failed for '{queries[0][:60]}': {e}")
    return await _stored_text_passages(project_id, queries[0], max(per_query * len(queries), 4), document_ids)


async def _stored_text_passages(project_id: str, query: str, limit: int, document_ids) -> List[Dict[str, Any]]:
    from services.document_service import document_service
    from services.graph_analytics_service import graph_analytics
    try:
        await document_service.ensure_project_indexed(project_id)   # rebuild missing passages
    except Exception as e:
        logger.debug(f"Index check failed for project {project_id}: {e}")
    passages, sources = await graph_analytics.keyword_context_from_stored_text(
        project_id, query, max_passages=limit, document_ids=document_ids or None,
        per_passage_sources=True, overview_if_empty=True)
    return [{"text": p, "document_id": s.get("doc_id"), "page": None, "heading": "", "score": 0.0, "chunk_id": None}
            for p, s in zip(passages, sources)]


async def passages_text(project_id: str, queries: List[str], per_query: int = 5,
                        document_ids: Optional[List[str]] = None, limit: Optional[int] = None) -> str:
    """search_passages joined into one context string."""
    hits = await search_passages(project_id, queries, per_query, document_ids)
    if limit:
        hits = hits[:limit]
    return "\n\n".join(h["text"] for h in hits)
