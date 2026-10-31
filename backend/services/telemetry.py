"""
Every AI call, measured (AGENTS.md Phase 4).

    telemetry.record("llm", model, role="small", input_tokens=..., output_tokens=..., latency_ms=...)
    telemetry.record_hit("answer", saved_usd=0.004)       # a cache hit: no call made

Rows go to ai_calls (user, feature, model, tokens, estimated cost, latency, cache
hit) for the admin cost dashboard and the per-plan monthly token caps. Writes are
buffered and flushed in the background, so a call never waits on the database,
and a failing write never breaks a student's request.

Costs are estimates from the *_PRICE_* settings (USD per 1M tokens). When the
Langfuse keys are set, the same calls are also sent to Langfuse's ingestion API.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import contextvars
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.settings import settings
from utils.logger import logger

FLUSH_AFTER_SECONDS = 1.0
FLUSH_AT_ROWS = 50
MAX_BUFFER = 5000          # if the database is down, keep at most this many rows


def _prices(role: str) -> tuple:
    """(input, output, cached input) USD per 1M tokens for a model role."""
    if role == "big":
        p_in, p_out, p_cached = (settings.BIG_LLM_PRICE_INPUT, settings.BIG_LLM_PRICE_OUTPUT,
                                 settings.BIG_LLM_PRICE_CACHED_INPUT)
    elif role == "embedding":
        p_in, p_out, p_cached = settings.EMBEDDING_PRICE_INPUT, 0.0, -1.0
    else:
        p_in, p_out, p_cached = (settings.SMALL_LLM_PRICE_INPUT, settings.SMALL_LLM_PRICE_OUTPUT,
                                 settings.SMALL_LLM_PRICE_CACHED_INPUT)
    return p_in, p_out, (p_in if p_cached is None or p_cached < 0 else p_cached)


def estimate_cost(role: str, input_tokens: int = 0, output_tokens: int = 0, cached_tokens: int = 0) -> float:
    if role == "rerank":
        return float(settings.RERANK_PRICE_PER_CALL or 0.0)
    p_in, p_out, p_cached = _prices(role)
    cached = min(max(cached_tokens, 0), max(input_tokens, 0))
    return ((input_tokens - cached) * p_in + cached * p_cached + output_tokens * p_out) / 1_000_000


# Cost meters open in this task: record() adds each call's cost to them, so a caller
# can learn what one piece of work cost (e.g. a quiz batch, to know what reuse saves)
_meters: contextvars.ContextVar[tuple] = contextvars.ContextVar("ai_cost_meters", default=())


class Meter:
    def __init__(self):
        self.cost = 0.0
        self.calls = 0


@contextlib.contextmanager
def meter():
    """with meter() as m: await work(); m.cost  (USD of the AI calls made inside)"""
    m = Meter()
    token = _meters.set(_meters.get() + (m,))
    try:
        yield m
    finally:
        _meters.reset(token)


def _context() -> tuple:
    try:
        from services.usage_service import current_feature, current_user_id
        return current_user_id.get(), current_feature.get()
    except Exception:
        return None, "other"


class Telemetry:
    def __init__(self):
        self._buffer: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None
        self._task_loop = None

    # ------------------------------------------------------------------ recording

    def record(self, kind: str, model: str = "", role: str = "", input_tokens: int = 0, output_tokens: int = 0,
               cached_tokens: int = 0, latency_ms: int = 0, ok: bool = True, cache_hit: bool = False,
               saved_usd: float = 0.0, feature: Optional[str] = None, user_id: Optional[str] = None) -> float:
        """Queue one row; returns the estimated cost in USD."""
        cost = 0.0 if cache_hit else estimate_cost(role, input_tokens, output_tokens, cached_tokens)
        if not cache_hit:
            for m in _meters.get():
                m.cost += cost
                m.calls += 1
        ctx_user, ctx_feature = _context()
        row = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id or ctx_user, "feature": (feature or ctx_feature or "other")[:40],
            "kind": kind, "model": (model or "")[:120], "role": role,
            "input_tokens": int(input_tokens or 0), "output_tokens": int(output_tokens or 0),
            "cached_tokens": int(cached_tokens or 0), "cost_usd": round(cost, 6),
            "saved_usd": round(float(saved_usd or 0.0), 6), "latency_ms": int(latency_ms or 0),
            "cache_hit": bool(cache_hit), "ok": bool(ok),
        }
        if len(self._buffer) < MAX_BUFFER:
            self._buffer.append(row)
        self._schedule()
        return cost

    def record_hit(self, role: str, saved_usd: float = 0.0, feature: Optional[str] = None, latency_ms: int = 0) -> None:
        """A cache hit (pool, shared asset or answer): no model was called."""
        self.record("cache", model="cache", role=role, cache_hit=True, saved_usd=saved_usd,
                    feature=feature, latency_ms=latency_ms)

    # ------------------------------------------------------------------ flushing

    def _schedule(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return      # no event loop (a script): flush() later writes the rows
        if self._task and not self._task.done() and self._task_loop is loop:
            if len(self._buffer) < FLUSH_AT_ROWS:
                return
        self._task_loop = loop
        delay = 0 if len(self._buffer) >= FLUSH_AT_ROWS else FLUSH_AFTER_SECONDS
        self._task = loop.create_task(self._flush_later(delay))

    async def _flush_later(self, delay: float) -> None:
        if delay:
            await asyncio.sleep(delay)
        await self.flush()

    async def flush(self) -> int:
        rows, self._buffer = self._buffer, []
        if not rows:
            return 0
        try:
            from db.client import async_db, get_supabase_client
            client = get_supabase_client()
            await async_db(lambda: client.table("ai_calls").insert(rows).execute())
        except Exception as e:
            logger.debug(f"[Telemetry] {len(rows)} AI-call rows not written: {e}")
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            await self._send_langfuse(rows)
        return len(rows)

    async def _send_langfuse(self, rows: List[Dict[str, Any]]) -> None:
        """Calls as Langfuse generations, over its public ingestion API (no SDK needed)."""
        try:
            import httpx
            auth = base64.b64encode(f"{settings.LANGFUSE_PUBLIC_KEY}:{settings.LANGFUSE_SECRET_KEY}".encode()).decode()
            batch = [{
                "id": str(uuid.uuid4()), "type": "generation-create", "timestamp": r["created_at"],
                "body": {
                    "id": str(uuid.uuid4()), "name": f"{r['feature']}:{r['kind']}", "startTime": r["created_at"],
                    "model": r["model"], "userId": r["user_id"],
                    "usage": {"input": r["input_tokens"], "output": r["output_tokens"], "unit": "TOKENS",
                              "totalCost": float(r["cost_usd"])},
                    "metadata": {"role": r["role"], "latency_ms": r["latency_ms"], "cache_hit": r["cache_hit"],
                                 "cached_tokens": r["cached_tokens"]},
                    "level": "DEFAULT" if r["ok"] else "ERROR",
                },
            } for r in rows]
            async with httpx.AsyncClient(timeout=5) as http:
                await http.post(settings.LANGFUSE_HOST.rstrip("/") + "/api/public/ingestion",
                                json={"batch": batch}, headers={"Authorization": f"Basic {auth}"})
        except Exception as e:
            logger.debug(f"[Telemetry] Langfuse send failed: {e}")


class Timer:
    """with Timer() as t: ...; t.ms"""

    def __enter__(self):
        self._start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *exc):
        self.ms = int((time.perf_counter() - self._start) * 1000)
        return False


telemetry = Telemetry()
