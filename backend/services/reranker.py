"""
Optional reranking of retrieved passages (Cohere/Jina/Voyage-style /rerank API).

On only when RERANK_API_KEY is set. Any failure returns None so callers keep
their own order: reranking improves answers but must never break them.
"""
import time
from typing import List, Optional

import httpx

from config.settings import settings
from utils.logger import logger


def enabled() -> bool:
    return bool(settings.RERANK_API_KEY)


async def rerank(query: str, documents: List[str], top_n: int) -> Optional[List[int]]:
    """Indexes into `documents`, best first, or None when reranking is off or fails."""
    if not enabled() or not documents:
        return None
    started = time.perf_counter()
    ok = False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(
                f"{settings.RERANK_BASE_URL.rstrip('/')}/rerank",
                headers={"Authorization": f"Bearer {settings.RERANK_API_KEY}"},
                json={"model": settings.RERANK_MODEL, "query": query, "documents": documents,
                      "top_n": min(top_n, len(documents))},
            )
        res.raise_for_status()
        body = res.json()
        results = body.get("results") or body.get("data") or []
        ok = True
        order = [int(r["index"]) for r in sorted(results, key=lambda r: -float(r.get("relevance_score", r.get("score", 0))))]
        return [i for i in order if 0 <= i < len(documents)][:top_n] or None
    except Exception as e:
        logger.warning(f"[Rerank] skipped: {e}")
        return None
    finally:
        _record(int((time.perf_counter() - started) * 1000), ok)


def _record(latency_ms: int, ok: bool) -> None:
    try:
        from services.telemetry import telemetry
        telemetry.record("rerank", settings.RERANK_MODEL, role="rerank", latency_ms=latency_ms, ok=ok)
    except Exception:
        pass
