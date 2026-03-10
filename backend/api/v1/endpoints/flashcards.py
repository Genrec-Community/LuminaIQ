from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from api.deps import get_current_user
from services.flashcard_service import FlashcardService

router = APIRouter()

class CardCreate(BaseModel):
    front: str
    back: str

class FlashcardSetCreate(BaseModel):
    title: str
    topic: Optional[str] = None
    description: Optional[str] = None
    cards: List[CardCreate]

class FlashcardSetUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None
    description: Optional[str] = None

class FlashcardGenerateRequest(BaseModel):
    topic: str
    num_cards: int = 10
    selected_documents: List[str] = []

@router.get("/{project_id}")
async def get_flashcard_sets(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all flashcard sets for a project"""
    service = FlashcardService()
    return await service.get_flashcard_sets(current_user["id"], project_id)

@router.post("/{project_id}")
async def create_flashcard_set(
    project_id: str,
    data: FlashcardSetCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new flashcard set"""
    service = FlashcardService()
    return await service.create_flashcard_set(
        user_id=current_user["id"],
        project_id=project_id,
        title=data.title,
        topic=data.topic,
        description=data.description,
        cards=data.cards
    )

@router.put("/{set_id}")
async def update_flashcard_set(
    set_id: str,
    data: FlashcardSetUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a flashcard set"""
    service = FlashcardService()
    return await service.update_flashcard_set(current_user["id"], set_id, data.dict(exclude_unset=True))

@router.delete("/{set_id}")
async def delete_flashcard_set(
    set_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a flashcard set"""
    service = FlashcardService()
    await service.delete_flashcard_set(current_user["id"], set_id)
    return {"message": "Flashcard set deleted successfully"}

@router.get("/{set_id}/cards")
async def get_flashcards(
    set_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all flashcards in a set"""
    service = FlashcardService()
    return await service.get_flashcards(current_user["id"], set_id)

@router.post("/{project_id}/generate")
async def generate_flashcards(
    project_id: str,
    data: FlashcardGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate flashcards using AI"""
    service = FlashcardService()
    return await service.generate_flashcards_with_ai(
        user_id=current_user["id"],
        project_id=project_id,
        topic=data.topic,
        num_cards=data.num_cards,
        selected_documents=data.selected_documents
    )
