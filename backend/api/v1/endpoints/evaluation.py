from fastapi import APIRouter, HTTPException, Depends
from services.evaluation_service import evaluation_service
from models.schemas import (
    EvaluationSubmitRequest,
    EvaluationResponse,
    SubjectiveTestGenerateRequest,
    SubjectiveTestResponse,
    SubjectiveTestSubmitRequest,
    SubjectiveTestResult,
)
from typing import Any
from api.deps import get_current_user

router = APIRouter()


@router.post("/generate-test", response_model=SubjectiveTestResponse)
async def generate_subjective_test(
    request: SubjectiveTestGenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a subjective test for a topic

    answer_size options:
    - small: Brief 1-2 sentence answers (max 15 questions)
    - medium: Paragraph answers (max 10 questions)
    - large: Detailed comprehensive answers (max 5 questions)
    """
    try:
        result = await evaluation_service.generate_subjective_test(
            project_id=request.project_id,
            topic=request.topic,
            num_questions=request.num_questions,
            selected_documents=request.selected_documents,
            answer_size=request.answer_size,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/submit-test", response_model=SubjectiveTestResult)
async def submit_subjective_test_endpoint(
    request: SubjectiveTestSubmitRequest, current_user: dict = Depends(get_current_user)
):
    """
    Submit subjective test answers for evaluation
    """
    try:
        result = await evaluation_service.submit_subjective_test(
            test_id=request.test_id, answers=request.answers
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/submit", response_model=EvaluationResponse)
async def submit_evaluation(
    request: EvaluationSubmitRequest, current_user: dict = Depends(get_current_user)
):
    """
    Submit a subjective answer for AI evaluation (Single Question)
    """
    try:
        result = await evaluation_service.evaluate_answer(
            project_id=request.project_id,
            user_id=current_user["id"],
            question=request.question,
            user_answer=request.user_answer,
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
