"""
User Data API Endpoints

Provides REST endpoints for all user data previously stored in localStorage:
  - Settings, Bookmarks, Study Activity,
  - Learning Progress, Pomodoro, Recent Searches, Streaks
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from api.deps import get_current_user
from services.user_data_service import user_data
from services.gamification_service import gamification
from utils.logger import logger

router = APIRouter()


# ============== Request Models ==============

class SaveSettingsRequest(BaseModel):
    settings: Dict[str, Any]


class AddBookmarkRequest(BaseModel):
    project_id: str
    title: str
    note: str = ""
    document_id: Optional[str] = None
    type: str = "general"
    highlight_text: Optional[str] = None
    color: Optional[str] = None


class UpdateBookmarkRequest(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None
    type: Optional[str] = None
    highlight_text: Optional[str] = None
    color: Optional[str] = None


class RecordActivityRequest(BaseModel):
    project_id: str
    activity_type: str  # quiz, review, notes, qa, pomodoro, chat
    meta: Optional[Dict[str, Any]] = None


class SaveProgressRequest(BaseModel):
    project_id: str
    completed_topics: List[str]


class SavePomodoroRequest(BaseModel):
    project_id: Optional[str] = None
    document_id: Optional[str] = None
    sessions: int
    focus_time_minutes: int


class SaveSearchRequest(BaseModel):
    project_id: str
    query: str


class ClearSearchesRequest(BaseModel):
    project_id: str


class AwardXPRequest(BaseModel):
    activity_type: str = "activity"
    meta: Optional[Dict[str, Any]] = None
    # The last time this device synced: XP earned since then comes back for the toasts
    since: Optional[str] = None


# ============== Gamification ==============

@router.get("/gamification")
async def get_gamification_data(since: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        data = await gamification.get_gamification(current_user["id"], since)
        return data
    except Exception as e:
        logger.error(f"Error getting gamification: {e}")
        raise HTTPException(500, str(e))


@router.post("/gamification/award-xp")
async def award_xp(
    request: AwardXPRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Sync after an activity. Grants nothing itself (Phase 7: XP comes only from learning the
    server measured); returns the state plus any XP earned since `since`, for the toasts.
    """
    try:
        result = await gamification.award_xp(
            user_id=current_user["id"],
            activity_type=request.activity_type,
            meta=request.meta,
            since=request.since,
        )
        return result
    except Exception as e:
        logger.error(f"Error awarding XP: {e}")
        raise HTTPException(500, str(e))


@router.get("/leaderboard")
async def class_leaderboard(current_user: dict = Depends(get_current_user)):
    """This week's learning XP in the student's class (school level, when the class has the leaderboard on)."""
    from services.leaderboard import class_week
    return await class_week(current_user["id"])


# ============== Settings ==============

@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    try:
        settings = await user_data.get_settings(current_user["id"])
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(500, str(e))


@router.put("/settings")
async def save_settings(
    request: SaveSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        settings = await user_data.save_settings(current_user["id"], request.settings)
        from services.levels import forget
        await forget(current_user["id"])   # studyLevel may have changed
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(500, str(e))


# ============== Where the student left off (Phase 5) ==============
# One JSON object per user: last book and view, in-progress quiz, lesson position, so a
# student resumes on any device. PATCH merges keys; a null value removes a key.

APP_STATE_MAX_BYTES = 64 * 1024


class AppStatePatch(BaseModel):
    state: Dict[str, Any]


@router.get("/state")
async def get_app_state(current_user: dict = Depends(get_current_user)):
    from db.client import async_db, get_supabase_client
    pg = get_supabase_client().pg
    rows = await async_db(lambda: pg.fetch("SELECT state, updated_at FROM app_state WHERE user_id = %s",
                                           (current_user["id"],)))
    return {"state": rows[0]["state"] if rows else {}, "updated_at": rows[0]["updated_at"] if rows else None}


@router.patch("/state")
async def patch_app_state(body: AppStatePatch, current_user: dict = Depends(get_current_user)):
    import json as _json
    from db.client import async_db, get_supabase_client
    if len(body.state) > 50 or any(len(k) > 120 for k in body.state):
        raise HTTPException(400, "Too many or too long keys.")
    pg = get_supabase_client().pg
    uid = current_user["id"]
    sets = {k: v for k, v in body.state.items() if v is not None}
    drops = [k for k, v in body.state.items() if v is None]

    def run():
        with pg.pool.connection() as conn:
            with conn.transaction():
                row = conn.execute("SELECT state FROM app_state WHERE user_id = %s FOR UPDATE", (uid,)).fetchone()
                state = dict(row["state"]) if row else {}
                state.update(sets)
                for k in drops:
                    state.pop(k, None)
                raw = _json.dumps(state)
                if len(raw.encode()) > APP_STATE_MAX_BYTES:
                    return None
                conn.execute(
                    """INSERT INTO app_state (user_id, state, updated_at) VALUES (%s, %s::jsonb, now())
                       ON CONFLICT (user_id) DO UPDATE SET state = EXCLUDED.state, updated_at = now()""", (uid, raw))
                return state

    state = await async_db(run)
    if state is None:
        raise HTTPException(413, "Saved state is too large.")
    return {"state": state}


# ============== Bookmarks ==============

@router.get("/bookmarks/{project_id}")
async def get_bookmarks(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        bookmarks = await user_data.get_bookmarks(current_user["id"], project_id)
        return {"bookmarks": bookmarks}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/bookmarks")
async def add_bookmark(
    request: AddBookmarkRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        bookmark = await user_data.add_bookmark(
            user_id=current_user["id"],
            project_id=request.project_id,
            title=request.title,
            note=request.note,
            document_id=request.document_id,
            bookmark_type=request.type,
            highlight_text=request.highlight_text,
            color=request.color,
        )
        return bookmark
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/bookmarks/{bookmark_id}")
async def update_bookmark(
    bookmark_id: str,
    request: UpdateBookmarkRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        updates = request.dict(exclude_none=True)
        result = await user_data.update_bookmark(current_user["id"], bookmark_id, updates)
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        success = await user_data.delete_bookmark(current_user["id"], bookmark_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(500, str(e))


# ============== Study Activity ==============

@router.get("/activity/{project_id}")
async def get_study_activity(
    project_id: str,
    days: int = 90,
    current_user: dict = Depends(get_current_user)
):
    try:
        activity = await user_data.get_study_activity(current_user["id"], project_id, days)
        return {"activity": activity}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/activity")
async def record_study_activity(
    request: RecordActivityRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await user_data.record_study_activity(
            user_id=current_user["id"],
            project_id=request.project_id,
            activity_type=request.activity_type,
            meta=request.meta,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ============== Learning Progress ==============

@router.get("/progress/{project_id}")
async def get_learning_progress(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        topics = await user_data.get_learning_progress(current_user["id"], project_id)
        return {"completed_topics": topics}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/progress")
async def save_learning_progress(
    request: SaveProgressRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        before = set(await user_data.get_learning_progress(current_user["id"], request.project_id) or [])
        topics = await user_data.save_learning_progress(
            user_id=current_user["id"],
            project_id=request.project_id,
            completed_topics=request.completed_topics,
        )
        # A plan step completed for the first time earns XP once (untick/retick earns nothing)
        from services.gamification_service import gamification
        for topic in [t for t in (topics or []) if t not in before][:10]:
            await gamification.award(current_user["id"], "exam_plan_step",
                                     dedupe_key=f"plan:{request.project_id}:{topic}",
                                     meta={"topic": topic, "project_id": request.project_id})
        return {"completed_topics": topics}
    except Exception as e:
        raise HTTPException(500, str(e))


# ============== Pomodoro ==============

@router.get("/pomodoro")
async def get_pomodoro(
    project_id: str = None,
    document_id: str = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        data = await user_data.get_pomodoro(
            user_id=current_user["id"],
            project_id=project_id,
            document_id=document_id,
        )
        return data
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/pomodoro")
async def save_pomodoro(
    request: SavePomodoroRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await user_data.save_pomodoro(
            user_id=current_user["id"],
            sessions=request.sessions,
            focus_time_minutes=request.focus_time_minutes,
            project_id=request.project_id,
            document_id=request.document_id,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ============== Recent Searches ==============

@router.get("/searches/{project_id}")
async def get_recent_searches(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        searches = await user_data.get_recent_searches(current_user["id"], project_id)
        return {"searches": searches}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/searches")
async def save_recent_search(
    request: SaveSearchRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        success = await user_data.save_recent_search(
            user_id=current_user["id"],
            project_id=request.project_id,
            query=request.query,
        )
        return {"success": success}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/searches/{project_id}")
async def clear_recent_searches(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        success = await user_data.clear_recent_searches(current_user["id"], project_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(500, str(e))


# ============== Streaks ==============

@router.get("/streaks/{project_id}")
async def get_streak(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        streak = await user_data.get_streak(current_user["id"], project_id)
        return streak
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/streaks/{project_id}")
async def update_streak(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        streak = await user_data.update_streak(current_user["id"], project_id)
        return streak
    except Exception as e:
        raise HTTPException(500, str(e))
