"""
Cached answers to first questions on shared books (AGENTS.md Phase 4, owner decision 13a).

Only the opening question of a chat about a shared-library or class book is cached, and
it is answered in a neutral voice (the level's style, no persona or personal profile),
so one answer fits every student of that book at that level. Follow-ups, personal books,
hints-first chats and custom prompts always get fresh answers.

Lookup: exact match on the normalised question, then the closest earlier question by
meaning (cosine >= SEMANTIC_CACHE_THRESHOLD) within the same book, level and rules.
Entries expire after ANSWER_CACHE_TTL_DAYS and are keyed by PROMPT_VERSION, so a prompt
change stops reuse of old answers.

Sources are stored against the book's root document and mapped back to the student's
own copy when served, so citations still open their book.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from config.settings import settings
from services.shared_content import Scope
from utils.logger import logger

PROMPT_VERSION = 1


def normalise(question: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (question or "").lower())).strip()


def scope_key(scope: Scope, level: str, deep: bool, outside_book: bool) -> str:
    raw = json.dumps([scope.roots, level or "general", bool(deep), bool(outside_book), PROMPT_VERSION])
    return hashlib.sha256(raw.encode()).hexdigest()


def _qhash(question: str) -> str:
    return hashlib.sha256(normalise(question).encode()).hexdigest()


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


def _to_student(scope: Scope, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for s in sources or []:
        doc = scope.doc_for_root(s.get("doc_id")) or s.get("doc_id")
        out.append({**s, "doc_id": doc})
    return out


def _to_root(scope: Scope, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{**s, "doc_id": scope.by_doc.get(s.get("doc_id"), s.get("doc_id"))} for s in sources or []]


async def _embedding(question: str) -> Optional[List[float]]:
    try:
        from services.embedding_service import embedding_service
        return await embedding_service.generate_embedding(question)   # cached: retrieval reuses it
    except Exception as e:
        logger.debug(f"[AnswerCache] no embedding: {e}")
        return None


async def lookup(scope: Scope, key: str, question: str) -> Optional[Dict[str, Any]]:
    """{"answer", "sources", "match"} for a cached answer, or None."""
    if not settings.ANSWER_CACHE_ENABLED:
        return None
    pg = _pg()
    try:
        rows = await _db(lambda: pg.fetch(
            """UPDATE answer_cache SET hits = hits + 1
               WHERE scope_key = %s AND question_hash = %s AND expires_at > now()
               RETURNING answer, sources, cost_usd""", (key, _qhash(question))))
        match = "exact"
        if not rows:
            vector = await _embedding(question)
            if vector is None:
                return None
            from services.vector_store import _vec
            lit = _vec(vector)
            near = await _db(lambda: pg.fetch(
                """SELECT id, 1 - (embedding <=> %s::vector) AS similarity FROM answer_cache
                   WHERE scope_key = %s AND expires_at > now() AND embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector LIMIT 1""", (lit, key, lit)))
            if not near or float(near[0]["similarity"] or 0) < settings.SEMANTIC_CACHE_THRESHOLD:
                return None
            rows = await _db(lambda: pg.fetch(
                "UPDATE answer_cache SET hits = hits + 1 WHERE id = %s RETURNING answer, sources, cost_usd",
                (near[0]["id"],)))
            match = "semantic"
        if not rows:
            return None
        from services.telemetry import telemetry
        telemetry.record_hit("answer", saved_usd=float(rows[0].get("cost_usd") or 0))
        logger.info(f"[AnswerCache] {match} hit")
        return {"answer": rows[0]["answer"], "sources": _to_student(scope, rows[0]["sources"]), "match": match}
    except Exception as e:
        logger.debug(f"[AnswerCache] lookup skipped: {e}")
        return None


def cacheable_answer(answer: str) -> bool:
    text = (answer or "").strip()
    return len(text) >= 20 and not text.startswith("Error:") and "\n\nError:" not in text


async def store(scope: Scope, key: str, question: str, answer: str, sources: List[Dict[str, Any]],
                cost_usd: float = 0.0) -> None:
    if not settings.ANSWER_CACHE_ENABLED or not cacheable_answer(answer):
        return
    vector = await _embedding(question)
    pg = _pg()
    try:
        from services.vector_store import _vec
        await _db(lambda: pg.fetch(
            """INSERT INTO answer_cache (scope_key, question_hash, question, embedding, answer, sources,
                                         cost_usd, expires_at)
               VALUES (%s, %s, %s, %s::vector, %s, %s::jsonb, %s, now() + make_interval(days => %s))
               ON CONFLICT (scope_key, question_hash) DO UPDATE
                 SET answer = EXCLUDED.answer, sources = EXCLUDED.sources, embedding = EXCLUDED.embedding,
                     cost_usd = EXCLUDED.cost_usd, expires_at = EXCLUDED.expires_at""",
            (key, _qhash(question), question[:2000], _vec(vector) if vector else None, answer,
             json.dumps(_to_root(scope, sources)), round(cost_usd, 6), settings.ANSWER_CACHE_TTL_DAYS)))
    except Exception as e:
        logger.debug(f"[AnswerCache] store skipped: {e}")


