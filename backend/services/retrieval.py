"""
Book passage retrieval shared by the study tools: vector search first, and when
that fails (embedding provider down, bad key) or finds nothing (document not
indexed yet), keyword search over the documents' stored text. So quizzes,
notes, flashcards and mindmaps keep working while the index is missing.
"""
import asyncio
from typing import Any, Dict, List, Optional

from utils.logger import logger


async def _vector_hits(project_id: str, queries: List[str], per_query: int,
                       document_ids: Optional[List[str]]) -> List[Dict[str, Any]]:
    from services.embedding_service import embedding_service
    from services.qdrant_service import qdrant_service

    filter_conds = {"document_ids": document_ids} if document_ids else None

    async def one(q: str):
        emb = await embedding_service.generate_embedding(q)
        return await qdrant_service.search(
            collection_name=f"project_{project_id}",
            query_vector=emb,
            limit=per_query,
            filter_conditions=filter_conds,
        )

    hits, seen = [], set()
    for results in await asyncio.gather(*[one(q) for q in queries]):
        for hit in results:
            if hit.get("text") and hit["text"] not in seen:
                seen.add(hit["text"])
                hits.append(hit)
    return hits


async def search_passages(
    project_id: str,
    queries: List[str],
    per_query: int = 5,
    document_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Passages for the queries, as dicts with "text" and "document_id" (vector
    hits also carry score/chunk_id). The first query is the main one; it drives
    the keyword fallback.
    """
    queries = [q for q in queries if q and q.strip()]
    if not queries:
        return []
    try:
        hits = await _vector_hits(project_id, queries, per_query, document_ids)
        if hits:
            return hits
    except Exception as e:
        logger.warning(f"Vector search failed for '{queries[0][:60]}', using stored text: {e}")

    from services.document_service import document_service
    from services.graph_analytics_service import graph_analytics

    try:
        # Re-embed documents that have no vectors (rate-limited per document)
        await document_service.ensure_project_indexed(project_id)
    except Exception as e:
        logger.debug(f"Index check failed for project {project_id}: {e}")

    passages, sources = await graph_analytics.keyword_context_from_stored_text(
        project_id,
        queries[0],
        max_passages=max(per_query * len(queries), 4),
        document_ids=document_ids or None,
        per_passage_sources=True,
        overview_if_empty=True,
    )
    return [
        {"text": p, "document_id": s.get("doc_id"), "score": 0.0, "chunk_id": None}
        for p, s in zip(passages, sources)
    ]


async def passages_text(project_id: str, queries: List[str], per_query: int = 5,
                        document_ids: Optional[List[str]] = None, limit: Optional[int] = None) -> str:
    """search_passages joined into one context string."""
    hits = await search_passages(project_id, queries, per_query, document_ids)
    if limit:
        hits = hits[:limit]
    return "\n\n".join(h["text"] for h in hits)
