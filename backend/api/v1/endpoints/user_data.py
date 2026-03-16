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
    activity_type: str
    meta: Optional[Dict[str, Any]] = None


# ============== Gamification ==============

@router.get("/gamification")
async def get_gamification_data(current_user: dict = Depends(get_current_user)):
    try:
        data = await gamification.get_gamification(current_user["id"])
        return data
    except Exception as e:
        logger.error(f"Error getting gamification: {e}")
        raise HTTPException(500, str(e))


@router.post("/gamification/award-xp")
async def award_xp(
    request: AwardXPRequest,
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await gamification.award_xp(
            user_id=current_user["id"],
            activity_type=request.activity_type,
            meta=request.meta,
        )
        return result
    except Exception as e:
        logger.error(f"Error awarding XP: {e}")
        raise HTTPException(500, str(e))


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
        return {"settings": settings}
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(500, str(e))


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
        topics = await user_data.save_learning_progress(
            user_id=current_user["id"],
            project_id=request.project_id,
            completed_topics=request.completed_topics,
        )
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
