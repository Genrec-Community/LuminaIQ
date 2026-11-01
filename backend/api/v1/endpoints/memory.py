"""
"What Lumina remembers about you" (AGENTS.md Phase 5). Only the student themselves can
read or change their memory; there is no teacher or admin route to it.

- GET    /memory               - facts, chat summaries, settings, and whether automatic memory applies
- POST   /memory               - add a fact {content, kind}
- PATCH  /memory/{id}          - edit a fact {content, kind?}
- DELETE /memory/{id}          - forget one fact
- DELETE /memory               - forget everything (facts and chat summaries; chats stay)
- PUT    /memory/settings      - {across_books?, auto?}
- DELETE /memory/summaries/{project_id} - forget one chat's summary
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.access import assert_project_owner
from api.deps import get_current_user
from db.client import async_db, get_supabase_client
from services import levels, memory

router = APIRouter()


def _id(value: str) -> str:
    import uuid
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise HTTPException(404, "Not found")


class MemoryIn(BaseModel):
    content: str = Field(..., min_length=2, max_length=300)
    kind: str = "fact"


class MemoryPatch(BaseModel):
    content: str = Field(..., min_length=2, max_length=300)
    kind: Optional[str] = None


class MemorySettings(BaseModel):
    across_books: Optional[bool] = None
    auto: Optional[bool] = None


async def _summaries(user_id: str):
    pg = get_supabase_client().pg
    return await async_db(lambda: pg.fetch(
        """SELECT s.project_id::text, p.name AS project_name, s.summary, s.covered_count, s.updated_at
           FROM chat_summaries s JOIN projects p ON p.id = s.project_id
           WHERE s.user_id = %s AND p.user_id = %s ORDER BY s.updated_at DESC""", (user_id, user_id)))


@router.get("")
async def get_memory(current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    eff = await levels.effective_for(uid)
    return {
        "memories": await memory.list_memories(uid),
        "summaries": await _summaries(uid),
        "settings": await memory.settings_for(uid),
        "auto_memory_available": memory.auto_memory_allowed(eff.get("level")),
        "limit": memory.MAX_MEMORIES,
    }


@router.post("")
async def add_memory(body: MemoryIn, current_user: dict = Depends(get_current_user)):
    return await memory.add_memory(current_user["id"], body.content, kind=body.kind, source="user")


@router.patch("/{memory_id}")
async def edit_memory(memory_id: str, body: MemoryPatch, current_user: dict = Depends(get_current_user)):
    row = await memory.update_memory(current_user["id"], _id(memory_id), body.content, body.kind)
    if not row:
        raise HTTPException(404, "Not found")
    return row


@router.delete("/{memory_id}")
async def forget(memory_id: str, current_user: dict = Depends(get_current_user)):
    if not await memory.delete_memory(current_user["id"], _id(memory_id)):
        raise HTTPException(404, "Not found")
    return {"deleted": True}


@router.delete("")
async def forget_everything(current_user: dict = Depends(get_current_user)):
    return await memory.clear_all(current_user["id"])


@router.put("/settings")
async def save_settings(body: MemorySettings, current_user: dict = Depends(get_current_user)):
    from services.user_data_service import user_data
    uid = current_user["id"]
    current = await user_data.get_settings(uid) or {}
    if body.across_books is not None:
        current["memoryAcrossBooks"] = body.across_books
    if body.auto is not None:
        current["autoMemory"] = body.auto
    await user_data.save_settings(uid, current)
    return await memory.settings_for(uid)


@router.delete("/summaries/{project_id}")
async def forget_summary(project_id: str, current_user: dict = Depends(get_current_user)):
    await assert_project_owner(project_id, current_user["id"])
    pg = get_supabase_client().pg
    await async_db(lambda: pg.fetch("DELETE FROM chat_summaries WHERE project_id = %s AND user_id = %s",
                                    (project_id, current_user["id"])))
    return {"deleted": True}
