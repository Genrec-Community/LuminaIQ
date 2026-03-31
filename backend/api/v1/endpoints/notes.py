from fastapi import APIRouter, HTTPException, Depends
from typing import Any
from services.notes_service import notes_service
from models.schemas import NotesGenerateRequest
from api.deps import get_current_user

router = APIRouter()


@router.get("/saved/{project_id}")
async def get_saved_notes(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """Get all saved notes for a project"""
    try:
        notes = await notes_service.get_saved_notes(project_id, current_user["id"])
        return notes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved/view/{note_id}")
async def get_saved_note(
    note_id: str, current_user: dict = Depends(get_current_user)
):
    """Get a specific saved note with full content"""
    try:
        note = await notes_service.get_saved_note(note_id, current_user["id"])
        return note
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/saved/{note_id}")
async def delete_saved_note(
    note_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a saved note"""
    try:
        await notes_service.delete_saved_note(note_id, current_user["id"])
        return {"message": "Note deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_notes(
    request: NotesGenerateRequest,
    current_user: dict = Depends(get_current_user),
) -> Any:
    """Generate notes for a project (auto-saves to DB)"""
    try:
        result = await notes_service.generate_notes(
            project_id=request.project_id,
            note_type=request.note_type,
            topic=request.topic,
            selected_documents=request.selected_documents,
            user_id=current_user["id"],
        )
        # result is now a dict with content + optional note_id
        if isinstance(result, dict):
            return result
        return {"content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
