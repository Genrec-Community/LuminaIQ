"""
Unit tests for dependency telemetry tracking.

Tests verify that external service calls (Redis, Supabase, Qdrant, LLM API)
are properly tracked with telemetry including operation name, duration,
success status, and relevant properties.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from core.redis_manager import RedisCacheManager
from services.qdrant_service import QdrantService
from services.llm_service import LLMService
from db.client import async_db


class TestRedisTelemetry:
    """Test Redis operations track telemetry correctly."""
    
    @pytest.mark.asyncio
    async def test_redis_get_tracks_telemetry(self):
        """Test that Redis GET operation tracks telemetry."""
        # Create Redis manager
        redis_manager = RedisCacheManager(
            host="localhost",
            port=6379,
            password="test",
            retry_attempts=1
        )
        
        # Mock telemetry service
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        redis_manager._telemetry = mock_telemetry
        
        # Mock Redis client
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value="test_value")
        redis_manager._client = mock_client
        redis_manager._is_available = True
        
        # Execute GET operation
        result = await redis_manager.get("test_key")
        
        # Verify telemetry was tracked
        assert mock_telemetry.track_dependency.called
        call_args = mock_telemetry.track_dependency.call_args
        assert call_args[1]["name"] == "Redis GET"
        assert call_args[1]["dependency_type"] == "redis"
        assert call_args[1]["success"] is True
        assert "operation" in call_args[1]["properties"]
        assert call_args[1]["properties"]["operation"] == "GET"
    
    @pytest.mark.asyncio
    async def test_redis_set_tracks_telemetry(self):
        """Test that Redis SET operation tracks telemetry."""
        redis_manager = RedisCacheManager(
            host="localhost",
            port=6379,
            password="test",
            retry_attempts=1
        )
        
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        redis_manager._telemetry = mock_telemetry
        
        mock_client = AsyncMock()
        mock_client.set = AsyncMock(return_value=True)
        redis_manager._client = mock_client
        redis_manager._is_available = True
        
        result = await redis_manager.set("test_key", "test_value", ttl=60)
        
        assert mock_telemetry.track_dependency.called
        call_args = mock_telemetry.track_dependency.call_args
        assert call_args[1]["name"] == "Redis SET"
        assert call_args[1]["success"] is True


class TestQdrantTelemetry:
    """Test Qdrant operations track telemetry correctly."""
    
    @pytest.mark.asyncio
    async def test_qdrant_search_tracks_telemetry(self):
        """Test that Qdrant search operation tracks telemetry."""
        # Create Qdrant service
        with patch('services.qdrant_service.AsyncQdrantClient'), \
             patch('services.qdrant_service.QdrantClient'):
            qdrant_service = QdrantService()
            
            # Mock telemetry service
            mock_telemetry = Mock()
            mock_telemetry.track_dependency = Mock()
            qdrant_service._telemetry = mock_telemetry
            
            # Mock async client
            mock_result = Mock()
            mock_result.points = []
            qdrant_service.async_client.query_points = AsyncMock(return_value=mock_result)
            
            # Execute search
            results = await qdrant_service.search(
                collection_name="test_collection",
                query_vector=[0.1] * 768,
                limit=5
            )
            
            # Verify telemetry was tracked
            assert mock_telemetry.track_dependency.called
            call_args = mock_telemetry.track_dependency.call_args
            assert call_args[1]["name"] == "Qdrant search"
            assert call_args[1]["dependency_type"] == "qdrant"
            assert call_args[1]["success"] is True
            assert call_args[1]["properties"]["operation"] == "search"
            assert call_args[1]["properties"]["collection"] == "test_collection"
    
    @pytest.mark.asyncio
    async def test_qdrant_upsert_tracks_telemetry(self):
        """Test that Qdrant upsert operation tracks telemetry."""
        with patch('services.qdrant_service.AsyncQdrantClient'), \
             patch('services.qdrant_service.QdrantClient'):
            qdrant_service = QdrantService()
            
            mock_telemetry = Mock()
            mock_telemetry.track_dependency = Mock()
            qdrant_service._telemetry = mock_telemetry
            
            qdrant_service.async_client.upsert = AsyncMock()
            
            await qdrant_service.upsert_chunks(
                collection_name="test_collection",
                chunks=["test chunk"],
                embeddings=[[0.1] * 768],
                metadata=[{"document_id": "doc1", "chunk_id": 0}]
            )
            
            assert mock_telemetry.track_dependency.called
            call_args = mock_telemetry.track_dependency.call_args
            assert call_args[1]["name"] == "Qdrant upsert"
            assert call_args[1]["success"] is True


class TestLLMTelemetry:
    """Test LLM API calls track telemetry correctly."""
    
    @pytest.mark.asyncio
    async def test_llm_chat_completion_tracks_telemetry(self):
        """Test that LLM chat completion tracks telemetry."""
        llm_service = LLMService()
        
        # Mock telemetry service
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        llm_service._telemetry = mock_telemetry
        
        # Mock LLM client
        with patch.object(llm_service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.content = "Test response"
            mock_client.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client
            
            # Execute chat completion
            result = await llm_service.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.7,
                max_tokens=100
            )
            
            # Verify telemetry was tracked
            assert mock_telemetry.track_dependency.called
            call_args = mock_telemetry.track_dependency.call_args
            assert call_args[1]["name"] == "Azure OpenAI chat_completion"
            assert call_args[1]["dependency_type"] == "http"
            assert call_args[1]["success"] is True
            assert call_args[1]["properties"]["operation"] == "chat_completion"
            assert call_args[1]["properties"]["deployment"] == llm_service.azure_deployment


class TestSupabaseTelemetry:
    """Test Supabase database operations track telemetry correctly."""
    
    @pytest.mark.asyncio
    async def test_async_db_tracks_telemetry(self):
        """Test that async_db wrapper tracks telemetry."""
        # Mock telemetry service
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        
        with patch('core.telemetry.get_telemetry_service', return_value=mock_telemetry):
            # Mock database query
            mock_query = Mock(return_value={"data": [{"id": "1"}]})
            
            # Execute query
            result = await async_db(mock_query)
            
            # Verify telemetry was tracked
            assert mock_telemetry.track_dependency.called
            call_args = mock_telemetry.track_dependency.call_args
            assert call_args[1]["name"] == "Supabase query"
            assert call_args[1]["dependency_type"] == "supabase"
            assert call_args[1]["success"] is True


class TestTelemetryFailureTracking:
    """Test that failed operations are tracked correctly."""
    
    @pytest.mark.asyncio
    async def test_redis_failure_tracks_telemetry(self):
        """Test that Redis operation failures track telemetry."""
        redis_manager = RedisCacheManager(
            host="localhost",
            port=6379,
            password="test",
            retry_attempts=1
        )
        
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        redis_manager._telemetry = mock_telemetry
        
        # Mock Redis client to raise RedisError (not generic Exception)
        from redis.exceptions import RedisError
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RedisError("Connection error"))
        redis_manager._client = mock_client
        redis_manager._is_available = True
        
        # Execute GET operation (should handle error gracefully)
        result = await redis_manager.get("test_key")
        
        # Verify telemetry tracked the failure
        assert mock_telemetry.track_dependency.called
        call_args = mock_telemetry.track_dependency.call_args
        assert call_args[1]["success"] is False
        assert "error" in call_args[1]["properties"]
    
    @pytest.mark.asyncio
    async def test_llm_failure_tracks_telemetry(self):
        """Test that LLM API failures track telemetry."""
        llm_service = LLMService()
        
        mock_telemetry = Mock()
        mock_telemetry.track_dependency = Mock()
        llm_service._telemetry = mock_telemetry
        
        with patch.object(llm_service, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.ainvoke = AsyncMock(side_effect=Exception("API error"))
            mock_get_client.return_value = mock_client
            
            # Execute chat completion (should raise exception)
            with pytest.raises(Exception):
                await llm_service.chat_completion(
                    messages=[{"role": "user", "content": "Hello"}]
                )
            
            # Verify telemetry tracked the failure
            assert mock_telemetry.track_dependency.called
            call_args = mock_telemetry.track_dependency.call_args
            assert call_args[1]["success"] is False
            assert "error" in call_args[1]["properties"]
