"""
Background jobs API, backed by the durable Postgres queue (utils/job_queue.py).

Users can see their own jobs (book processing, imports). Submitting jobs
directly is limited to kinds in USER_JOB_KINDS; none are open yet, because the
generation tools run as normal requests.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from db.client import async_db, get_supabase_client
from utils import job_queue as q

router = APIRouter()

# Job kinds a user may submit through this API (each needs a handler in services/jobs.py)
USER_JOB_KINDS: set = set()

# Queue status -> the names this API always used
_STATUS = {"queued": "pending", "running": "processing", "done": "completed", "failed": "failed"}


class JobSubmitRequest(BaseModel):
    job_type: str
    metadata: Dict[str, Any] = {}


class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: int
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


def _response(job: Dict[str, Any]) -> JobStatusResponse:
    status = _STATUS.get(job["status"], job["status"])
    return JobStatusResponse(
        job_id=job["id"], job_type=job["kind"], status=status,
        progress=100 if job["status"] in ("done", "failed") else 0,
        result=job.get("result"), error=job.get("error") if job["status"] == "failed" else None,
        created_at=job["created_at"],
        started_at=job.get("heartbeat_at") if job["attempts"] else None,
        completed_at=job.get("finished_at"),
    )


async def _own_job(job_id: str, user_id: str) -> Dict[str, Any]:
    pg = get_supabase_client().pg
    job = await async_db(lambda: q.get(pg, job_id))
    if not job or job.get("user_id") != user_id:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/submit", response_model=JobSubmitResponse)
async def submit_job(request: JobSubmitRequest, current_user: dict = Depends(get_current_user)):
    if request.job_type not in USER_JOB_KINDS:
        raise HTTPException(400, f"Unknown job type: {request.job_type}")
    from services.jobs import enqueue

    job = await enqueue(request.job_type, request.metadata, user_id=current_user["id"])
    return JobSubmitResponse(job_id=job["id"], status=_STATUS[job["status"]], created_at=job["created_at"])


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    return _response(await _own_job(job_id, current_user["id"]))


@router.get("/my-jobs", response_model=List[JobStatusResponse])
async def get_my_jobs(limit: int = 10, current_user: dict = Depends(get_current_user)):
    pg = get_supabase_client().pg
    jobs = await async_db(lambda: q.list_for_user(pg, current_user["id"], max(1, min(limit, 50))))
    return [_response(j) for j in jobs]


@router.get("/status/{job_id}/poll")
async def poll_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    """Lightweight polling: minimal fields."""
    job = await _own_job(job_id, current_user["id"])
    status = _STATUS.get(job["status"], job["status"])
    return {"job_id": job["id"], "status": status,
            "progress": 100 if job["status"] in ("done", "failed") else 0,
            "completed": job["status"] in ("done", "failed")}
