"""
Adaptive Fair-Share Rate Limiter - DISABLED

Rate limiting has been removed as the API limits have been increased.
This module now provides pass-through methods with no delays.

All jobs run at full speed with no throttling.
"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from utils.logger import logger


@dataclass
class JobInfo:
    """Information about an active embedding job"""

    job_id: str
    document_id: str
    total_batches: int
    completed_batches: int = 0
    start_time: float = field(default_factory=time.monotonic)


class AdaptiveFairShareLimiter:
    """
    Adaptive Rate Limiter - DISABLED.

    All jobs run at full speed with no throttling.
    Rate limiting has been removed.
    """

    def __init__(self):
        # Job tracking (for stats only)
        self._active_jobs: Dict[str, JobInfo] = {}
        self._job_counter = 0
        self._lock = asyncio.Lock()

        # Stats
        self._total_requests = 0

    async def register_job(self, document_id: str, total_batches: int) -> str:
        """
        Register a new embedding job.
        Returns a unique job_id.
        """
        async with self._lock:
            self._job_counter += 1
            job_id = f"job_{self._job_counter}_{document_id[:8]}"

            self._active_jobs[job_id] = JobInfo(
                job_id=job_id, document_id=document_id, total_batches=total_batches
            )

            logger.info(
                f"[RateLimiter] Registered {job_id} | "
                f"Active jobs: {len(self._active_jobs)} | "
                f"Rate: UNLIMITED (no rate limiting)"
            )

            return job_id

    async def unregister_job(self, job_id: str):
        """
        Remove a completed job from tracking.
        """
        async with self._lock:
            if job_id in self._active_jobs:
                job = self._active_jobs.pop(job_id)
                duration = time.monotonic() - job.start_time

                logger.info(
                    f"[RateLimiter] Completed {job_id} | "
                    f"Duration: {duration:.1f}s | "
                    f"Batches: {job.completed_batches}/{job.total_batches} | "
                    f"Remaining jobs: {len(self._active_jobs)}"
                )

    async def acquire(self, job_id: Optional[str] = None, tokens: int = 1) -> float:
        """
        Acquire tokens - NO WAITING (rate limiting disabled).

        Returns: 0.0 (no wait time)
        """
        self._total_requests += 1

        # Update job progress if job_id provided
        if job_id and job_id in self._active_jobs:
            self._active_jobs[job_id].completed_batches += 1

        return 0.0

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "active_jobs": len(self._active_jobs),
            "current_rate_per_job": "unlimited",
            "total_requests": self._total_requests,
            "total_waits": 0,
            "avg_wait_time": 0.0,
            "current_tokens": "unlimited",
            "status": "disabled - no rate limiting",
            "jobs": [
                {
                    "job_id": job.job_id,
                    "progress": f"{job.completed_batches}/{job.total_batches}",
                    "duration": time.monotonic() - job.start_time,
                }
                for job in self._active_jobs.values()
            ],
        }

    def get_active_job_count(self) -> int:
        """Get number of currently active jobs"""
        return len(self._active_jobs)


# Singleton instance
_adaptive_limiter: Optional[AdaptiveFairShareLimiter] = None


def get_adaptive_limiter() -> AdaptiveFairShareLimiter:
    """Get the global adaptive rate limiter (disabled - no rate limiting)"""
    global _adaptive_limiter
    if _adaptive_limiter is None:
        _adaptive_limiter = AdaptiveFairShareLimiter()
    return _adaptive_limiter
