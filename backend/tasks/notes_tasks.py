"""Batch notes generation background tasks.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

This module contains Celery tasks for generating notes for multiple topics
concurrently, with a concurrency limit of 2 LLM calls and progress tracking.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.celery_app import celery_app
from core.job_manager import BackgroundJobManager, JobStatusEnum
from core.redis_manager import get_redis_manager

logger = logging.getLogger(__name__)

# Max concurrent LLM calls per requirement 9.2
_MAX_LLM_CONCURRENCY = 2


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop.run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


@celery_app.task(
    name="backend.tasks.notes_tasks.generate_batch_notes",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def generate_batch_notes(
    self,
    project_id: str,
    topic_ids: List[str],
    note_types: List[str],
    job_id: str,
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate notes for multiple topics as a background Celery task.

    Processes each (topic, note_type) combination with a concurrency limit
    of 2 simultaneous LLM calls. Progress is updated after each note is saved.

    Args:
        project_id: Project identifier
        topic_ids: List of topic IDs (or topic name strings) to generate notes for
        note_types: Types of notes to generate (e.g. "Comprehensive Summary")
        job_id: Job ID for progress tracking in Redis
        user_id: User who initiated the job (used for saving notes)
        correlation_id: Request correlation ID for tracing

    Returns:
        Dictionary with generation results
    """
    log_prefix = f"[NotesTask job={job_id} project={project_id}]"
    logger.info(
        f"{log_prefix} Starting batch notes generation, "
        f"topics={len(topic_ids)}, note_types={note_types}"
    )

    async def _generate():
        redis_manager = get_redis_manager()
        job_manager = BackgroundJobManager(redis_manager)

        await job_manager.update_job_status(
            job_id,
            status=JobStatusEnum.PROCESSING,
            progress=0,
        )

        # Import services here to avoid circular imports at module load
        from services.notes_service import notes_service
        from db.client import get_supabase_client, async_db

        client = get_supabase_client()

        # Build the full work list: (topic_id, note_type) pairs
        work_items: List[tuple] = [
            (topic_id, note_type)
            for topic_id in topic_ids
            for note_type in note_types
        ]
        total = len(work_items)
        completed_count = 0
        failed_count = 0
        results: List[Dict[str, Any]] = []

        semaphore = asyncio.Semaphore(_MAX_LLM_CONCURRENCY)

        async def _process_one(topic_id: str, note_type: str) -> Dict[str, Any]:
            """Generate and save a single note, respecting the LLM concurrency limit."""
            nonlocal completed_count, failed_count

            # Resolve topic name from Supabase if it looks like a UUID
            topic_name: Optional[str] = None
            if len(topic_id) == 36 and "-" in topic_id:
                try:
                    res = await async_db(
                        lambda: client.table("topics")
                        .select("name")
                        .eq("id", topic_id)
                        .single()
                        .execute()
                    )
                    topic_name = res.data.get("name") if res.data else topic_id
                except Exception:
                    topic_name = topic_id
            else:
                topic_name = topic_id

            async with semaphore:
                logger.debug(f"{log_prefix} Generating '{note_type}' for topic '{topic_name}'")
                try:
                    result = await notes_service.generate_notes(
                        project_id=project_id,
                        note_type=note_type,
                        topic=topic_name or "",
                        user_id=user_id or "",
                    )
                    completed_count += 1
                    progress = int((completed_count / total) * 100)
                    await job_manager.update_job_status(job_id, progress=progress)
                    logger.info(
                        f"{log_prefix} Completed '{note_type}' for '{topic_name}' "
                        f"({completed_count}/{total})"
                    )
                    return {
                        "topic": topic_name,
                        "note_type": note_type,
                        "status": "completed",
                        "note_id": result.get("note_id") if isinstance(result, dict) else None,
                    }
                except Exception as exc:
                    failed_count += 1
                    completed_count += 1  # still advance progress counter
                    progress = int((completed_count / total) * 100)
                    await job_manager.update_job_status(job_id, progress=progress)
                    logger.error(
                        f"{log_prefix} Failed '{note_type}' for '{topic_name}': {exc}"
                    )
                    return {
                        "topic": topic_name,
                        "note_type": note_type,
                        "status": "failed",
                        "error": str(exc),
                    }

        try:
            # Run all work items concurrently, bounded by the semaphore
            tasks = [_process_one(tid, nt) for tid, nt in work_items]
            results = await asyncio.gather(*tasks)

            final_result = {
                "project_id": project_id,
                "total": total,
                "completed": sum(1 for r in results if r["status"] == "completed"),
                "failed": sum(1 for r in results if r["status"] == "failed"),
                "notes": results,
            }

            final_status = (
                JobStatusEnum.COMPLETED if failed_count == 0 else JobStatusEnum.FAILED
            )
            error_msg = (
                f"{failed_count} note(s) failed to generate" if failed_count > 0 else None
            )

            await job_manager.update_job_status(
                job_id,
                status=final_status,
                progress=100,
                result=final_result,
                error_message=error_msg,
            )

            logger.info(
                f"{log_prefix} Batch complete — "
                f"completed={final_result['completed']}, failed={final_result['failed']}"
            )
            return final_result

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"{log_prefix} Task failed: {error_msg}", exc_info=True)
            await job_manager.update_job_status(
                job_id,
                status=JobStatusEnum.FAILED,
                error_message=error_msg,
            )
            raise

    try:
        return _run_async(_generate())
    except Exception as exc:
        logger.error(f"[NotesTask job={job_id}] Retrying due to: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
