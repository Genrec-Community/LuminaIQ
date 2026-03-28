"""Integration tests for health check endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Test suite for health check endpoints."""
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_redis(self):
        """Initialize Redis manager before tests."""
        from core.redis_manager import initialize_redis_manager
        import asyncio
        
        # Initialize Redis manager (will gracefully degrade if unavailable)
        redis_manager = initialize_redis_manager()
        
        # Try to connect (will log warning if unavailable)
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(redis_manager.connect())
            loop.close()
        except Exception:
            pass  # Graceful degradation
        
        yield
        
        # Cleanup
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(redis_manager.disconnect())
            loop.close()
        except Exception:
            pass
    
    @pytest.fixture(scope="class")
    def client(self, setup_redis):
        """Create test client after Redis is initialized."""
        from main import app
        return TestClient(app)
    
    def test_health_endpoint_returns_200(self, client):
        """Test that /health endpoint returns 200 OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data
        
        # Verify values
        assert data["status"] == "healthy"
        assert data["service"] == "lumina-backend"
        assert data["version"] == "1.0.0"
    
    def test_health_endpoint_response_time(self, client):
        """Test that /health endpoint responds quickly (< 100ms)."""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        elapsed_ms = (time.time() - start_time) * 1000
        
        assert response.status_code == 200
        assert elapsed_ms < 100, f"Health check took {elapsed_ms}ms, expected < 100ms"
    
    def test_health_ready_endpoint_exists(self, client):
        """Test that /health/ready endpoint exists and returns valid response."""
        response = client.get("/health/ready")
        
        # Should return either 200 or 503 depending on dependencies
        assert response.status_code in [200, 503]
        
        data = response.json()
        
        # Verify response structure
        assert "status" in data
        
        if response.status_code == 200:
            assert data["status"] == "ready"
            assert "dependencies" in data
            
            # Verify all expected dependencies are checked
            dependencies = data["dependencies"]
            expected_deps = ["redis", "supabase", "qdrant", "azure_openai"]
            
            for dep_name in expected_deps:
                assert dep_name in dependencies, f"Missing dependency: {dep_name}"
                
                dep_status = dependencies[dep_name]
                assert "status" in dep_status
                assert "latency_ms" in dep_status
                assert dep_status["status"] in ["healthy", "degraded", "unhealthy"]
        else:
            # 503 response
            assert data["status"] == "not_ready"
            assert "dependencies" in data or "error" in data
    
    def test_health_ready_endpoint_response_time(self, client):
        """Test that /health/ready endpoint responds within 1 second."""
        import time
        
        start_time = time.time()
        response = client.get("/health/ready")
        elapsed_ms = (time.time() - start_time) * 1000
        
        assert response.status_code in [200, 503]
        assert elapsed_ms < 1000, f"Readiness check took {elapsed_ms}ms, expected < 1000ms"
    
    def test_health_ready_dependency_structure(self, client):
        """Test that dependency status has correct structure."""
        response = client.get("/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            dependencies = data["dependencies"]
            
            # Check structure of each dependency
            for dep_name, dep_status in dependencies.items():
                assert "status" in dep_status
                assert "latency_ms" in dep_status
                
                # latency_ms should be a number
                assert isinstance(dep_status["latency_ms"], (int, float))
                assert dep_status["latency_ms"] >= 0
                
                # error_message is optional, only present when unhealthy
                if dep_status["status"] != "healthy":
                    # May or may not have error_message
                    pass
    
    def test_health_ready_includes_cache_status(self, client):
        """Test that /health/ready endpoint includes cache status information."""
        response = client.get("/health/ready")
        
        assert response.status_code in [200, 503]
        data = response.json()
        
        # Verify cache_status is present
        assert "cache_status" in data, "cache_status should be included in readiness response"
        
        cache_status = data["cache_status"]
        
        # Verify cache_status structure
        assert "enabled" in cache_status
        assert "available" in cache_status
        assert "graceful_degradation" in cache_status
        assert "mode" in cache_status
        assert "message" in cache_status
        
        # Verify types
        assert isinstance(cache_status["enabled"], bool)
        assert isinstance(cache_status["available"], bool)
        assert isinstance(cache_status["graceful_degradation"], bool)
        assert isinstance(cache_status["mode"], str)
        assert isinstance(cache_status["message"], str)
        
        # Verify mode is valid
        assert cache_status["mode"] in ["normal", "degraded"]
    
    def test_health_ready_cache_status_normal_mode(self, client):
        """Test cache status when Redis is available (normal mode)."""
        response = client.get("/health/ready")
        
        if response.status_code == 200:
            data = response.json()
            
            # If Redis dependency is healthy, cache should be in normal mode
            if data["dependencies"]["redis"]["status"] == "healthy":
                cache_status = data["cache_status"]
                
                assert cache_status["enabled"] is True
                assert cache_status["available"] is True
                assert cache_status["graceful_degradation"] is False
                assert cache_status["mode"] == "normal"
                assert "operational" in cache_status["message"].lower()
    
    def test_health_ready_cache_status_degraded_mode(self, client):
        """Test cache status when Redis is unavailable (degraded mode)."""
        response = client.get("/health/ready")
        data = response.json()
        
        # If Redis dependency is unhealthy, cache should be in degraded mode
        if data["dependencies"]["redis"]["status"] == "unhealthy":
            cache_status = data["cache_status"]
            
            assert cache_status["enabled"] is True
            assert cache_status["available"] is False
            assert cache_status["graceful_degradation"] is True
            assert cache_status["mode"] == "degraded"
            assert "degraded" in cache_status["message"].lower()
            assert "database" in cache_status["message"].lower()



