"""
Parallel Embedding Processor - Best-in-Class Implementation

Features:
- True parallel document processing with smart concurrency control
- Automatic retry with exponential backoff for transient failures
- Optimized batch sizes to prevent database timeouts
- Per-document progress tracking
- Graceful error handling and recovery
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from utils.logger import logger


class ProcessingStatus(Enum):
    """Clear status names - no 'queued' since we process immediately"""

    PENDING = "pending"  # Just created, about to start
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ProcessingJob:
    """A document being processed"""

    job_id: str
    document_id: str
    project_id: str
    filename: str
    chunks: List[str]
    status: ProcessingStatus = ProcessingStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: int = 0  # 0-100
    total_batches: int = 0
    completed_batches: int = 0
    retry_count: int = 0
    current_batch: int = 0


class ParallelEmbeddingProcessor:
    """
    High-performance parallel embedding processor.

    Key optimizations:
    - Semaphore-controlled concurrency prevents database overwhelm
    - Smaller batch sizes reduce timeout risk
    - Automatic retries handle transient failures
    - Parallel document processing with controlled parallelism

    Usage:
        processor = get_embedding_processor()
        job_id = await processor.process(doc_id, project_id, filename, chunks, callback)
        status = processor.get_status(job_id)
    """

    # Tunable parameters for optimal performance
    MAX_CONCURRENT_DOCUMENTS = 3  # Max documents processing simultaneously
    MAX_CONCURRENT_BATCHES = 2  # Max batches per document at once
    MAX_RETRIES = 3  # Retries per batch before failing
    RETRY_BASE_DELAY = 1.0  # Base delay for exponential backoff (seconds)
    OPTIMAL_BATCH_SIZE = 50  # Chunks per batch (smaller = fewer timeouts)

    def __init__(
        self,
        max_concurrent_docs: int = None,
        max_concurrent_batches: int = None,
        max_retries: int = None,
        batch_size: int = None,
    ):
        # Allow override of defaults
        self.max_concurrent_docs = max_concurrent_docs or self.MAX_CONCURRENT_DOCUMENTS
        self.max_concurrent_batches = (
            max_concurrent_batches or self.MAX_CONCURRENT_BATCHES
        )
        self.max_retries = max_retries or self.MAX_RETRIES
        self.batch_size = batch_size or self.OPTIMAL_BATCH_SIZE

        self._jobs: Dict[str, ProcessingJob] = {}
        self._job_counter = 0
        self._lock = asyncio.Lock()
        self._active_tasks: Dict[str, asyncio.Task] = {}

        # Semaphore to limit concurrent document processing
        self._doc_semaphore = asyncio.Semaphore(self.max_concurrent_docs)
        # Global semaphore for database writes
        self._db_write_semaphore = asyncio.Semaphore(
            self.max_concurrent_docs * self.max_concurrent_batches
        )

        logger.info(
            f"[EmbeddingProcessor] Initialized | "
            f"Max docs: {self.max_concurrent_docs} | "
            f"Max batches: {self.max_concurrent_batches} | "
            f"Batch size: {self.batch_size}"
        )

    async def process(
        self,
        document_id: str,
        project_id: str,
        filename: str,
        chunks: List[str],
        process_callback: Callable[[ProcessingJob, List[str], int], Any],
    ) -> str:
        """
        Start processing a document immediately.

        Args:
            document_id: The document ID
            project_id: The project ID
            filename: Document filename
            chunks: List of text chunks to embed
            process_callback: Async function called for each batch
                             Signature: callback(job, batch_chunks, batch_index) -> Any

        Returns:
            job_id: Unique identifier for tracking this job
        """
        async with self._lock:
            self._job_counter += 1
            job_id = f"proc_{self._job_counter}_{document_id[:8]}"

            # Calculate batches upfront
            total_batches = (len(chunks) + self.batch_size - 1) // self.batch_size

            job = ProcessingJob(
                job_id=job_id,
                document_id=document_id,
                project_id=project_id,
                filename=filename,
                chunks=chunks,
                total_batches=total_batches,
            )
            self._jobs[job_id] = job

            logger.info(
                f"[EmbeddingProcessor] Starting {filename} | "
                f"Chunks: {len(chunks)} | Batches: {total_batches} | Job: {job_id}"
            )

            # Start processing with concurrency control
            task = asyncio.create_task(self._process_document(job, process_callback))
            self._active_tasks[job_id] = task

            return job_id

    async def _process_document(
        self,
        job: ProcessingJob,
        callback: Callable[[ProcessingJob, List[str], int], Any],
    ):
        """Process a document with controlled concurrency"""
        async with self._doc_semaphore:  # Limit concurrent documents
            try:
                job.status = ProcessingStatus.PROCESSING
                job.started_at = datetime.now()

                # Split chunks into batches
                batches = self._create_batches(job.chunks)
                job.total_batches = len(batches)

                logger.info(
                    f"[EmbeddingProcessor] Processing {job.filename} | "
                    f"{len(batches)} batches of ~{self.batch_size} chunks"
                )

                # Process batches with controlled parallelism
                await self._process_batches_parallel(job, batches, callback)

                # Check if all batches completed
                if job.completed_batches == job.total_batches:
                    job.status = ProcessingStatus.COMPLETED
                    job.completed_at = datetime.now()
                    job.progress = 100

                    duration = (job.completed_at - job.started_at).total_seconds()
                    chunks_per_sec = len(job.chunks) / max(0.1, duration)

                    logger.info(
                        f"[EmbeddingProcessor] Completed {job.filename} | "
                        f"Duration: {duration:.1f}s | "
                        f"Speed: {chunks_per_sec:.1f} chunks/s"
                    )
                else:
                    job.status = ProcessingStatus.FAILED
                    job.completed_at = datetime.now()
                    logger.error(
                        f"[EmbeddingProcessor] Failed {job.filename} | "
                        f"Completed: {job.completed_batches}/{job.total_batches}"
                    )

            except Exception as e:
                job.status = ProcessingStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.now()
                logger.error(f"[EmbeddingProcessor] Failed {job.filename}: {e}")
                import traceback

                logger.error(traceback.format_exc())
            finally:
                self._active_tasks.pop(job.job_id, None)

    def _create_batches(self, chunks: List[str]) -> List[List[str]]:
        """Split chunks into optimal batch sizes"""
        return [
            chunks[i : i + self.batch_size]
            for i in range(0, len(chunks), self.batch_size)
        ]

    async def _process_batches_parallel(
        self,
        job: ProcessingJob,
        batches: List[List[str]],
        callback: Callable,
    ):
        """Process batches with controlled parallelism and retries"""
        # Create semaphore for this document's batch concurrency
        batch_semaphore = asyncio.Semaphore(self.max_concurrent_batches)

        async def process_single_batch(batch_idx: int, batch: List[str]) -> bool:
            """Process a single batch with retry logic"""
            async with batch_semaphore:
                async with self._db_write_semaphore:  # Global DB write limit
                    return await self._process_batch_with_retry(
                        job, batch, batch_idx, callback
                    )

        # Process all batches with controlled concurrency
        tasks = [process_single_batch(idx, batch) for idx, batch in enumerate(batches)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful batches
        job.completed_batches = sum(1 for r in results if r is True)

    async def _process_batch_with_retry(
        self,
        job: ProcessingJob,
        batch: List[str],
        batch_idx: int,
        callback: Callable,
    ) -> bool:
        """Process a batch with exponential backoff retry"""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    job.status = ProcessingStatus.RETRYING
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"[{job.filename}] Batch {batch_idx + 1} retry {attempt}/{self.max_retries} "
                        f"after {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

                job.current_batch = batch_idx + 1

                # Execute the callback
                await callback(job, batch, batch_idx)

                # Update progress
                completed = job.completed_batches + 1
                job.progress = int((completed / max(1, job.total_batches)) * 100)

                logger.debug(
                    f"[{job.filename}] Batch {batch_idx + 1}/{job.total_batches} done | "
                    f"Progress: {job.progress}%"
                )

                return True

            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(
                    f"[{job.filename}] Batch {batch_idx + 1} timeout (attempt {attempt + 1})"
                )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Retry on transient errors
                if any(
                    x in error_str
                    for x in ["timeout", "connection", "temporary", "retry"]
                ):
                    logger.warning(
                        f"[{job.filename}] Batch {batch_idx + 1} transient error: {e}"
                    )
                else:
                    # Non-retryable error
                    logger.error(f"[{job.filename}] Batch {batch_idx + 1} failed: {e}")
                    break

        # All retries exhausted
        job.error_message = f"Batch {batch_idx + 1} failed after {self.max_retries + 1} attempts: {last_error}"
        logger.error(f"[{job.filename}] {job.error_message}")
        return False

    def get_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a specific job"""
        job = self._jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "document_id": job.document_id,
            "filename": job.filename,
            "status": job.status.value,
            "progress": job.progress,
            "current_batch": job.current_batch,
            "completed_batches": job.completed_batches,
            "total_batches": job.total_batches,
            "retry_count": job.retry_count,
            "error_message": job.error_message,
        }

    def get_document_status(self, document_id: str) -> Optional[Dict]:
        """Get status by document_id"""
        for job in self._jobs.values():
            if job.document_id == document_id:
                return self.get_status(job.job_id)
        return None

    def get_stats(self) -> Dict:
        """Get processor statistics"""
        by_status = {}
        for status in ProcessingStatus:
            by_status[status.value] = [
                j for j in self._jobs.values() if j.status == status
            ]

        processing_jobs = by_status.get("processing", []) + by_status.get(
            "retrying", []
        )

        return {
            "processing": len(processing_jobs),
            "completed": len(by_status.get("completed", [])),
            "failed": len(by_status.get("failed", [])),
            "total": len(self._jobs),
            "active_tasks": len(self._active_tasks),
            "current_jobs": [
                {
                    "filename": j.filename,
                    "progress": j.progress,
                    "batch": f"{j.current_batch}/{j.total_batches}",
                    "status": j.status.value,
                }
                for j in processing_jobs
            ],
            "config": {
                "max_concurrent_docs": self.max_concurrent_docs,
                "max_concurrent_batches": self.max_concurrent_batches,
                "batch_size": self.batch_size,
                "max_retries": self.max_retries,
            },
        }

    def update_progress(self, job_id: str, completed_batches: int, total_batches: int):
        """Manual progress update (for compatibility)"""
        job = self._jobs.get(job_id)
        if job:
            job.completed_batches = completed_batches
            job.total_batches = total_batches
            job.progress = int((completed_batches / max(1, total_batches)) * 100)

    async def stop(self):
        """Gracefully stop all processing"""
        logger.info("[EmbeddingProcessor] Stopping all tasks...")

        for job_id, task in list(self._active_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._active_tasks.clear()
        logger.info("[EmbeddingProcessor] All tasks stopped")

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Remove old completed/failed jobs"""
        now = datetime.now()
        to_remove = []

        for job_id, job in self._jobs.items():
            if job.status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
                if job.completed_at:
                    age_hours = (now - job.completed_at).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        to_remove.append(job_id)

        for job_id in to_remove:
            del self._jobs[job_id]

        if to_remove:
            logger.info(f"[EmbeddingProcessor] Cleaned up {len(to_remove)} old jobs")


# Singleton instance
_processor: Optional[ParallelEmbeddingProcessor] = None


def get_embedding_processor(
    max_concurrent_docs: int = None,
    max_concurrent_batches: int = None,
    batch_size: int = None,
) -> ParallelEmbeddingProcessor:
    """Get the global embedding processor"""
    global _processor
    if _processor is None:
        _processor = ParallelEmbeddingProcessor(
            max_concurrent_docs=max_concurrent_docs,
            max_concurrent_batches=max_concurrent_batches,
            batch_size=batch_size,
        )
    return _processor


# Backwards compatibility alias
def get_embedding_queue() -> ParallelEmbeddingProcessor:
    """Deprecated: Use get_embedding_processor() instead"""
    return get_embedding_processor()


EmbeddingQueue = ParallelEmbeddingProcessor  # Backwards compatibility
