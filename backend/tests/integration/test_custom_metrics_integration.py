"""
Integration tests for custom metrics tracking.

**Validates: Requirements 20.3**

Tests the end-to-end custom metrics tracking functionality.
"""

import pytest
from unittest.mock import Mock, patch


class TestCustomMetricsIntegration:
    """Integration tests for custom metrics tracking."""
    
    def test_telemetry_service_has_custom_metrics_methods(self):
        """Verify TelemetryService has all required custom metrics methods."""
        from core.telemetry import TelemetryService
        
        service = TelemetryService(connection_string=None)
        
        # Verify methods exist
        assert hasattr(service, 'track_cache_hit_rate')
        assert hasattr(service, 'track_job_queue_length')
        assert hasattr(service, 'track_embedding_throughput')
        
        # Verify methods are callable
        assert callable(service.track_cache_hit_rate)
        assert callable(service.track_job_queue_length)
        assert callable(service.track_embedding_throughput)
    
    def test_redis_manager_has_telemetry_integration(self):
        """Verify RedisCacheManager integrates with telemetry."""
        from core.redis_manager import RedisCacheManager
        
        manager = RedisCacheManager(
            host="localhost",
            port=6379,
            password="test"
        )
        
        # Verify telemetry integration methods exist
        assert hasattr(manager, '_get_telemetry')
        assert hasattr(manager, '_track_cache_hit_rate_telemetry')
        assert callable(manager._get_telemetry)
        assert callable(manager._track_cache_hit_rate_telemetry)
    
    def test_job_manager_has_telemetry_integration(self):
        """Verify BackgroundJobManager integrates with telemetry."""
        from core.job_manager import BackgroundJobManager
        from core.redis_manager import RedisCacheManager
        
        mock_redis = Mock(spec=RedisCacheManager)
        manager = BackgroundJobManager(redis_manager=mock_redis)
        
        # Verify telemetry integration methods exist
        assert hasattr(manager, '_get_telemetry')
        assert hasattr(manager, '_track_job_queue_length')
        assert hasattr(manager, '_queue_length')
        assert callable(manager._get_telemetry)
        assert callable(manager._track_job_queue_length)
    
    def test_embedding_service_has_telemetry_integration(self):
        """Verify EmbeddingService integrates with telemetry."""
        from services.embedding_service import EmbeddingService
        
        service = EmbeddingService(redis_manager=None)
        
        # Verify telemetry integration methods exist
        assert hasattr(service, '_get_telemetry')
        assert hasattr(service, '_track_embedding_throughput')
        assert callable(service._get_telemetry)
        assert callable(service._track_embedding_throughput)
    
    def test_custom_metrics_graceful_degradation(self):
        """Test that custom metrics work gracefully when telemetry is disabled."""
        from core.telemetry import TelemetryService
        
        # Create disabled service
        service = TelemetryService(connection_string=None)
        service.enabled = False
        
        # Should not raise exceptions
        service.track_cache_hit_rate(hit_rate=85.5, cache_type="embedding")
        service.track_job_queue_length(queue_length=5)
        service.track_embedding_throughput(embeddings_per_second=125.5, batch_size=50)
    
    def test_custom_metrics_with_properties(self):
        """Test that custom metrics accept and handle properties correctly."""
        from core.telemetry import TelemetryService
        
        service = TelemetryService(connection_string=None)
        service.enabled = True
        service.meter = Mock()
        
        # Mock gauge and histogram
        mock_gauge = Mock()
        mock_histogram = Mock()
        service.meter.create_gauge = Mock(return_value=mock_gauge)
        service.meter.create_histogram = Mock(return_value=mock_histogram)
        service.job_queue_length = Mock()
        
        # Track with properties
        service.track_cache_hit_rate(
            hit_rate=85.5,
            cache_type="embedding",
            properties={"project_id": "proj_123", "user_id": "user_456"}
        )
        
        service.track_job_queue_length(
            queue_length=5,
            job_type="KNOWLEDGE_GRAPH_BUILD",
            properties={"project_id": "proj_123"}
        )
        
        service.track_embedding_throughput(
            embeddings_per_second=125.5,
            batch_size=50,
            properties={"model": "text-embedding-3-small", "cache_hit_rate": "80.0"}
        )
        
        # Verify all methods were called
        assert mock_gauge.set.called
        assert service.job_queue_length.add.called
        assert mock_histogram.record.called
