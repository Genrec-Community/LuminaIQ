"""
Study content for shared books, paid for once (AGENTS.md Phase 4, owner decision 13a).

A *shared book* is a bookstore import or a class-book copy, or the original they were
copied from. Each resolves to a root document (shared_root_documents() in SQL). Personal
uploads have no root and always get freshly generated content.

    scope = await shared_content.scope_for(project_id, selected_documents)   # None = personal
    items, generated = await shared_content.draw(user_id, scope, "quiz", topic, level,
                                                 variant="medium", n=10, make=generate)
    content = await shared_content.asset(scope, "notes", [note_type, topic, level], make=generate_one)

draw(): quiz questions and flashcards come from a pool per (book, tool, topic, level,
variant, prompt version). A student gets items they haven't seen, in random order, with
quiz options shuffled; the pool grows only when they run out. asset(): one generated
result per key (notes, mindmaps), shared by every student of that book.

Everything degrades to plain generation if the database misbehaves.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from config.settings import settings
from utils.logger import logger

# Bump when a generator's prompt changes in a way that should stop reuse of old items
PROMPT_VERSIONS = {"quiz": 2, "flashcards": 2, "notes": 1, "mindmap": 1}
MIN_BATCH = 5          # when a pool runs dry, generate at least this many new items


@dataclass
class Scope:
    roots: List[str]                                   # sorted root document ids
    by_doc: Dict[str, str] = field(default_factory=dict)   # student's document id -> root id

    def doc_for_root(self, root: str) -> Optional[str]:
        return next((d for d, r in self.by_doc.items() if r == root), None)


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


def _hash(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _topic_key(topic: Optional[str]) -> str:
    from services.book_library import topic_key
    return topic_key(topic or "") or (topic or "").strip().lower()


# ------------------------------------------------------------------- scope

async def scope_for(project_id: str, document_ids: Optional[List[str]] = None) -> Optional[Scope]:
    """The shared roots behind the documents in play, or None if any of them is a personal upload."""
    if not settings.SHARED_CONTENT_ENABLED:
        return None
    try:
        pg = _pg()
        if document_ids:
            rows = await _db(lambda: pg.fetch(
                "SELECT id FROM documents WHERE project_id = %s AND id = ANY(%s::uuid[])",
                (project_id, list(document_ids))))
        else:
            rows = await _db(lambda: pg.fetch(
                "SELECT id FROM documents WHERE project_id = %s AND upload_status = 'completed'", (project_id,)))
        docs = [str(r["id"]) for r in rows]
        if not docs:
            return None
        roots = await _db(lambda: pg.fetch(
            "SELECT document_id, root_id FROM shared_root_documents(%s::uuid[])", (docs,)))
        by_doc = {str(r["document_id"]): str(r["root_id"]) for r in roots if r.get("root_id")}
        if len(by_doc) != len(docs):
            return None
        return Scope(roots=sorted(set(by_doc.values())), by_doc=by_doc)
    except Exception as e:
        logger.debug(f"[Shared] scope lookup skipped: {e}")
        return None


# ------------------------------------------------------------------- items

def item_text(tool: str, item: Dict[str, Any]) -> str:
    text = item.get("question") if tool == "quiz" else item.get("front")
    return re.sub(r"\W+", " ", str(text or item)).strip().lower()


def shuffle_options(question: Dict[str, Any], rng: Optional[random.Random] = None) -> Dict[str, Any]:
    """The same question with its options in a new order and letters reassigned."""
    rng = rng or random
    options = list(question.get("options") or [])
    if len(options) < 2:
        return dict(question)
    correct_letter = str(question.get("correct_answer", "")).strip().upper()[:1]
    correct_text = next((o.get("text") for o in options if str(o.get("option", "")).upper() == correct_letter), None)
    rng.shuffle(options)
    letters = "ABCDEFGH"
    new_options = [{"option": letters[i], "text": o.get("text")} for i, o in enumerate(options)]
    new_correct = next((o["option"] for o in new_options if o["text"] == correct_text), correct_letter)
    return {**question, "options": new_options, "correct_answer": new_correct}


def pool_key(tool: str, roots: List[str], topic: Optional[str], level: str, variant: str = "") -> str:
    return _hash("pool", tool, sorted(roots), _topic_key(topic), level or "", variant or "",
                 PROMPT_VERSIONS.get(tool, 1))


async def _unseen(user_id: Optional[str], key: str, n: int) -> List[Tuple[int, Dict[str, Any], float]]:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        """SELECT p.id, p.item, p.cost_usd FROM content_pool p
           WHERE p.pool_key = %s
             AND NOT EXISTS (SELECT 1 FROM content_pool_seen s WHERE s.user_id = %s AND s.item_id = p.id)
           ORDER BY random() LIMIT %s""", (key, user_id, n)))
    return [(int(r["id"]), r["item"], float(r.get("cost_usd") or 0)) for r in rows]


async def _mark_seen(user_id: Optional[str], ids: List[int]) -> None:
    if not user_id or not ids:
        return
    pg = _pg()
    await _db(lambda: pg.fetch(
        """INSERT INTO content_pool_seen (user_id, item_id) SELECT %s, unnest(%s::bigint[])
           ON CONFLICT DO NOTHING""", (user_id, ids)))


async def _add(key: str, tool: str, roots: List[str], topic: Optional[str], level: str,
               items: List[Dict[str, Any]], cost_each: float) -> List[Tuple[int, Dict[str, Any]]]:
    pg = _pg()
    out = []
    for item in items:
        rows = await _db(lambda item=item: pg.fetch(
            """INSERT INTO content_pool (pool_key, tool, root_ids, topic, level, item, item_hash, cost_usd)
               VALUES (%s, %s, %s::uuid[], %s, %s, %s::jsonb, %s, %s)
               ON CONFLICT (pool_key, item_hash) DO NOTHING RETURNING id""",
            (key, tool, roots, topic or "", level or "", json.dumps(item), _hash(item_text(tool, item)),
             round(cost_each, 6))))
        if rows:
            out.append((int(rows[0]["id"]), item))
    return out


def _present(tool: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [shuffle_options(i) for i in items] if tool == "quiz" else list(items)


async def draw(user_id: Optional[str], scope: Optional[Scope], tool: str, topic: Optional[str], level: str,
               n: int, make: Callable[[int], Awaitable[List[Dict[str, Any]]]],
               variant: str = "") -> Tuple[List[Dict[str, Any]], int]:
    """
    n items for this student: from the pool when the book is shared (generating only
    what's missing), otherwise freshly made. Returns (items, how many were generated).
    """
    from services.telemetry import meter, telemetry

    if scope is None:
        items = await make(n)
        return items, len(items)

    key = pool_key(tool, scope.roots, topic, level, variant)
    try:
        have = await _unseen(user_id, key, n)
    except Exception as e:
        logger.debug(f"[Shared] pool read failed, generating: {e}")
        items = await make(n)
        return items, len(items)

    picked = [(i, item) for i, item, _ in have]
    generated = 0
    if len(have) < n:
        need = n - len(have)
        with meter() as m:
            fresh = await make(max(need, MIN_BATCH))
        generated = len(fresh)
        try:
            added = await _add(key, tool, scope.roots, topic, level, fresh, m.cost / max(1, len(fresh)))
        except Exception as e:
            logger.debug(f"[Shared] pool write failed: {e}")
            added = []
        seen_texts = {item_text(tool, it) for _, it in picked}
        source = added if added else [(None, it) for it in fresh]
        for i, it in source:
            if len(picked) >= n:
                break
            if item_text(tool, it) not in seen_texts:
                seen_texts.add(item_text(tool, it))
                picked.append((i, it))
    else:
        telemetry.record_hit("pool", saved_usd=sum(c for _, _, c in have))
        logger.info(f"[Shared] {tool} for '{topic}': {n} items from the pool, nothing generated")

    try:
        await _mark_seen(user_id, [i for i, _ in picked if i is not None])
    except Exception as e:
        logger.debug(f"[Shared] seen-marking failed: {e}")
    items = [it for _, it in picked]
    random.shuffle(items)
    return _present(tool, items), generated


# ------------------------------------------------------------------- one-per-key assets

async def asset(scope: Optional[Scope], tool: str, key_parts: List[Any],
                make: Callable[[], Awaitable[Any]]) -> Tuple[Any, bool]:
    """(content, came from the shared cache). Personal books always generate."""
    from services.telemetry import meter, telemetry

    if scope is None:
        return await make(), False
    parts = [_topic_key(p) if isinstance(p, str) else p for p in key_parts]
    key = _hash("asset", tool, scope.roots, parts, PROMPT_VERSIONS.get(tool, 1))
    pg = _pg()
    try:
        rows = await _db(lambda: pg.fetch(
            "UPDATE shared_content SET hits = hits + 1 WHERE key = %s RETURNING content, cost_usd", (key,)))
        if rows:
            telemetry.record_hit("asset", saved_usd=float(rows[0].get("cost_usd") or 0))
            logger.info(f"[Shared] {tool} reused from the shared cache")
            return rows[0]["content"]["value"], True
    except Exception as e:
        logger.debug(f"[Shared] asset read failed: {e}")
    with meter() as m:
        content = await make()
    # A fallback result (the model's output couldn't be used) is never shared
    if content and not (isinstance(content, dict) and content.get("_fallback")):
        try:
            await _db(lambda: pg.fetch(
                """INSERT INTO shared_content (key, tool, root_ids, content, cost_usd)
                   VALUES (%s, %s, %s::uuid[], %s::jsonb, %s) ON CONFLICT (key) DO NOTHING""",
                (key, tool, scope.roots, json.dumps({"value": content}), round(m.cost, 6))))
        except Exception as e:
            logger.debug(f"[Shared] asset write failed: {e}")
    return content, False
