"""
Background Jobs API

Provides endpoints for async AI processing:
- Submit heavy AI tasks (MCQ, notes, mindmaps, flashcards)
- Poll for job status
- Get job results

These endpoints NEVER block - they return immediately with a job_id
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio

from api.deps import get_current_user
from utils.background_jobs import job_manager, JobStatus
from utils.cache import content_cache
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class JobSubmitRequest(BaseModel):
    """Request to submit a background job"""
    job_type: str
    metadata: Dict[str, Any] = {}


class JobSubmitResponse(BaseModel):
    """Response after submitting a job"""
    job_id: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    """Response with job status"""
    job_id: str
    job_type: str
    status: str
    progress: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# Job type to handler mapping
JOB_HANDLERS = {}


def register_job_handler(job_type: str):
    """Decorator to register a job handler"""
    def decorator(func):
        JOB_HANDLERS[job_type] = func
        return func
    return decorator


# Submit a new background job
@router.post("/submit", response_model=JobSubmitResponse)
async def submit_job(
    request: JobSubmitRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a heavy AI task to run in background.
    
    Returns immediately with job_id - never blocks.
    Use /status/{job_id} to check progress.
    """
    job_type = request.job_type
    
    # Check if handler exists
    if job_type not in JOB_HANDLERS:
        # Check if it's a direct generation request
        if job_type == "generate_mcq":
            job_type = "generate_mcq"
        elif job_type == "generate_notes":
            job_type = "generate_notes"
        elif job_type == "generate_mindmap":
            job_type = "generate_mindmap"
        elif job_type == "generate_flashcards":
            job_type = "generate_flashcards"
        else:
            raise HTTPException(400, f"Unknown job type: {job_type}")
    
    # Create job
    job = job_manager.create_job(
        job_type=job_type,
        user_id=current_user.get("id"),
        metadata=request.metadata
    )
    
    # Schedule background processing
    asyncio.create_task(process_job_async(job.id))
    
    logger.info(f"Submitted background job {job.id} of type {job_type}")
    
    return JobSubmitResponse(
        job_id=job.id,
        status=job.status.value,
        created_at=job.created_at.isoformat()
    )


async def process_job_async(job_id: str):
    """Process a job in background"""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        
        handler = JOB_HANDLERS.get(job.job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type: {job.job_type}"
            return
        
        # Execute the handler
        result = await handler(job, current_user=None)  # Will get user from job metadata
        
        job.result = result
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        
        # Cache result for quick retrieval
        cache_key = f"job_result:{job_id}"
        await content_cache.set(cache_key, result, ttl=3600)
        
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        job = job_manager.get_job(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()


# Get job status
@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the status of a background job"""
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Check if user owns this job
    if job.user_id and job.user_id != current_user.get("id"):
        raise HTTPException(403, "Not authorized to view this job")
    
    return JobStatusResponse(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status.value,
        progress=job.progress,
        result=job.result,
        error=job.error,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None
    )


# Get user's jobs
@router.get("/my-jobs", response_model=List[JobStatusResponse])
async def get_my_jobs(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """Get all background jobs for the current user"""
    user_id = current_user.get("id")
    jobs = job_manager.get_user_jobs(user_id, limit)
    
    return [
        JobStatusResponse(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status.value,
            progress=job.progress,
            result=job.result,
            error=job.error,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None
        )
        for job in jobs
    ]


# Quick status check - lightweight endpoint
@router.get("/status/{job_id}/poll")
async def poll_job_status(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Lightweight polling endpoint for job status.
    Returns minimal info for frequent polling.
    """
    job = job_manager.get_job(job_id)
    
    if not job:
        return {"status": "not_found"}
    
    # Check if user owns this job
    if job.user_id and job.user_id != current_user.get("id"):
        return {"status": "forbidden"}
    
    return {
        "job_id": job.id,
        "status": job.status.value,
        "progress": job.progress,
        "completed": job.status in [JobStatus.COMPLETED, JobStatus.FAILED]
    }
