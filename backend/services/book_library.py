"""
Shared book library: generated study assets (Visual Lab simulations, cram
cards) are reused across everyone who uploads the same book, so popular
textbooks are only paid for once.

How a "same book" is recognised
  Each document's stored text gets a bottom-k MinHash sketch: the K smallest
  64-bit hashes of its 6-word shingles. Two sketches estimate the Jaccard
  similarity of the two texts, so different PDFs / extractions of the same
  book still match, while different books don't. Candidate books are found
  through a GIN index on each sketch's smallest hashes, then compared exactly.

How a "same topic" is recognised
  Topic names are normalised (case, punctuation, plurals, filler words). A
  match needs a high word overlap AND identical distinguishing tokens
  (numbers, ordinals, roman numerals), so "Newton's first law" never matches
  "Newton's second law". Near-misses fall back to embedding similarity.

Only content derived from the book itself is shared, and only with users whose
own upload matches that book. Everything degrades silently: if anything here
fails, the caller simply generates the asset as before.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from db.client import async_db, get_supabase_client
from utils.logger import logger

SKETCH_K = 128          # sketch size (estimation error ~ 1/sqrt(K) ≈ 9%)
INDEX_KEYS = 16         # smallest hashes stored in the indexed column
SHINGLE_WORDS = 6
SAME_BOOK = 0.6         # Jaccard estimate needed to call two texts the same book
BUCKET = "shared-assets"

_STOP = {
    "a", "an", "and", "the", "of", "in", "on", "by", "to", "for", "with", "its", "their",
    "is", "are", "as", "at", "from", "or", "into", "how", "what", "why", "about",
    "introduction", "intro", "basics", "basic", "overview", "concept", "concepts",
    "understanding", "chapter", "topic", "part",
}
_ORDINALS = {
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
}


# ---------------------------------------------------------------- sketches

def _hash64(s: str) -> int:
    # 63 bits so it fits a signed Postgres bigint
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big") >> 1


def sketch_text(text: str) -> List[int]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < SHINGLE_WORDS:
        return []
    hashes = {
        _hash64(" ".join(words[i:i + SHINGLE_WORDS]))
        for i in range(len(words) - SHINGLE_WORDS + 1)
    }
    return sorted(hashes)[:SKETCH_K]


def sketch_similarity(a: List[int], b: List[int]) -> float:
    """Bottom-k estimate of the Jaccard similarity of the two texts."""
    if not a or not b:
        return 0.0
    k = min(len(a), len(b), SKETCH_K)
    union_bottom = sorted(set(a) | set(b))[:k]
    sa, sb = set(a), set(b)
    return sum(1 for h in union_bottom if h in sa and h in sb) / k


# ------------------------------------------------------------------ topics

_ORDINAL_DIGITS = {
    "1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "5th": "fifth",
    "6th": "sixth", "7th": "seventh", "8th": "eighth", "9th": "ninth", "10th": "tenth",
}


def _tokens(topic: str) -> List[str]:
    words = re.findall(r"[a-z0-9]+", topic.lower().replace("'s", ""))
    out = []
    for w in words:
        w = _ORDINAL_DIGITS.get(w, w)
        if w in _STOP:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def topic_key(topic: str) -> str:
    return " ".join(sorted(set(_tokens(topic)))) or topic.strip().lower()


def _distinguishing(tokens: List[str]) -> set:
    return {t for t in tokens if t.isdigit() or t in _ORDINALS}


def lexical_match(topic: str, candidates: List[str]) -> tuple:
    """Best candidate by word overlap → (candidate or None, score)."""
    q = _tokens(topic)
    qs, qd = set(q), _distinguishing(q)
    best, best_score = None, 0.0
    for c in candidates:
        ct = _tokens(c)
        cs = set(ct)
        if not qs or not cs or _distinguishing(ct) != qd:
            continue
        score = len(qs & cs) / len(qs | cs)
        if score > best_score:
            best, best_score = c, score
    return best, best_score


async def match_topic(topic: str, candidates: List[str]) -> Optional[str]:
    if not candidates:
        return None
    key = topic_key(topic)
    for c in candidates:
        if topic_key(c) == key:
            return c
    best, score = lexical_match(topic, candidates)
    if score >= 0.6:
        return best
    if best is None or score < 0.34:
        return None
    # Near miss ("Coulomb law" vs "Coulomb's law of electrostatic force"): ask the embedder
    try:
        from services.embedding_service import embedding_service

        shortlist = sorted(
            candidates, key=lambda c: -lexical_match(topic, [c])[1]
        )[:5]
        vectors = await embedding_service.generate_embeddings([topic] + shortlist)
        qv = vectors[0]

        def cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        scored = [(cos(qv, v), c) for v, c in zip(vectors[1:], shortlist)]
        sim, cand = max(scored)
        if sim >= 0.9 and _distinguishing(_tokens(cand)) == _distinguishing(_tokens(topic)):
            return cand
    except Exception as e:
        logger.debug(f"Embedding topic match skipped: {e}")
    return None


# ------------------------------------------------------------------- books

class BookLibrary:
    def __init__(self):
        self.client = get_supabase_client()
        self._doc_book: Dict[str, Optional[str]] = {}  # process-level cache

    async def book_for_document(self, document: Dict[str, Any]) -> Optional[str]:
        """Shared book id for a document (registering the book if it's new)."""
        doc_id = document["id"]
        if doc_id in self._doc_book:
            return self._doc_book[doc_id]
        book_id = None
        try:
            res = await async_db(lambda: self.client.table("document_books")
                                 .select("book_id").eq("document_id", doc_id).limit(1).execute())
            if res.data:
                book_id = res.data[0]["book_id"]
            else:
                book_id = await self._register(document)
        except Exception as e:
            logger.debug(f"Book lookup skipped for {doc_id}: {e}")
            return None
        self._doc_book[doc_id] = book_id
        return book_id

    async def _register(self, document: Dict[str, Any]) -> Optional[str]:
        import asyncio
        from services.document_service import document_service

        text = await document_service.load_stored_text(document)
        if not text or len(text) < 2000:
            return None
        sketch = await asyncio.to_thread(sketch_text, text)
        if len(sketch) < SKETCH_K // 2:
            return None
        keys = sketch[:INDEX_KEYS]

        res = await async_db(lambda: self.client.table("shared_books")
                             .select("id, sketch").overlaps("sketch_keys", keys).limit(50).execute())
        best_id, best_sim = None, 0.0
        for row in res.data or []:
            sim = sketch_similarity(sketch, row["sketch"] or [])
            if sim > best_sim:
                best_id, best_sim = row["id"], sim

        if best_id and best_sim >= SAME_BOOK:
            book_id = best_id
            logger.info(f"[BookLibrary] {document.get('filename')} matches shared book {book_id} ({best_sim:.2f})")
        else:
            ins = await async_db(lambda: self.client.table("shared_books").insert({
                "sketch": sketch, "sketch_keys": keys,
                "title": (document.get("filename") or "")[:200],
            }).execute())
            book_id = ins.data[0]["id"]
        await async_db(lambda: self.client.table("document_books").upsert(
            {"document_id": document["id"], "book_id": book_id}, on_conflict="document_id"
        ).execute())
        return book_id

    async def books_for_topic(self, project_id: str, topic: str,
                              selected_documents: List[str]) -> List[str]:
        """Shared book ids of the project documents this topic comes from."""
        from services.knowledge_graph_service import knowledge_graph

        try:
            docs = await knowledge_graph.load_project_documents(project_id)
        except Exception:
            return []
        if selected_documents:
            wanted = set(selected_documents)
            docs = [d for d in docs if d["id"] in wanted]
        key = topic_key(topic)
        owning = [d for d in docs if any(topic_key(t) == key for t in (d.get("topics") or []))]
        if not owning and len(docs) == 1:
            owning = docs  # free-typed topic, but there's only one book in play
        books = []
        for d in owning[:3]:
            b = await self.book_for_document({**d, "project_id": project_id})
            if b and b not in books:
                books.append(b)
        return books

    # -------------------------------------------------------------- assets

    async def get_asset(self, book_ids: List[str], topic: str, kind: str) -> Optional[Dict[str, Any]]:
        for book_id in book_ids:
            try:
                res = await async_db(lambda: self.client.table("shared_topic_assets")
                                     .select("topic, content, storage_path")
                                     .eq("book_id", book_id).eq("kind", kind).execute())
                rows = res.data or []
                if not rows:
                    continue
                match = await match_topic(topic, [r["topic"] for r in rows])
                if not match:
                    continue
                row = next(r for r in rows if r["topic"] == match)
                if row.get("storage_path"):
                    data = await async_db(lambda: self.client.storage.from_(BUCKET).download(row["storage_path"]))
                    content = {"html": data.decode("utf-8")}
                else:
                    content = row["content"]
                logger.info(f"[BookLibrary] Reused {kind} '{match}' for '{topic}' (book {book_id})")
                return content
            except Exception as e:
                logger.debug(f"Shared asset read skipped: {e}")
        return None

    async def put_asset(self, book_ids: List[str], topic: str, kind: str, content: Dict[str, Any]) -> None:
        for book_id in book_ids:
            try:
                key = topic_key(topic)
                storage_path = None
                stored = content
                if kind.startswith("visual") and content.get("html"):
                    storage_path = f"{book_id}/{kind}/{hashlib.sha1(key.encode()).hexdigest()}.html"
                    body = content["html"].encode("utf-8")
                    await async_db(lambda: self.client.storage.from_(BUCKET).upload(
                        file=body, path=storage_path,
                        file_options={"content-type": "text/html; charset=utf-8", "upsert": "true"},
                    ))
                    stored = {}
                await async_db(lambda: self.client.table("shared_topic_assets").upsert({
                    "book_id": book_id, "topic": topic, "topic_key": key, "kind": kind,
                    "content": stored, "storage_path": storage_path,
                }, on_conflict="book_id,topic_key,kind").execute())
            except Exception as e:
                logger.debug(f"Shared asset write skipped: {e}")


book_library = BookLibrary()
