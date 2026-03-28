"""
Unit tests for custom metrics tracking.

**Validates: Requirements 20.3**

Tests the custom metrics tracking functionality for:
- Cache hit rate
- Job queue length
- Embedding throughput
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.telemetry import TelemetryService


class TestCustomMetricsTracking:
    """Test custom metrics tracking methods."""
    
    @pytest.fixture
    def mock_telemetry_service(self):
        """Create a mock telemetry service with enabled state."""
        service = TelemetryService(connection_string=None)
        service.enabled = True
        service.meter = Mock()
        return service
    
    def test_track_cache_hit_rate(self, mock_telemetry_service):
        """Test cache hit rate tracking."""
        # Create mock gauge
        mock_gauge = Mock()
        mock_telemetry_service.meter.create_gauge = Mock(return_value=mock_gauge)
        
        # Track cache hit rate
        mock_telemetry_service.track_cache_hit_rate(
            hit_rate=85.5,
            cache_type="embedding",
            properties={"total_requests": 1000}
        )
        
        # Verify gauge was created
        mock_telemetry_service.meter.create_gauge.assert_called_once_with(
            name="cache.hit_rate",
            description="Cache hit rate percentage",
            unit="%"
        )
        
        # Verify gauge was set with correct value and attributes
        mock_gauge.set.assert_called_once()
        call_args = mock_gauge.set.call_args
        assert call_args[0][0] == 85.5  # hit_rate value
        assert call_args[1]["attributes"]["cache_type"] == "embedding"
        assert call_args[1]["attributes"]["total_requests"] == "1000"
    
    def test_track_job_queue_length(self, mock_telemetry_service):
        """Test job queue length tracking."""
        # Create mock up-down counter
        mock_counter = Mock()
        mock_telemetry_service.job_queue_length = mock_counter
        
        # Track queue length
        mock_telemetry_service.track_job_queue_length(
            queue_length=5,
            job_type="KNOWLEDGE_GRAPH_BUILD",
            properties={"project_id": "proj_123"}
        )
        
        # Verify counter was updated
        mock_counter.add.assert_called_once()
        call_args = mock_counter.add.call_args
        assert call_args[0][0] == 5  # queue_length value
        assert call_args[1]["attributes"]["job_type"] == "KNOWLEDGE_GRAPH_BUILD"
        assert call_args[1]["attributes"]["project_id"] == "proj_123"
    
    def test_track_embedding_throughput(self, mock_telemetry_service):
        """Test embedding throughput tracking."""
        # Create mock histogram
        mock_histogram = Mock()
        mock_telemetry_service.meter.create_histogram = Mock(return_value=mock_histogram)
        
        # Track embedding throughput
        mock_telemetry_service.track_embedding_throughput(
            embeddings_per_second=125.5,
            batch_size=50,
            properties={
                "model": "text-embedding-3-small",
                "cache_hit_rate": "80.0"
            }
        )
        
        # Verify histogram was created
        mock_telemetry_service.meter.create_histogram.assert_called_once_with(
            name="embedding.throughput",
            description="Embedding generation throughput (embeddings per second)",
            unit="embeddings/s"
        )
        
        # Verify histogram recorded value
        mock_histogram.record.assert_called_once()
        call_args = mock_histogram.record.call_args
        assert call_args[0][0] == 125.5  # embeddings_per_second value
        assert call_args[1]["attributes"]["batch_size"] == "50"
        assert call_args[1]["attributes"]["model"] == "text-embedding-3-small"
        assert call_args[1]["attributes"]["cache_hit_rate"] == "80.0"
    
    def test_track_cache_hit_rate_disabled(self):
        """Test cache hit rate tracking when telemetry is disabled."""
        service = TelemetryService(connection_string=None)
        service.enabled = False
        
        # Should not raise exception
        service.track_cache_hit_rate(hit_rate=85.5, cache_type="embedding")
    
    def test_track_job_queue_length_disabled(self):
        """Test job queue length tracking when telemetry is disabled."""
        service = TelemetryService(connection_string=None)
        service.enabled = False
        
        # Should not raise exception
        service.track_job_queue_length(queue_length=5)
    
    def test_track_embedding_throughput_disabled(self):
        """Test embedding throughput tracking when telemetry is disabled."""
        service = TelemetryService(connection_string=None)
        service.enabled = False
        
        # Should not raise exception
        service.track_embedding_throughput(
            embeddings_per_second=125.5,
            batch_size=50
        )


class TestRedisCacheManagerMetrics:
    """Test Redis cache manager metrics integration."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_rate_tracking_every_100_requests(self):
        """Test that cache hit rate is tracked every 100 requests."""
        from core.redis_manager import RedisCacheManager
        from unittest.mock import AsyncMock
        
        # Create manager
        manager = RedisCacheManager(
            host="localhost",
            port=6379,
            password="test",
        )
        
        # Mock telemetry
        mock_telemetry = Mock()
        manager._telemetry = mock_telemetry
        
        # Mock Redis client
        manager._client = Mock()
        manager._client.get = AsyncMock(return_value=None)
        manager._is_available = True
        
        # Simulate 99 requests (should not track)
        manager._stats["total_requests"] = 98
        
        await manager.get("test_key")
        
        # Should not have tracked yet (99 requests)
        mock_telemetry.track_cache_hit_rate.assert_not_called()
        
        # One more request to reach 100 (should track)
        await manager.get("test_key")
        
        # Should have tracked now (100 requests)
        assert mock_telemetry.track_cache_hit_rate.called
        # Should track overall + per-type metrics
        assert mock_telemetry.track_cache_hit_rate.call_count >= 1


class TestBackgroundJobManagerMetrics:
    """Test background job manager metrics integration."""
    
    @pytest.mark.asyncio
    async def test_job_queue_length_tracking_on_enqueue(self):
        """Test that job queue length is tracked when jobs are enqueued."""
        from core.job_manager import BackgroundJobManager, JobType
        from core.redis_manager import RedisCacheManager
        from unittest.mock import AsyncMock
        
        # Create mock Redis manager
        mock_redis = Mock(spec=RedisCacheManager)
        mock_redis.set = AsyncMock(return_value=True)
        
        # Create job manager
        manager = BackgroundJobManager(redis_manager=mock_redis)
        
        # Mock telemetry
        mock_telemetry = Mock()
        manager._telemetry = mock_telemetry
        
        # Enqueue a job
        await manager.enqueue_job(
            job_type=JobType.KNOWLEDGE_GRAPH_BUILD,
            payload={"test": "data"},
            project_id="proj_123"
        )
        
        # Verify queue length was tracked
        mock_telemetry.track_job_queue_length.assert_called_once()
        call_args = mock_telemetry.track_job_queue_length.call_args
        assert call_args[1]["queue_length"] == 1


class TestEmbeddingServiceMetrics:
    """Test embedding service metrics integration."""
    
    @pytest.mark.asyncio
    async def test_embedding_throughput_tracking(self):
        """Test that embedding throughput is tracked after batch operations."""
        from services.embedding_service import EmbeddingService
        from unittest.mock import AsyncMock
        
        # Mock the entire embeddings object before creating service
        with patch('services.embedding_service.OpenAIEmbeddings') as MockEmbeddings:
            mock_embeddings_instance = Mock()
            mock_embeddings_instance.aembed_documents = AsyncMock(
                return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            )
            MockEmbeddings.return_value = mock_embeddings_instance
            
            # Create service
            service = EmbeddingService(redis_manager=None)
            
            # Mock telemetry
            mock_telemetry = Mock()
            service._telemetry = mock_telemetry
            
            # Generate embeddings
            texts = ["text1", "text2"]
            await service.generate_embeddings(texts)
            
            # Verify throughput was tracked
            mock_telemetry.track_embedding_throughput.assert_called_once()
            call_args = mock_telemetry.track_embedding_throughput.call_args
            assert call_args[1]["batch_size"] == 2
            assert call_args[1]["embeddings_per_second"] > 0
