from fastapi import APIRouter, HTTPException, Depends
from typing import Any
from services.notes_service import notes_service
from models.schemas import NotesGenerateRequest, NotesGenerateResponse

router = APIRouter()

@router.post("/generate", response_model=NotesGenerateResponse)
async def generate_notes(request: NotesGenerateRequest) -> Any:
    """Generate notes for a project"""
    try:
        content = await notes_service.generate_notes(
            project_id=request.project_id,
            note_type=request.note_type,
            topic=request.topic,
            selected_documents=request.selected_documents
        )
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
