"""Celery application configuration for background job processing.

**Validates: Requirements 7.1, 7.2, 7.5**

This module configures Celery with Redis as broker and result backend for
persistent, distributed background job processing.
"""

import logging
from celery import Celery
from kombu import Exchange, Queue

from config.settings import settings

logger = logging.getLogger(__name__)


# Create Celery application
celery_app = Celery(
    "lumina_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.tasks.document_tasks",
        "backend.tasks.knowledge_graph_tasks",
        "backend.tasks.notes_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Worker settings
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,  # 3 concurrent workers
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)
    
    # Task timeout settings
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,  # 10 minutes hard limit
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,  # 9 minutes soft limit
    
    # Retry settings
    task_acks_late=True,  # Acknowledge task after completion (not before)
    task_reject_on_worker_lost=True,  # Reject task if worker crashes
    task_default_retry_delay=2,  # 2 seconds initial retry delay
    task_max_retries=settings.CELERY_MAX_RETRIES,  # 3 retries
    
    # Result backend settings
    result_expires=86400,  # Results expire after 24 hours
    result_persistent=True,  # Persist results to Redis
    
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Task routing
    task_routes={
        "backend.tasks.document_tasks.*": {"queue": "documents"},
        "backend.tasks.knowledge_graph_tasks.*": {"queue": "knowledge_graph"},
        "backend.tasks.notes_tasks.*": {"queue": "notes"},
    },
    
    # Queue definitions
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("documents", Exchange("documents"), routing_key="documents"),
        Queue("knowledge_graph", Exchange("knowledge_graph"), routing_key="knowledge_graph"),
        Queue("notes", Exchange("notes"), routing_key="notes"),
    ),
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat scheduler (for periodic tasks)
    beat_schedule={
        # Example: Clean up old job records every hour
        "cleanup-old-jobs": {
            "task": "backend.tasks.maintenance_tasks.cleanup_old_jobs",
            "schedule": 3600.0,  # Every hour
        },
    },
)


# Task base class with common functionality
class BaseTask(celery_app.Task):
    """
    Base task class with common error handling and logging.
    """
    
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": settings.CELERY_MAX_RETRIES}
    retry_backoff = settings.CELERY_RETRY_BACKOFF  # Exponential backoff
    retry_backoff_max = 60  # Max 60 seconds between retries
    retry_jitter = True  # Add random jitter to prevent thundering herd
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries.
        
        Args:
            exc: Exception that caused failure
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        logger.error(
            f"[Celery] Task {self.name} failed after all retries: "
            f"task_id={task_id}, error={exc}",
            exc_info=einfo
        )
        
        # TODO: Send alert notification
        # TODO: Update job status in Redis/Supabase
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task is retried.
        
        Args:
            exc: Exception that caused retry
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
            einfo: Exception info
        """
        logger.warning(
            f"[Celery] Task {self.name} retrying: "
            f"task_id={task_id}, retry={self.request.retries}, error={exc}"
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """
        Called when task succeeds.
        
        Args:
            retval: Task return value
            task_id: Task ID
            args: Task positional arguments
            kwargs: Task keyword arguments
        """
        logger.info(
            f"[Celery] Task {self.name} completed successfully: "
            f"task_id={task_id}"
        )


# Set default task base class
celery_app.Task = BaseTask


# Startup logging
logger.info(
    f"[Celery] Application configured with broker={settings.CELERY_BROKER_URL}, "
    f"concurrency={settings.CELERY_WORKER_CONCURRENCY}, "
    f"task_time_limit={settings.CELERY_TASK_TIME_LIMIT}s"
)


# Example task for testing
@celery_app.task(name="backend.tasks.test_task")
def test_task(message: str) -> str:
    """
    Test task for verifying Celery setup.
    
    Args:
        message: Test message
        
    Returns:
        Echo of the message
    """
    logger.info(f"[Celery] Test task executed with message: {message}")
    return f"Echo: {message}"
