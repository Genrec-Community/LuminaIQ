"""Knowledge graph generation background tasks.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 21.4**

This module contains Celery tasks for building and updating knowledge graphs
from extracted topics, with progress tracking and distributed locking.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from core.celery_app import celery_app
from core.job_manager import BackgroundJobManager, JobStatusEnum
from core.redis_manager import get_redis_manager
from core.lock_manager import DistributedLockManager
from utils.logger import set_correlation_id, clear_correlation_id

logger = logging.getLogger(__name__)

# Progress milestones (percentage)
_PROGRESS_FETCH_TOPICS = 10
_PROGRESS_LOCK_ACQUIRED = 15
_PROGRESS_BATCH_START = 20
_PROGRESS_BATCH_END = 90
_PROGRESS_STORE = 95
_PROGRESS_DONE = 100


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
    name="backend.tasks.knowledge_graph_tasks.build_knowledge_graph",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def build_knowledge_graph(
    self,
    project_id: str,
    topics: List[str],
    job_id: str,
    force_rebuild: bool = False,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build knowledge graph from topics as a background Celery task.

    Acquires a distributed lock for the project to prevent concurrent builds.
    Updates job progress in Redis every ~10%.

    Args:
        project_id: Project identifier
        topics: List of topic names to build graph from
        job_id: Job ID for progress tracking in Redis
        force_rebuild: Whether to rebuild an existing graph
        correlation_id: Request correlation ID for tracing

    Returns:
        Dictionary with graph statistics (nodes, edges)
    """
    log_prefix = f"[KGTask job={job_id} project={project_id}]"
    logger.info(f"{log_prefix} Starting knowledge graph build, topics={len(topics)}, force_rebuild={force_rebuild}")

    # Propagate correlation_id into the logger ContextVar for this task (Requirement 21.4)
    if correlation_id:
        set_correlation_id(correlation_id)

    async def _build():
        redis_manager = get_redis_manager()
        job_manager = BackgroundJobManager(redis_manager)
        lock_manager = DistributedLockManager(redis_manager)

        # Mark job as processing
        await job_manager.update_job_status(
            job_id,
            status=JobStatusEnum.PROCESSING,
            progress=0,
        )

        lock_resource = f"kg_build:{project_id}"
        lock_token: Optional[str] = None

        try:
            # Acquire distributed lock (5-second timeout, 5-minute TTL)
            lock_token = await lock_manager.acquire_lock(lock_resource, timeout=5, ttl=300)
            if lock_token is None:
                raise RuntimeError(
                    f"Knowledge graph build already in progress for project {project_id}"
                )

            await job_manager.update_job_status(job_id, progress=_PROGRESS_LOCK_ACQUIRED)
            logger.info(f"{log_prefix} Distributed lock acquired")

            # Import here to avoid circular imports at module load time
            from services.knowledge_graph_service import KnowledgeGraph

            kg = KnowledgeGraph()

            # Fetch existing topics from Supabase if none provided
            if not topics:
                from db.client import async_db
                from db.client import get_supabase_client
                client = get_supabase_client()
                result = await async_db(
                    lambda: client.table("documents")
                    .select("topics")
                    .eq("project_id", project_id)
                    .eq("upload_status", "completed")
                    .execute()
                )
                all_topics: List[str] = []
                for doc in result.data or []:
                    all_topics.extend(doc.get("topics") or [])
                topics_to_use = list(set(all_topics))
            else:
                topics_to_use = topics

            await job_manager.update_job_status(job_id, progress=_PROGRESS_FETCH_TOPICS)
            logger.info(f"{log_prefix} Topics resolved: {len(topics_to_use)}")

            if len(topics_to_use) < 2:
                result_data = {"edges_created": 0, "message": "Need at least 2 topics"}
                await job_manager.update_job_status(
                    job_id,
                    status=JobStatusEnum.COMPLETED,
                    progress=_PROGRESS_DONE,
                    result=result_data,
                )
                return result_data

            # Build graph — the service handles batching internally.
            # We hook into progress by wrapping the call with pre/post updates.
            await job_manager.update_job_status(job_id, progress=_PROGRESS_BATCH_START)

            graph_result = await kg.build_graph_from_topics(
                project_id=project_id,
                topics=topics_to_use,
                force_rebuild=force_rebuild,
            )

            await job_manager.update_job_status(job_id, progress=_PROGRESS_STORE)
            logger.info(f"{log_prefix} Graph built: {graph_result}")

            await job_manager.update_job_status(
                job_id,
                status=JobStatusEnum.COMPLETED,
                progress=_PROGRESS_DONE,
                result=graph_result,
            )

            return graph_result

        except Exception as exc:
            error_msg = str(exc)
            logger.error(f"{log_prefix} Task failed: {error_msg}", exc_info=True)
            await job_manager.update_job_status(
                job_id,
                status=JobStatusEnum.FAILED,
                error_message=error_msg,
            )
            raise

        finally:
            if lock_token:
                await lock_manager.release_lock(lock_resource, lock_token)
                logger.info(f"{log_prefix} Distributed lock released")

    try:
        return _run_async(_build())
    except Exception as exc:
        logger.error(f"{log_prefix} Retrying due to: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    finally:
        if correlation_id:
            clear_correlation_id()
