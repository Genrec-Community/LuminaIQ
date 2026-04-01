"""
Background Job System for Heavy AI Tasks

This module provides async job processing for heavy AI endpoints:
- MCQ generation
- Notes generation  
- Mindmap generation
- Flashcard generation
- Document embedding

Fast endpoints (/fast/*) return immediately
Heavy endpoints (/heavy/*) return a job_id and process in background
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BackgroundJob:
    """Represents a background job"""
    id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = 0  # 0-100
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackgroundJobManager:
    """
    In-memory background job manager.
    For production, use Redis with proper persistence.
    """
    
    def __init__(self):
        self._jobs: Dict[str, BackgroundJob] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._cleanup_interval = 3600  # Cleanup every hour
        self._max_job_age = 3600 * 24  # Keep jobs for 24 hours
        
    def register_handler(self, job_type: str, handler: Callable):
        """Register a handler for a job type"""
        self._task_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
    
    def create_job(
        self, 
        job_type: str, 
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BackgroundJob:
        """Create a new background job"""
        job_id = str(uuid.uuid4())
        job = BackgroundJob(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            user_id=user_id,
            metadata=metadata or {}
        )
        self._jobs[job_id] = job
        logger.info(f"Created job {job_id} of type {job_type}")
        return job
    
    async def process_job(self, job_id: str) -> BackgroundJob:
        """Process a job asynchronously"""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status != JobStatus.PENDING:
            return job
            
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        
        handler = self._task_handlers.get(job.job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler for job type: {job.job_type}"
            return job
        
        try:
            logger.info(f"Processing job {job_id} of type {job.job_type}")
            # Run the handler with progress updates
            result = await handler(job)
            job.result = result
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress = 100
            logger.info(f"Job {job_id} completed successfully")
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}")
            job.status = JobStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            
        return job
    
    def get_job(self, job_id: str) -> Optional[BackgroundJob]:
        """Get a job by ID"""
        return self._jobs.get(job_id)
    
    def get_user_jobs(self, user_id: str, limit: int = 10) -> list:
        """Get jobs for a user"""
        user_jobs = [
            job for job in self._jobs.values() 
            if job.user_id == user_id
        ]
        # Sort by created_at descending
        user_jobs.sort(key=lambda x: x.created_at, reverse=True)
        return user_jobs[:limit]
    
    def cleanup_old_jobs(self):
        """Remove old completed/failed jobs"""
        cutoff = datetime.utcnow() - timedelta(seconds=self._max_job_age)
        to_remove = [
            job_id for job_id, job in self._jobs.items()
            if job.completed_at and job.completed_at < cutoff
        ]
        for job_id in to_remove:
            del self._jobs[job_id]
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old jobs")


# Global job manager instance
job_manager = BackgroundJobManager()


# Helper to run heavy tasks in background
async def run_in_background(
    job_type: str,
    user_id: Optional[str],
    metadata: Dict[str, Any],
    handler: Callable
) -> BackgroundJob:
    """Submit a job to run in the background"""
    job = job_manager.create_job(job_type, user_id, metadata)
    
    # Schedule the job to run
    asyncio.create_task(job_manager.process_job(job.id))
    
    return job
