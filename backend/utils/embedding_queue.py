"""
Parallel Embedding Processor with Global Concurrency Control

Processes all documents in parallel BUT with shared resource limits.
This prevents database timeouts when multiple PDFs are uploaded together.

Features:
- Immediate processing (no queue delays)
- Parallel document processing
- GLOBAL concurrency limits prevent Qdrant timeouts
- Progress tracking per document
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from utils.logger import logger


class JobStatus(Enum):
    PENDING = "pending"  # Just created, waiting for semaphore
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EmbeddingJob:
    """A job in the embedding processor"""

    job_id: str
    document_id: str
    project_id: str
    filename: str
    chunks: List[str]
    status: JobStatus = JobStatus.PENDING
    position: int = 0
    total_in_queue: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: int = 0  # 0-100
    total_batches: int = 0
    completed_batches: int = 0


class EmbeddingQueue:
    """
    Parallel Embedding Processor with Global Concurrency Control.

    KEY FIX: Uses global semaphores to prevent overwhelming Qdrant
    when multiple documents are uploaded simultaneously.

    Without limits: 3 PDFs x 20 concurrent batches = 60 parallel DB writes = TIMEOUT
    With limits: 3 PDFs share 8 concurrent DB writes = SUCCESS

    Usage:
        queue = get_embedding_queue()
        job_id = await queue.enqueue(doc_id, project_id, filename, chunks, callback)
        status = queue.get_job_status(job_id)
    """

    # Global limits - shared across ALL documents
    MAX_CONCURRENT_DOCUMENTS = 5  # Max docs processing at once
    MAX_GLOBAL_DB_OPERATIONS = 8  # Total concurrent Qdrant writes
    MAX_GLOBAL_EMBEDDINGS = 10  # Total concurrent embedding API calls

    # Singleton semaphores - created once, shared by all
    _doc_semaphore: Optional[asyncio.Semaphore] = None
    _db_semaphore: Optional[asyncio.Semaphore] = None
    _embed_semaphore: Optional[asyncio.Semaphore] = None

    def __init__(self):
        self._jobs: Dict[str, EmbeddingJob] = {}  # job_id -> job
        self._job_counter = 0
        self._lock = asyncio.Lock()
        self._active_tasks: Dict[str, asyncio.Task] = {}  # job_id -> task
        self._ensure_semaphores()

    def _ensure_semaphores(self):
        """Create semaphores if not already created"""
        if EmbeddingQueue._doc_semaphore is None:
            EmbeddingQueue._doc_semaphore = asyncio.Semaphore(
                self.MAX_CONCURRENT_DOCUMENTS
            )
        if EmbeddingQueue._db_semaphore is None:
            EmbeddingQueue._db_semaphore = asyncio.Semaphore(
                self.MAX_GLOBAL_DB_OPERATIONS
            )
        if EmbeddingQueue._embed_semaphore is None:
            EmbeddingQueue._embed_semaphore = asyncio.Semaphore(
                self.MAX_GLOBAL_EMBEDDINGS
            )

        logger.info(
            f"[EmbeddingQueue] Limits: {self.MAX_CONCURRENT_DOCUMENTS} docs, "
            f"{self.MAX_GLOBAL_DB_OPERATIONS} DB ops, {self.MAX_GLOBAL_EMBEDDINGS} embed calls"
        )

    @classmethod
    def get_db_semaphore(cls) -> asyncio.Semaphore:
        """Get the global DB operation semaphore for use in document_service"""
        if cls._db_semaphore is None:
            cls._db_semaphore = asyncio.Semaphore(cls.MAX_GLOBAL_DB_OPERATIONS)
        return cls._db_semaphore

    @classmethod
    def get_embed_semaphore(cls) -> asyncio.Semaphore:
        """Get the global embedding semaphore for use in document_service"""
        if cls._embed_semaphore is None:
            cls._embed_semaphore = asyncio.Semaphore(cls.MAX_GLOBAL_EMBEDDINGS)
        return cls._embed_semaphore

    async def start(self):
        """No-op - processing starts immediately on enqueue"""
        pass

    async def stop(self):
        """Cancel all active processing tasks"""
        for job_id, task in list(self._active_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._active_tasks.clear()
        logger.info("[EmbeddingQueue] All tasks stopped")

    async def enqueue(
        self,
        document_id: str,
        project_id: str,
        filename: str,
        chunks: List[str],
        process_callback: Callable[[EmbeddingJob], Any],
    ) -> str:
        """
        Add a document and start processing immediately.

        Args:
            document_id: The document ID
            project_id: The project ID
            filename: Document filename
            chunks: List of text chunks to embed
            process_callback: Async function to call for processing

        Returns:
            job_id: Unique identifier for this job
        """
        async with self._lock:
            self._job_counter += 1
            job_id = f"emb_{self._job_counter}_{document_id[:8]}"

            job = EmbeddingJob(
                job_id=job_id,
                document_id=document_id,
                project_id=project_id,
                filename=filename,
                chunks=chunks,
                position=0,
                total_in_queue=1,
            )

            self._jobs[job_id] = job

            active_count = len(self._active_tasks)
            logger.info(
                f"[EmbeddingQueue] Starting {filename} | "
                f"Chunks: {len(chunks)} | Job: {job_id} | "
                f"Active: {active_count + 1}"
            )

            # Start processing immediately in a new task
            task = asyncio.create_task(self._process_job(job, process_callback))
            self._active_tasks[job_id] = task

            return job_id

    async def _process_job(
        self, job: EmbeddingJob, callback: Callable[[EmbeddingJob], Any]
    ):
        """Process a single job with document-level concurrency control"""
        try:
            # Wait for document slot (limits concurrent docs)
            async with EmbeddingQueue._doc_semaphore:
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.now()
                job.position = 0

                logger.info(
                    f"[EmbeddingQueue] Processing {job.filename} | "
                    f"Chunks: {len(job.chunks)}"
                )

                # Execute the callback (which uses global semaphores for batch ops)
                await callback(job)

                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now()
                job.progress = 100

                duration = (job.completed_at - job.started_at).total_seconds()
                chunks_per_sec = len(job.chunks) / max(0.1, duration)
                logger.info(
                    f"[EmbeddingQueue] Completed {job.filename} | "
                    f"Duration: {duration:.1f}s | Speed: {chunks_per_sec:.1f} chunks/s"
                )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            logger.error(f"[EmbeddingQueue] Failed {job.filename}: {e}")
            import traceback

            logger.error(f"[EmbeddingQueue] Traceback: {traceback.format_exc()}")

        finally:
            # Remove from active tasks
            self._active_tasks.pop(job.job_id, None)

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a specific job"""
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "document_id": job.document_id,
            "filename": job.filename,
            "status": job.status.value,
            "position": job.position,
            "total_in_queue": job.total_in_queue,
            "progress": job.progress,
            "completed_batches": job.completed_batches,
            "total_batches": job.total_batches,
            "error_message": job.error_message,
        }

    def get_document_status(self, document_id: str) -> Optional[Dict]:
        """Get status by document_id"""
        for job in self._jobs.values():
            if job.document_id == document_id:
                return self.get_job_status(job.job_id)
        return None

    def get_queue_stats(self) -> Dict:
        """Get overall queue statistics"""
        pending = [j for j in self._jobs.values() if j.status == JobStatus.PENDING]
        processing = [
            j for j in self._jobs.values() if j.status == JobStatus.PROCESSING
        ]
        completed = [j for j in self._jobs.values() if j.status == JobStatus.COMPLETED]
        failed = [j for j in self._jobs.values() if j.status == JobStatus.FAILED]

        return {
            "queued": len(pending),
            "processing": len(processing),
            "completed": len(completed),
            "failed": len(failed),
            "total": len(self._jobs),
            "active_tasks": len(self._active_tasks),
            "current_jobs": [
                {"filename": j.filename, "progress": j.progress} for j in processing
            ],
        }

    def update_job_progress(
        self, job_id: str, completed_batches: int, total_batches: int
    ):
        """Update progress for a job (called during processing)"""
        job = self._jobs.get(job_id)
        if job:
            job.completed_batches = completed_batches
            job.total_batches = total_batches
            job.progress = int((completed_batches / max(1, total_batches)) * 100)

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove completed/failed jobs older than max_age_hours"""
        now = datetime.now()
        to_remove = []

        for job_id, job in self._jobs.items():
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                if job.completed_at:
                    age = (now - job.completed_at).total_seconds() / 3600
                    if age > max_age_hours:
                        to_remove.append(job_id)

        for job_id in to_remove:
            del self._jobs[job_id]

        if to_remove:
            logger.info(f"[EmbeddingQueue] Cleaned up {len(to_remove)} old jobs")


# Singleton instance
_embedding_queue: Optional[EmbeddingQueue] = None


def get_embedding_queue() -> EmbeddingQueue:
    """Get the global embedding queue"""
    global _embedding_queue
    if _embedding_queue is None:
        _embedding_queue = EmbeddingQueue()
    return _embedding_queue
