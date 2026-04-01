"""Unit tests for correlation ID propagation to background jobs.

**Validates: Requirement 21.4**

Tests cover:
- correlation_id stored in job metadata when enqueuing
- dispatch_celery_task passes correlation_id in headers AND kwargs
- BaseTask.__call__ sets the logger ContextVar from task headers
- BaseTask.__call__ sets the logger ContextVar from task kwargs (fallback)
- BaseTask.__call__ clears the ContextVar after task execution
- Task functions (build_knowledge_graph, generate_batch_notes, reprocess_document)
  accept and propagate correlation_id
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from core.job_manager import BackgroundJobManager, JobType, JobStatusEnum
from core.redis_manager import RedisCacheManager
from utils.logger import clear_correlation_id, get_correlation_id, set_correlation_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_manager():
    manager = MagicMock(spec=RedisCacheManager)
    manager.is_available = True
    manager.set = AsyncMock(return_value=True)
    manager.get = AsyncMock(return_value=None)
    manager.delete = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def job_manager(redis_manager):
    return BackgroundJobManager(redis_manager)


# ---------------------------------------------------------------------------
# enqueue_job — correlation_id stored in metadata
# ---------------------------------------------------------------------------


class TestEnqueueJobCorrelationID:
    """Verify correlation_id is persisted in job metadata when enqueuing."""

    @pytest.mark.asyncio
    async def test_correlation_id_stored_in_metadata(self, job_manager, redis_manager):
        """correlation_id must be saved in job metadata (Requirement 21.4)."""
        correlation_id = "req-trace-abc123"

        job_id = await job_manager.enqueue_job(
            job_type=JobType.KNOWLEDGE_GRAPH_BUILD,
            payload={"topics": ["topic1"]},
            project_id="proj_1",
            correlation_id=correlation_id,
        )

        call_args = redis_manager.set.call_args
        job_data = json.loads(call_args[0][1])

        assert job_data["metadata"]["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_none_correlation_id_stored(self, job_manager, redis_manager):
        """None correlation_id must be stored without error."""
        job_id = await job_manager.enqueue_job(
            job_type=JobType.BATCH_NOTES_GENERATION,
            payload={},
            project_id="proj_2",
            correlation_id=None,
        )

        call_args = redis_manager.set.call_args
        job_data = json.loads(call_args[0][1])

        assert job_data["metadata"]["correlation_id"] is None


# ---------------------------------------------------------------------------
# dispatch_celery_task — headers and kwargs
# ---------------------------------------------------------------------------


class TestDispatchCeleryTask:
    """Verify dispatch_celery_task propagates correlation_id correctly."""

    def test_correlation_id_in_headers(self, job_manager):
        """correlation_id must be passed in Celery task headers."""
        correlation_id = "trace-xyz-789"

        with patch("core.celery_app.celery_app") as mock_celery:
            job_manager.dispatch_celery_task(
                task_name="backend.tasks.knowledge_graph_tasks.build_knowledge_graph",
                args=["proj_1", ["topic1"]],
                kwargs={"job_id": "job_001"},
                job_id="job_001",
                correlation_id=correlation_id,
            )

            mock_celery.send_task.assert_called_once()
            _, send_kwargs = mock_celery.send_task.call_args
            assert send_kwargs["headers"]["correlation_id"] == correlation_id

    def test_correlation_id_in_kwargs_fallback(self, job_manager):
        """correlation_id must also be injected into task kwargs as fallback."""
        correlation_id = "trace-fallback-456"

        with patch("core.celery_app.celery_app") as mock_celery:
            job_manager.dispatch_celery_task(
                task_name="backend.tasks.notes_tasks.generate_batch_notes",
                args=[],
                kwargs={"job_id": "job_002"},
                job_id="job_002",
                correlation_id=correlation_id,
            )

            _, send_kwargs = mock_celery.send_task.call_args
            assert send_kwargs["kwargs"]["correlation_id"] == correlation_id

    def test_no_correlation_id_sends_empty_headers(self, job_manager):
        """When correlation_id is None, headers dict must be empty."""
        with patch("core.celery_app.celery_app") as mock_celery:
            job_manager.dispatch_celery_task(
                task_name="backend.tasks.document_tasks.reprocess_document",
                args=[],
                kwargs={"job_id": "job_003"},
                job_id="job_003",
                correlation_id=None,
            )

            _, send_kwargs = mock_celery.send_task.call_args
            assert send_kwargs["headers"] == {}

    def test_job_id_used_as_celery_task_id(self, job_manager):
        """job_id must be forwarded as the Celery task_id for correlation."""
        with patch("core.celery_app.celery_app") as mock_celery:
            job_manager.dispatch_celery_task(
                task_name="backend.tasks.knowledge_graph_tasks.build_knowledge_graph",
                args=[],
                kwargs={},
                job_id="job_unique_id",
                correlation_id="some-trace",
            )

            _, send_kwargs = mock_celery.send_task.call_args
            assert send_kwargs["task_id"] == "job_unique_id"

    def test_existing_correlation_id_kwarg_not_overwritten(self, job_manager):
        """If caller already set correlation_id in kwargs, it must not be overwritten."""
        with patch("core.celery_app.celery_app") as mock_celery:
            job_manager.dispatch_celery_task(
                task_name="backend.tasks.notes_tasks.generate_batch_notes",
                args=[],
                kwargs={"correlation_id": "caller-set-id"},
                job_id="job_004",
                correlation_id="manager-set-id",
            )

            _, send_kwargs = mock_celery.send_task.call_args
            # setdefault must not overwrite the caller-provided value
            assert send_kwargs["kwargs"]["correlation_id"] == "caller-set-id"


# ---------------------------------------------------------------------------
# BaseTask — ContextVar lifecycle
# ---------------------------------------------------------------------------


class TestBaseTaskCorrelationIDLifecycle:
    """Verify BaseTask sets and clears the logger ContextVar around task execution."""

    def test_get_correlation_id_from_headers(self):
        """_get_correlation_id must read from request.headers first."""
        from core.celery_app import BaseTask, celery_app

        @celery_app.task(base=BaseTask, name="test.task.get_corr_headers")
        def _task():
            pass

        # Push a fake request with headers onto the request stack
        fake_req = MagicMock()
        fake_req.headers = {"correlation_id": "from-headers"}
        fake_req.kwargs = {}
        _task.request_stack.push(fake_req)
        try:
            result = _task._get_correlation_id()
        finally:
            _task.request_stack.pop()

        assert result == "from-headers"

    def test_get_correlation_id_from_kwargs_fallback(self):
        """_get_correlation_id must fall back to kwargs when headers absent."""
        from core.celery_app import BaseTask, celery_app

        @celery_app.task(base=BaseTask, name="test.task.get_corr_kwargs")
        def _task():
            pass

        fake_req = MagicMock()
        fake_req.headers = {}
        fake_req.kwargs = {"correlation_id": "from-kwargs"}
        _task.request_stack.push(fake_req)
        try:
            result = _task._get_correlation_id()
        finally:
            _task.request_stack.pop()

        assert result == "from-kwargs"

    def test_get_correlation_id_returns_none_when_absent(self):
        """_get_correlation_id must return None when no correlation_id present."""
        from core.celery_app import BaseTask, celery_app

        @celery_app.task(base=BaseTask, name="test.task.get_corr_none")
        def _task():
            pass

        fake_req = MagicMock()
        fake_req.headers = {}
        fake_req.kwargs = {}
        _task.request_stack.push(fake_req)
        try:
            result = _task._get_correlation_id()
        finally:
            _task.request_stack.pop()

        assert result is None

    def test_correlation_id_set_and_cleared_via_call(self):
        """BaseTask.__call__ must set ContextVar during execution and clear it after."""
        from core.celery_app import BaseTask, celery_app

        captured = {}

        @celery_app.task(base=BaseTask, name="test.task.call_lifecycle")
        def _task():
            captured["during"] = get_correlation_id()
            return "ok"

        clear_correlation_id()

        fake_req = MagicMock()
        fake_req.headers = {"correlation_id": "lifecycle-id"}
        fake_req.kwargs = {}
        _task.request_stack.push(fake_req)
        try:
            _task.__call__()
        finally:
            _task.request_stack.pop()

        assert captured.get("during") == "lifecycle-id"
        assert get_correlation_id() is None  # cleared after task


# ---------------------------------------------------------------------------
# Task functions — accept correlation_id parameter
# ---------------------------------------------------------------------------


class TestTaskFunctionCorrelationIDParam:
    """Verify task functions accept correlation_id and call set_correlation_id."""

    def test_build_knowledge_graph_accepts_correlation_id(self):
        """build_knowledge_graph must accept correlation_id kwarg without error."""
        import inspect
        from tasks.knowledge_graph_tasks import build_knowledge_graph

        sig = inspect.signature(build_knowledge_graph.run)
        assert "correlation_id" in sig.parameters

    def test_generate_batch_notes_accepts_correlation_id(self):
        """generate_batch_notes must accept correlation_id kwarg without error."""
        import inspect
        from tasks.notes_tasks import generate_batch_notes

        sig = inspect.signature(generate_batch_notes.run)
        assert "correlation_id" in sig.parameters

    def test_reprocess_document_accepts_correlation_id(self):
        """reprocess_document must accept correlation_id kwarg without error."""
        import inspect
        from tasks.document_tasks import reprocess_document

        sig = inspect.signature(reprocess_document.run)
        assert "correlation_id" in sig.parameters

    def test_process_document_accepts_correlation_id(self):
        """process_document must accept correlation_id kwarg without error."""
        import inspect
        from tasks.document_tasks import process_document

        sig = inspect.signature(process_document.run)
        assert "correlation_id" in sig.parameters

    @patch("tasks.knowledge_graph_tasks.set_correlation_id")
    @patch("tasks.knowledge_graph_tasks._run_async", return_value={"edges_created": 0})
    def test_build_knowledge_graph_calls_set_correlation_id(
        self, mock_run_async, mock_set_corr
    ):
        """build_knowledge_graph must call set_correlation_id when correlation_id provided."""
        from tasks.knowledge_graph_tasks import build_knowledge_graph

        build_knowledge_graph.run(
            project_id="proj_1",
            topics=["t1", "t2"],
            job_id="job_1",
            correlation_id="trace-kg-001",
        )

        mock_set_corr.assert_called_once_with("trace-kg-001")

    @patch("tasks.notes_tasks.set_correlation_id")
    @patch("tasks.notes_tasks._run_async", return_value={"total": 0})
    def test_generate_batch_notes_calls_set_correlation_id(
        self, mock_run_async, mock_set_corr
    ):
        """generate_batch_notes must call set_correlation_id when correlation_id provided."""
        from tasks.notes_tasks import generate_batch_notes

        generate_batch_notes.run(
            project_id="proj_1",
            topic_ids=["t1"],
            note_types=["summary"],
            job_id="job_2",
            correlation_id="trace-notes-002",
        )

        mock_set_corr.assert_called_once_with("trace-notes-002")

    @patch("tasks.document_tasks.set_correlation_id")
    @patch("tasks.document_tasks._run_async", return_value={"status": "completed"})
    def test_reprocess_document_calls_set_correlation_id(
        self, mock_run_async, mock_set_corr
    ):
        """reprocess_document must call set_correlation_id when correlation_id provided."""
        from tasks.document_tasks import reprocess_document

        reprocess_document.run(
            document_id="doc_1",
            job_id="job_3",
            correlation_id="trace-doc-003",
        )

        mock_set_corr.assert_called_once_with("trace-doc-003")
