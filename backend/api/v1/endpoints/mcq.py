from fastapi import APIRouter, HTTPException, Depends
from services.mcq_service import mcq_service
from models.schemas import (
    MCQGenerateRequest,
    MCQTestResponse,
    MCQSubmitRequest,
    MCQSubmitResponse,
)
from typing import Any, List, Dict
from api.deps import get_current_user

router = APIRouter()


@router.get("/topics/{project_id}", response_model=Dict[str, Any])
async def get_topics(project_id: str, current_user: dict = Depends(get_current_user)):
    """
    Extract potential topics/chapters from project documents
    """
    try:
        topics = await mcq_service.get_topics(project_id)
        return topics
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/generate", response_model=MCQTestResponse)
async def generate_mcq(
    request: MCQGenerateRequest, current_user: dict = Depends(get_current_user)
):
    """
    Generate MCQ questions for a chapter/topic
    """
    try:
        result = await mcq_service.generate_mcq(
            project_id=request.project_id,
            topic=request.topic,
            num_questions=request.num_questions,
            selected_documents=request.selected_documents,
            difficulty=request.difficulty,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/submit", response_model=MCQSubmitResponse)
async def submit_mcq(
    request: MCQSubmitRequest, current_user: dict = Depends(get_current_user)
):
    """
    Submit MCQ answers and get evaluation
    """
    try:
        result = await mcq_service.submit_test(
            test_id=request.test_id, answers=request.answers
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
