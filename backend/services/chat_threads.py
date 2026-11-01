"""
Several chats per book, like ChatGPT's "New chat".

A message without a thread goes to the book's most recent chat (or a new one), so older
clients (the Android shell, the tutor panel) keep working. A new chat is titled from
its first question, without a model call.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

NEW_TITLE = "New chat"
TITLE_CHARS = 60


def _pg():
    from db.client import get_supabase_client
    return get_supabase_client().pg


async def _db(fn):
    from db.client import async_db
    return await async_db(fn)


def title_from(message: str) -> str:
    text = re.sub(r"^\[[^\]]*\]\s*", "", (message or "").strip())   # drop "[Tutor Mode: ...]" style prefixes
    text = re.sub(r"\s+", " ", text)
    if len(text) <= TITLE_CHARS:
        return text or NEW_TITLE
    cut = text[:TITLE_CHARS].rsplit(" ", 1)[0]
    return (cut or text[:TITLE_CHARS]).rstrip(" ,.;:") + "…"


_COLUMNS = "id::text, project_id::text, title, created_at, updated_at"


async def list_threads(project_id: str, user_id: str) -> List[Dict[str, Any]]:
    pg = _pg()
    return await _db(lambda: pg.fetch(
        f"""SELECT {_COLUMNS},
                   (SELECT count(*) FROM chat_messages m WHERE m.thread_id = t.id) AS message_count
            FROM chat_threads t WHERE project_id = %s AND user_id = %s
            ORDER BY updated_at DESC LIMIT 200""", (project_id, user_id)))


async def create(project_id: str, user_id: str, title: Optional[str] = None) -> Dict[str, Any]:
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        f"INSERT INTO chat_threads (project_id, user_id, title) VALUES (%s, %s, %s) RETURNING {_COLUMNS}",
        (project_id, user_id, (title or NEW_TITLE)[:120])))
    return {**rows[0], "message_count": 0}


async def get(thread_id: str, user_id: str) -> Dict[str, Any]:
    """The thread, if it belongs to this user (404 otherwise)."""
    import uuid
    try:
        tid = str(uuid.UUID(str(thread_id)))
    except ValueError:
        raise HTTPException(404, "Chat not found")
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        f"SELECT {_COLUMNS} FROM chat_threads WHERE id = %s AND user_id = %s", (tid, user_id)))
    if not rows:
        raise HTTPException(404, "Chat not found")
    return rows[0]


async def resolve(project_id: str, user_id: str, thread_id: Optional[str]) -> Dict[str, Any]:
    """The chat a message goes to: the given one (it must be in this book), else the latest, else a new one."""
    if thread_id:
        thread = await get(thread_id, user_id)
        if thread["project_id"] != str(project_id):
            raise HTTPException(404, "Chat not found")
        return thread
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        f"SELECT {_COLUMNS} FROM chat_threads WHERE project_id = %s AND user_id = %s ORDER BY updated_at DESC LIMIT 1",
        (project_id, user_id)))
    return rows[0] if rows else await create(project_id, user_id)


async def touch(thread: Dict[str, Any], message: str) -> None:
    """A new message: move the chat to the top, and name it after its first question."""
    pg = _pg()
    title = title_from(message) if thread.get("title") == NEW_TITLE else None
    await _db(lambda: pg.fetch(
        "UPDATE chat_threads SET updated_at = now(), title = COALESCE(%s, title) WHERE id = %s",
        (title, thread["id"])))


async def rename(thread_id: str, user_id: str, title: str) -> Dict[str, Any]:
    await get(thread_id, user_id)
    pg = _pg()
    rows = await _db(lambda: pg.fetch(
        f"UPDATE chat_threads SET title = %s WHERE id = %s RETURNING {_COLUMNS}",
        ((title or NEW_TITLE).strip()[:120] or NEW_TITLE, thread_id)))
    return rows[0]


async def delete(thread_id: str, user_id: str) -> None:
    """Delete a chat with its messages and summary (the student's choice; owner decision 13)."""
    thread = await get(thread_id, user_id)
    pg = _pg()
    await _db(lambda: pg.fetch("DELETE FROM chat_threads WHERE id = %s", (thread["id"],)))


async def messages(thread_id: str) -> List[Dict[str, Any]]:
    pg = _pg()
    return await _db(lambda: pg.fetch(
        "SELECT role, content, sources, created_at, image_path FROM chat_messages WHERE thread_id = %s ORDER BY created_at",
        (thread_id,)))
