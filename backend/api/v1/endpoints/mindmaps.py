from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from api.deps import get_current_user
from services.mindmap_service import MindmapService

router = APIRouter()

class MindmapGenerate(BaseModel):
    title: str
    topic: str
    selected_documents: List[str] = []

class MindmapUpdate(BaseModel):
    title: Optional[str] = None
    data: Optional[dict] = None

@router.get("/{project_id}")
async def get_mindmaps(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all mindmaps for a project"""
    service = MindmapService()
    return await service.get_mindmaps(current_user["id"], project_id)

@router.post("/{project_id}/generate")
async def generate_mindmap(
    project_id: str,
    data: MindmapGenerate,
    current_user: dict = Depends(get_current_user)
):
    """Generate a new mindmap"""
    service = MindmapService()
    return await service.generate_mindmap(
        user_id=current_user["id"],
        project_id=project_id,
        title=data.title,
        topic=data.topic,
        selected_documents=data.selected_documents
    )

@router.get("/{mindmap_id}/view")
async def get_mindmap(
    mindmap_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific mindmap"""
    service = MindmapService()
    return await service.get_mindmap(current_user["id"], mindmap_id)

@router.put("/{mindmap_id}")
async def update_mindmap(
    mindmap_id: str,
    data: MindmapUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a mindmap"""
    service = MindmapService()
    return await service.update_mindmap(current_user["id"], mindmap_id, data.dict(exclude_unset=True))

@router.delete("/{mindmap_id}")
async def delete_mindmap(
    mindmap_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a mindmap"""
    service = MindmapService()
    await service.delete_mindmap(current_user["id"], mindmap_id)
    return {"message": "Mindmap deleted successfully"}
