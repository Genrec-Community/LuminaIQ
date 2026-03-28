"""Unit tests for BackgroundJobManager.

**Validates: Requirements 7.3, 7.4, 10.1, 10.4, 10.5**
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from core.job_manager import (
    BackgroundJobManager,
    JobType,
    JobStatusEnum,
    JobStatus
)
from core.redis_manager import RedisCacheManager


@pytest.fixture
async def redis_manager():
    """Create a mock RedisCacheManager for testing."""
    manager = MagicMock(spec=RedisCacheManager)
    manager.is_available = True
    manager.set = AsyncMock(return_value=True)
    manager.get = AsyncMock(return_value=None)
    manager.delete = AsyncMock(return_value=True)
    return manager


@pytest.fixture
async def job_manager(redis_manager):
    """Create a BackgroundJobManager instance for testing."""
    return BackgroundJobManager(redis_manager)


@pytest.mark.asyncio
async def test_initialization(redis_manager):
    """Test BackgroundJobManager initialization."""
    manager = BackgroundJobManager(redis_manager)
    
    assert manager.redis_manager == redis_manager
    assert manager.job_ttl == 86400  # 24 hours


@pytest.mark.asyncio
async def test_enqueue_job(job_manager, redis_manager):
    """Test job enqueueing."""
    payload = {"topics": ["topic1", "topic2"]}
    project_id = "proj_123"
    user_id = "user_456"
    
    job_id = await job_manager.enqueue_job(
        job_type=JobType.KNOWLEDGE_GRAPH_BUILD,
        payload=payload,
        project_id=project_id,
        user_id=user_id,
        priority=1
    )
    
    # Verify job_id format
    assert job_id.startswith("job_")
    assert len(job_id) > 10
    
    # Verify Redis set was called
    redis_manager.set.assert_called_once()
    call_args = redis_manager.set.call_args
    
    # Verify key format
    assert call_args[0][0] == f"job:{job_id}"
    
    # Verify job data
    job_data = json.loads(call_args[0][1])
    assert job_data["job_id"] == job_id
    assert job_data["job_type"] == JobType.KNOWLEDGE_GRAPH_BUILD.value
    assert job_data["status"] == JobStatusEnum.PENDING.value
    assert job_data["progress"] == 0
    assert job_data["project_id"] == project_id
    assert job_data["user_id"] == user_id
    assert job_data["metadata"]["payload"] == payload
    assert job_data["metadata"]["priority"] == 1
    
    # Verify TTL
    assert call_args[1]["ttl"] == 86400


@pytest.mark.asyncio
async def test_enqueue_job_redis_failure(job_manager, redis_manager):
    """Test job enqueueing when Redis fails."""
    redis_manager.set.return_value = False
    
    with pytest.raises(RuntimeError, match="Failed to enqueue job"):
        await job_manager.enqueue_job(
            job_type=JobType.BATCH_NOTES_GENERATION,
            payload={},
            project_id="proj_123"
        )


@pytest.mark.asyncio
async def test_get_job_status(job_manager, redis_manager):
    """Test retrieving job status."""
    job_id = "job_abc123"
    job_data = {
        "job_id": job_id,
        "job_type": JobType.KNOWLEDGE_GRAPH_BUILD.value,
        "status": JobStatusEnum.PROCESSING.value,
        "progress": 50,
        "project_id": "proj_123",
        "user_id": "user_456",
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": {}
    }
    
    redis_manager.get.return_value = json.dumps(job_data)
    
    job_status = await job_manager.get_job_status(job_id)
    
    assert job_status is not None
    assert job_status.job_id == job_id
    assert job_status.status == JobStatusEnum.PROCESSING.value
    assert job_status.progress == 50
    assert job_status.project_id == "proj_123"
    
    redis_manager.get.assert_called_once_with(f"job:{job_id}")


@pytest.mark.asyncio
async def test_get_job_status_not_found(job_manager, redis_manager):
    """Test retrieving non-existent job status."""
    redis_manager.get.return_value = None
    
    job_status = await job_manager.get_job_status("job_nonexistent")
    
    assert job_status is None


@pytest.mark.asyncio
async def test_get_job_status_invalid_json(job_manager, redis_manager):
    """Test retrieving job with invalid JSON."""
    redis_manager.get.return_value = "invalid json"
    
    job_status = await job_manager.get_job_status("job_invalid")
    
    assert job_status is None


@pytest.mark.asyncio
async def test_update_job_status(job_manager, redis_manager):
    """Test updating job status."""
    job_id = "job_abc123"
    
    # Mock existing job
    existing_job = JobStatus(
        job_id=job_id,
        job_type=JobType.KNOWLEDGE_GRAPH_BUILD.value,
        status=JobStatusEnum.PENDING.value,
        progress=0,
        project_id="proj_123",
        created_at="2024-01-15T10:00:00Z"
    )
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.KNOWLEDGE_GRAPH_BUILD.value,
        "status": JobStatusEnum.PENDING.value,
        "progress": 0,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": None
    })
    
    # Update to processing
    success = await job_manager.update_job_status(
        job_id,
        status=JobStatusEnum.PROCESSING,
        progress=25
    )
    
    assert success
    
    # Verify Redis set was called
    redis_manager.set.assert_called()
    call_args = redis_manager.set.call_args
    
    updated_data = json.loads(call_args[0][1])
    assert updated_data["status"] == JobStatusEnum.PROCESSING.value
    assert updated_data["progress"] == 25
    assert updated_data["started_at"] is not None


@pytest.mark.asyncio
async def test_update_job_status_to_completed(job_manager, redis_manager):
    """Test updating job status to completed."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.KNOWLEDGE_GRAPH_BUILD.value,
        "status": JobStatusEnum.PROCESSING.value,
        "progress": 50,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": None
    })
    
    result_data = {"nodes": 10, "edges": 15}
    
    success = await job_manager.update_job_status(
        job_id,
        status=JobStatusEnum.COMPLETED,
        progress=100,
        result=result_data
    )
    
    assert success
    
    # Verify completed_at was set
    call_args = redis_manager.set.call_args
    updated_data = json.loads(call_args[0][1])
    assert updated_data["status"] == JobStatusEnum.COMPLETED.value
    assert updated_data["progress"] == 100
    assert updated_data["completed_at"] is not None
    assert updated_data["result"] == result_data


@pytest.mark.asyncio
async def test_update_job_status_to_failed(job_manager, redis_manager):
    """Test updating job status to failed."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.BATCH_NOTES_GENERATION.value,
        "status": JobStatusEnum.PROCESSING.value,
        "progress": 30,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": None
    })
    
    error_msg = "LLM API rate limit exceeded"
    
    success = await job_manager.update_job_status(
        job_id,
        status=JobStatusEnum.FAILED,
        error_message=error_msg
    )
    
    assert success
    
    # Verify error message and completed_at were set
    call_args = redis_manager.set.call_args
    updated_data = json.loads(call_args[0][1])
    assert updated_data["status"] == JobStatusEnum.FAILED.value
    assert updated_data["error_message"] == error_msg
    assert updated_data["completed_at"] is not None


@pytest.mark.asyncio
async def test_update_nonexistent_job(job_manager, redis_manager):
    """Test updating non-existent job."""
    redis_manager.get.return_value = None
    
    success = await job_manager.update_job_status(
        "job_nonexistent",
        status=JobStatusEnum.COMPLETED
    )
    
    assert not success


@pytest.mark.asyncio
async def test_retry_failed_job(job_manager, redis_manager):
    """Test retrying a failed job."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.DOCUMENT_REPROCESSING.value,
        "status": JobStatusEnum.FAILED.value,
        "progress": 50,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": "2024-01-15T10:05:00Z",
        "error_message": "Network timeout",
        "retry_count": 1,
        "result": None,
        "metadata": None
    })
    
    success = await job_manager.retry_failed_job(job_id)
    
    assert success
    
    # Verify job was reset to pending
    call_args = redis_manager.set.call_args
    updated_data = json.loads(call_args[0][1])
    assert updated_data["status"] == JobStatusEnum.PENDING.value
    assert updated_data["retry_count"] == 2
    assert updated_data["error_message"] is None
    assert updated_data["started_at"] is None
    assert updated_data["completed_at"] is None


@pytest.mark.asyncio
async def test_retry_non_failed_job(job_manager, redis_manager):
    """Test retrying a job that hasn't failed."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.KNOWLEDGE_GRAPH_BUILD.value,
        "status": JobStatusEnum.PROCESSING.value,
        "progress": 50,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": None
    })
    
    success = await job_manager.retry_failed_job(job_id)
    
    assert not success


@pytest.mark.asyncio
async def test_cancel_job(job_manager, redis_manager):
    """Test cancelling a pending job."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.BATCH_NOTES_GENERATION.value,
        "status": JobStatusEnum.PENDING.value,
        "progress": 0,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "retry_count": 0,
        "result": None,
        "metadata": None
    })
    
    success = await job_manager.cancel_job(job_id)
    
    assert success
    
    # Verify job was marked as failed with cancellation message
    call_args = redis_manager.set.call_args
    updated_data = json.loads(call_args[0][1])
    assert updated_data["status"] == JobStatusEnum.FAILED.value
    assert "cancelled" in updated_data["error_message"].lower()


@pytest.mark.asyncio
async def test_cancel_completed_job(job_manager, redis_manager):
    """Test cancelling a completed job (should fail)."""
    job_id = "job_abc123"
    
    redis_manager.get.return_value = json.dumps({
        "job_id": job_id,
        "job_type": JobType.KNOWLEDGE_GRAPH_BUILD.value,
        "status": JobStatusEnum.COMPLETED.value,
        "progress": 100,
        "project_id": "proj_123",
        "user_id": None,
        "created_at": "2024-01-15T10:00:00Z",
        "started_at": "2024-01-15T10:01:00Z",
        "completed_at": "2024-01-15T10:05:00Z",
        "error_message": None,
        "retry_count": 0,
        "result": {},
        "metadata": None
    })
    
    success = await job_manager.cancel_job(job_id)
    
    assert not success


@pytest.mark.asyncio
async def test_job_ttl_24_hours(job_manager):
    """Test that jobs have 24-hour TTL (Requirement 10.5)."""
    assert job_manager.job_ttl == 86400  # 24 hours in seconds


@pytest.mark.asyncio
async def test_job_metadata_storage(job_manager, redis_manager):
    """Test that all required job metadata is stored (Requirement 7.3)."""
    payload = {"test": "data"}
    project_id = "proj_123"
    
    job_id = await job_manager.enqueue_job(
        job_type=JobType.CACHE_WARMING,
        payload=payload,
        project_id=project_id
    )
    
    call_args = redis_manager.set.call_args
    job_data = json.loads(call_args[0][1])
    
    # Verify all required metadata fields are present
    required_fields = [
        "job_id", "job_type", "status", "progress",
        "project_id", "created_at"
    ]
    
    for field in required_fields:
        assert field in job_data, f"Missing required field: {field}"
