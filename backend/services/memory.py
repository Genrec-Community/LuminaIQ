"""
Conversation memory (AGENTS.md Phase 5, layer 3).

Rolling chat summary: every ~10 messages a background job folds the older part of a
project's chat into one short summary (small model). The model then gets the summary
plus the recent turns, so a 100-turn chat still "remembers" turn 3 without sending it.

Long-term memory facts (user_memories): in the same job, the small model notes stable
facts about the learner (goals, exam, preferences, struggles, interests), deduplicated
against what's already stored and capped per user. Automatic facts are only for Class 11
and above (owner decision 13); Class 5-10 gets the learner model and the chat summary.
Facts unused for 6 months fade (deleted by worker housekeeping). Students can view, edit
and delete everything (api/v1/endpoints/memory.py). Teachers never see any of it.

Settings (user settings JSON): memoryAcrossBooks (default on) and autoMemory (default on).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import logger

SUMMARY_EVERY = 10      # new messages before the summary is refreshed
KEEP_RECENT = 6         # turns always sent as they are
MAX_RECENT = 16         # turns after the summary's cut-off sent at most
MAX_MEMORIES = 60       # facts kept per user (least recently used go first)
PROMPT_MEMORIES = 10    # facts put in one prompt at most
AUTO_MEMORY_LEVELS = {"higher_secondary", "ugpg", "research", "general"}
KINDS = {"goal", "preference", "struggle", "interest", "fact"}


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


# --------------------------------------------------------------------------- settings

async def settings_for(user_id: str) -> Dict[str, bool]:
    try:
        from services.user_data_service import user_data
        s = await user_data.get_settings(user_id) or {}
    except Exception:
        s = {}
    return {"across_books": s.get("memoryAcrossBooks", True) is not False,
            "auto": s.get("autoMemory", True) is not False}


def auto_memory_allowed(level: Optional[str]) -> bool:
    return (level or "general") in AUTO_MEMORY_LEVELS


# --------------------------------------------------------------------------- chat summary

async def chat_context(project_id: str) -> Tuple[str, List[Dict[str, str]]]:
    """(summary of earlier turns, recent turns oldest-first) for one project's chat."""
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        "SELECT summary, covered_until FROM chat_summaries WHERE project_id = %s", (project_id,)))
    summary = rows[0]["summary"] if rows else ""
    cutoff = rows[0]["covered_until"] if rows else None
    if cutoff:
        recent = await _db(lambda: pg.fetch(
            """SELECT role, content FROM chat_messages WHERE project_id = %s AND created_at > %s
               ORDER BY created_at DESC LIMIT %s""", (project_id, cutoff, MAX_RECENT)))
        if len(recent) < KEEP_RECENT:
            recent = await _db(lambda: pg.fetch(
                "SELECT role, content FROM chat_messages WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
                (project_id, KEEP_RECENT)))
    else:
        recent = await _db(lambda: pg.fetch(
            "SELECT role, content FROM chat_messages WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
            (project_id, MAX_RECENT)))
    return summary, [{"role": r["role"], "content": r["content"]} for r in reversed(recent)]


async def maybe_refresh(project_id: str, user_id: str, level: str) -> bool:
    """Queue a summary/memory refresh when enough new messages have piled up."""
    pg = _pg()
    try:
        rows = await _db(lambda: pg.fetch(
            """SELECT count(*) AS n FROM chat_messages m WHERE m.project_id = %s AND m.created_at >
                 COALESCE((SELECT covered_until FROM chat_summaries WHERE project_id = %s), '-infinity')""",
            (project_id, project_id)))
        if int(rows[0]["n"]) < SUMMARY_EVERY + KEEP_RECENT:
            return False
        from services.jobs import enqueue
        await enqueue("refresh_memory", {"project_id": project_id, "user_id": user_id, "level": level},
                      user_id=user_id, dedupe_key=f"refresh_memory:{project_id}")
        return True
    except Exception as e:
        logger.debug(f"[Memory] refresh not queued: {e}")
        return False


_SUMMARY_PROMPT = (
    "You keep a running summary of a tutoring chat between a student and their study companion. "
    "Update the summary with the new messages. Keep: what the student asked and is studying, what was "
    "explained (key points, formulas, examples used), what confused them and whether it was resolved, and "
    "anything they said about their goals or preferences. Drop small talk. At most 250 words, plain text, "
    "written in the third person ('The student...'). Reply with the summary only."
)

_FACTS_PROMPT = (
    "You maintain a short list of long-term facts about a student, to personalise future tutoring. "
    "From the student's messages, note only stable, useful facts: goals and exams (with dates), preferred "
    "explanation style, interests usable as examples, persistent struggles. Never store sensitive details "
    "(health, family problems, religion, contact details, addresses, passwords) or one-off questions.\n"
    "Existing facts (id: kind: text) are given. Reply with JSON only:\n"
    '{"add": [{"kind": "goal|preference|struggle|interest|fact", "content": "..."}], '
    '"update": [{"id": "...", "content": "..."}], "delete": ["id", ...]}\n'
    "Update a fact instead of adding a near-duplicate; delete facts the student contradicts. "
    "Use empty lists when nothing changes."
)


def _transcript(messages: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{m['role']}: {m['content'][:1500]}" for m in messages)


def _json_obj(text: str) -> Dict[str, Any]:
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        out = json.loads(text[start:end])
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


async def refresh(project_id: str, user_id: str, level: str) -> Dict[str, Any]:
    """Fold older turns into the summary and update memory facts (the refresh_memory job)."""
    from services.llm_service import llm_service

    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        "SELECT summary, covered_until, covered_count FROM chat_summaries WHERE project_id = %s", (project_id,)))
    prev = rows[0]["summary"] if rows else ""
    cutoff = rows[0]["covered_until"] if rows else None
    count = int(rows[0]["covered_count"]) if rows else 0
    new = await _db(lambda: pg.fetch(
        """SELECT role, content, created_at FROM chat_messages
           WHERE project_id = %s AND created_at > COALESCE(%s, '-infinity'::timestamptz)
           ORDER BY created_at""", (project_id, cutoff)))
    older = new[:-KEEP_RECENT]
    if len(older) < SUMMARY_EVERY:
        return {"summarised": 0}

    summary = await llm_service.chat_completion(
        [{"role": "system", "content": _SUMMARY_PROMPT},
         {"role": "user", "content": f"Current summary:\n{prev or '(none yet)'}\n\nNew messages:\n{_transcript(older)}"}],
        temperature=0.2, max_tokens=600, task="memory")
    summary = (summary or prev).strip()[:4000]
    await _db(lambda: pg.fetch(
        """INSERT INTO chat_summaries (project_id, user_id, summary, covered_until, covered_count, updated_at)
           VALUES (%s, %s, %s, %s, %s, now())
           ON CONFLICT (project_id) DO UPDATE SET summary = EXCLUDED.summary, covered_until = EXCLUDED.covered_until,
             covered_count = EXCLUDED.covered_count, updated_at = now()""",
        (project_id, user_id, summary, older[-1]["created_at"], count + len(older))))

    facts = {"added": 0, "updated": 0, "deleted": 0}
    prefs = await settings_for(user_id)
    student_lines = [m for m in older if m["role"] == "user"]
    if auto_memory_allowed(level) and prefs["auto"] and student_lines:
        facts = await _extract_facts(user_id, project_id, student_lines)
    return {"summarised": len(older), **facts}


async def _extract_facts(user_id: str, project_id: str, messages: List[Dict[str, Any]]) -> Dict[str, int]:
    from services.llm_service import llm_service

    existing = await list_memories(user_id)
    known = "\n".join(f"{m['id']}: {m['kind']}: {m['content']}" for m in existing) or "(none)"
    out = await llm_service.chat_completion(
        [{"role": "system", "content": _FACTS_PROMPT},
         {"role": "user", "content": f"Existing facts:\n{known}\n\nStudent's messages:\n{_transcript(messages)}"}],
        temperature=0, max_tokens=500, task="memory")
    ops = _json_obj(out or "")
    ids = {m["id"] for m in existing}
    seen = {_norm(m["content"]) for m in existing}
    added = updated = deleted = 0
    for a in (ops.get("add") or [])[:5]:
        text = str((a or {}).get("content") or "").strip()[:300]
        if text and _norm(text) not in seen:
            await add_memory(user_id, text, kind=str(a.get("kind") or "fact"), project_id=project_id, source="chat")
            seen.add(_norm(text))
            added += 1
    for u in ops.get("update") or []:
        if (u or {}).get("id") in ids and str(u.get("content") or "").strip():
            await update_memory(user_id, u["id"], str(u["content"]).strip()[:300])
            updated += 1
    for d in ops.get("delete") or []:
        if d in ids:
            await delete_memory(user_id, d)
            deleted += 1
    await _enforce_cap(user_id)
    return {"added": added, "updated": updated, "deleted": deleted}


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


# --------------------------------------------------------------------------- facts: CRUD

async def list_memories(user_id: str) -> List[Dict[str, Any]]:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        """SELECT id::text, project_id::text, kind, content, source, last_used_at, created_at, updated_at
           FROM user_memories WHERE user_id = %s ORDER BY updated_at DESC""", (user_id,)))
    return rows


async def add_memory(user_id: str, content: str, kind: str = "fact", project_id: Optional[str] = None,
                     source: str = "user") -> Dict[str, Any]:
    pg = _pg()
    kind = kind if kind in KINDS else "fact"
    rows = await _db(lambda: pg.fetch(
        """INSERT INTO user_memories (user_id, project_id, kind, content, source) VALUES (%s, %s, %s, %s, %s)
           RETURNING id::text, project_id::text, kind, content, source, last_used_at, created_at, updated_at""",
        (user_id, project_id, kind, content.strip()[:300], source)))
    if source == "user":
        await _enforce_cap(user_id)
    return rows[0]


async def update_memory(user_id: str, memory_id: str, content: str, kind: Optional[str] = None) -> Optional[Dict[str, Any]]:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        """UPDATE user_memories SET content = %s, kind = COALESCE(%s, kind), updated_at = now()
           WHERE id = %s AND user_id = %s
           RETURNING id::text, project_id::text, kind, content, source, last_used_at, created_at, updated_at""",
        (content.strip()[:300], kind if kind in KINDS else None, memory_id, user_id)))
    return rows[0] if rows else None


async def delete_memory(user_id: str, memory_id: str) -> bool:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        "DELETE FROM user_memories WHERE id = %s AND user_id = %s RETURNING id", (memory_id, user_id)))
    return bool(rows)


async def clear_all(user_id: str) -> Dict[str, int]:
    """Forget everything: memory facts and every chat summary (chats themselves stay)."""
    pg = _pg()
    facts = await _db(lambda: pg.fetch("DELETE FROM user_memories WHERE user_id = %s RETURNING id", (user_id,)))
    summaries = await _db(lambda: pg.fetch(
        "DELETE FROM chat_summaries WHERE user_id = %s RETURNING project_id", (user_id,)))
    return {"memories": len(facts), "summaries": len(summaries)}


async def _enforce_cap(user_id: str) -> None:
    pg = _pg()
    await _db(lambda: pg.fetch(
        """DELETE FROM user_memories WHERE id IN (
             SELECT id FROM user_memories WHERE user_id = %s ORDER BY last_used_at DESC, updated_at DESC OFFSET %s)""",
        (user_id, MAX_MEMORIES)))


# --------------------------------------------------------------------------- facts for a prompt

async def for_prompt(user_id: str, project_id: str, question: str, across_books: bool = True,
                     limit: int = PROMPT_MEMORIES) -> List[Dict[str, Any]]:
    """The facts most relevant to this question (word overlap, then recency), marked as used."""
    try:
        facts = await list_memories(user_id)
    except Exception as e:
        logger.debug(f"[Memory] facts unavailable: {e}")
        return []
    if not across_books:
        # Facts from other books stay there; ones the student typed in (no book) apply everywhere
        facts = [f for f in facts if not f.get("project_id") or f["project_id"] == str(project_id)]
    words = set(_norm(question).split())
    always = {"goal", "preference"}
    facts.sort(key=lambda f: (f["kind"] in always, len(words & set(_norm(f["content"]).split())),
                              str(f.get("last_used_at") or "")), reverse=True)
    chosen = facts[:limit]
    if chosen:
        pg = _pg()
        try:
            await _db(lambda: pg.fetch("UPDATE user_memories SET last_used_at = now() WHERE id = ANY(%s::uuid[])",
                                       ([f["id"] for f in chosen],)))
        except Exception:
            pass
    return chosen
