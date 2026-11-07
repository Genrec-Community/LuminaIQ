from fastapi import APIRouter, HTTPException, Depends
from utils.rate_limit import rate_limit
from utils.tools import require_tool
from services.mcq_service import mcq_service
from models.schemas import (
    MCQGenerateRequest,
    MCQTestResponse,
    MCQSubmitRequest,
    MCQSubmitResponse,
)
from typing import Any, List, Dict
from api.access import assert_row_access
from api.deps import get_current_user
from services import levels
from services.usage_service import usage, metered

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


@router.get("/saved/{project_id}")
async def get_saved_tests(
    project_id: str, current_user: dict = Depends(get_current_user)
):
    """Get all saved MCQ tests for a project"""
    try:
        tests = await mcq_service.get_saved_tests(project_id)
        return tests
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/saved/view/{test_id}")
async def get_saved_test(
    test_id: str, current_user: dict = Depends(get_current_user)
):
    """Get a specific saved MCQ test with full questions"""
    await assert_row_access("mcq_tests", test_id, current_user["id"])
    try:
        test = await mcq_service.get_saved_test(test_id)
        return test
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/saved/{test_id}")
async def delete_saved_test(
    test_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a saved MCQ test"""
    await assert_row_access("mcq_tests", test_id, current_user["id"])
    try:
        await mcq_service.delete_saved_test(test_id)
        return {"message": "Test deleted successfully"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/generate", response_model=MCQTestResponse, dependencies=[Depends(rate_limit("generate")), Depends(require_tool("quiz"))])
async def generate_mcq(
    request: MCQGenerateRequest, current_user: dict = Depends(get_current_user)
):
    """
    Generate MCQ questions for a chapter/topic
    """
    metered(current_user, "questions")
    wanted = max(1, request.num_questions or 1)
    # Questions drawn from a shared book's pool are free: check now, charge only new ones
    await usage.check(current_user["id"], "questions", wanted)
    try:
        eff = await levels.effective_for(current_user["id"])
        result = await mcq_service.generate_mcq(
            project_id=request.project_id,
            topic=request.topic,
            num_questions=request.num_questions,
            selected_documents=request.selected_documents,
            difficulty=request.difficulty,
            user_id=current_user["id"],
            level=eff.get("level", ""),
        )
    except Exception as e:
        raise HTTPException(500, str(e))
    if result.get("generated"):
        await usage.charge(current_user["id"], "questions", min(result["generated"], wanted))
    return result


@router.post("/submit", response_model=MCQSubmitResponse)
async def submit_mcq(
    request: MCQSubmitRequest, current_user: dict = Depends(get_current_user)
):
    """
    Submit MCQ answers and get evaluation
    """
    await assert_row_access("mcq_tests", request.test_id, current_user["id"])
    try:
        result = await mcq_service.submit_test(
            test_id=request.test_id, answers=request.answers, user_id=current_user["id"]
        )
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
