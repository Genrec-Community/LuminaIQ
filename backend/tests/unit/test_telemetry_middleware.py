"""Unit tests for telemetry middleware.

**Validates: Requirements 20.1, 20.2, 20.5**

Tests:
- Request telemetry tracking (duration, status code, endpoint)
- Correlation ID generation and propagation
- User ID and project ID extraction
- Cache status tracking
- Exception telemetry tracking
- Global exception handler telemetry tracking
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from middleware.telemetry import (
    TelemetryMiddleware,
    get_user_id_from_request,
    get_project_id_from_request,
    get_cache_status_from_response,
)


@pytest.fixture
def mock_telemetry_service():
    """Create a mock telemetry service."""
    service = Mock()
    service.enabled = True
    service.track_request = Mock()
    service.track_exception = Mock()
    return service


@pytest.fixture
def app_with_telemetry(mock_telemetry_service):
    """Create a FastAPI app with telemetry middleware."""
    app = FastAPI()
    
    # Patch get_telemetry_service to return our mock
    with patch("middleware.telemetry.get_telemetry_service", return_value=mock_telemetry_service):
        app.add_middleware(TelemetryMiddleware)
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}
    
    @app.get("/test-cache")
    async def test_cache_endpoint():
        response = JSONResponse(content={"message": "cached"})
        response.headers["X-Cache-Status"] = "HIT"
        return response
    
    @app.get("/test-error")
    async def test_error_endpoint():
        raise ValueError("Test error")
    
    return app


class TestTelemetryMiddleware:
    """Test suite for TelemetryMiddleware."""
    
    @pytest.mark.asyncio
    async def test_request_telemetry_tracking(self, app_with_telemetry, mock_telemetry_service):
        """Test that request telemetry is tracked with correct properties."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request
        response = client.get("/test")
        
        # Verify response
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        
        # Verify telemetry was tracked
        assert mock_telemetry_service.track_request.called
        call_args = mock_telemetry_service.track_request.call_args
        
        # Check request name
        assert call_args[1]["name"] == "GET /test"
        
        # Check status code
        assert call_args[1]["status_code"] == 200
        
        # Check duration (should be positive)
        assert call_args[1]["duration"] > 0
        
        # Check properties
        properties = call_args[1]["properties"]
        assert "correlation_id" in properties
        assert properties["method"] == "GET"
        assert properties["path"] == "/test"
    
    @pytest.mark.asyncio
    async def test_correlation_id_in_response_header(self, app_with_telemetry):
        """Test that correlation ID is added to response headers."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request
        response = client.get("/test")
        
        # Verify correlation ID header exists
        assert "X-Correlation-ID" in response.headers
        
        # Verify it's a valid UUID format
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) == 36  # UUID format: 8-4-4-4-12
        assert correlation_id.count("-") == 4
    
    @pytest.mark.asyncio
    async def test_user_id_tracking(self, app_with_telemetry, mock_telemetry_service):
        """Test that user ID is extracted and tracked in telemetry."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request with user ID header
        response = client.get("/test", headers={"X-User-ID": "user_123"})
        
        # Verify telemetry includes user_id
        assert mock_telemetry_service.track_request.called
        call_args = mock_telemetry_service.track_request.call_args
        properties = call_args[1]["properties"]
        
        assert "user_id" in properties
        assert properties["user_id"] == "user_123"
    
    @pytest.mark.asyncio
    async def test_project_id_tracking(self, app_with_telemetry, mock_telemetry_service):
        """Test that project ID is extracted and tracked in telemetry."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request with project_id query parameter
        response = client.get("/test?project_id=proj_456")
        
        # Verify telemetry includes project_id
        assert mock_telemetry_service.track_request.called
        call_args = mock_telemetry_service.track_request.call_args
        properties = call_args[1]["properties"]
        
        assert "project_id" in properties
        assert properties["project_id"] == "proj_456"
    
    @pytest.mark.asyncio
    async def test_cache_status_tracking(self, app_with_telemetry, mock_telemetry_service):
        """Test that cache status is extracted and tracked in telemetry."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request to endpoint that returns cache status
        response = client.get("/test-cache")
        
        # Verify response has cache status header
        assert response.headers.get("X-Cache-Status") == "HIT"
        
        # Verify telemetry includes cache_status
        assert mock_telemetry_service.track_request.called
        call_args = mock_telemetry_service.track_request.call_args
        properties = call_args[1]["properties"]
        
        assert "cache_status" in properties
        assert properties["cache_status"] == "HIT"
    
    @pytest.mark.asyncio
    async def test_exception_telemetry_tracking(self, app_with_telemetry, mock_telemetry_service):
        """Test that exceptions are tracked in telemetry."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app_with_telemetry)
        
        # Make a request that raises an exception
        with pytest.raises(ValueError):
            client.get("/test-error")
        
        # Verify exception telemetry was tracked
        assert mock_telemetry_service.track_exception.called
        call_args = mock_telemetry_service.track_exception.call_args
        
        # Check exception
        exception = call_args[1]["exception"]
        assert isinstance(exception, ValueError)
        assert str(exception) == "Test error"
        
        # Check properties
        properties = call_args[1]["properties"]
        assert "correlation_id" in properties
        assert properties["method"] == "GET"
        assert properties["path"] == "/test-error"
        assert properties["exception_type"] == "ValueError"
        
        # Verify failed request telemetry was also tracked
        assert mock_telemetry_service.track_request.called
        request_call_args = mock_telemetry_service.track_request.call_args
        assert request_call_args[1]["status_code"] == 500
    
    @pytest.mark.asyncio
    async def test_telemetry_disabled_when_not_configured(self):
        """Test that middleware works when telemetry is not configured."""
        app = FastAPI()
        
        # Create mock telemetry service with enabled=False
        mock_service = Mock()
        mock_service.enabled = False
        
        with patch("middleware.telemetry.get_telemetry_service", return_value=mock_service):
            app.add_middleware(TelemetryMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Make a request
        response = client.get("/test")
        
        # Verify response is successful
        assert response.status_code == 200
        
        # Verify correlation ID is still added
        assert "X-Correlation-ID" in response.headers
    
    @pytest.mark.asyncio
    async def test_slow_request_logging(self, app_with_telemetry, mock_telemetry_service, caplog):
        """Test that slow requests (>500ms) are logged."""
        from fastapi.testclient import TestClient
        import time
        
        # Create app with slow endpoint
        app = FastAPI()
        
        with patch("middleware.telemetry.get_telemetry_service", return_value=mock_telemetry_service):
            app.add_middleware(TelemetryMiddleware)
        
        @app.get("/slow")
        async def slow_endpoint():
            time.sleep(0.6)  # Sleep for 600ms
            return {"message": "slow"}
        
        client = TestClient(app)
        
        # Make a request
        with caplog.at_level("WARNING"):
            response = client.get("/slow")
        
        # Verify response
        assert response.status_code == 200
        
        # Verify slow request was logged
        assert any("Slow request detected" in record.message for record in caplog.records)


class TestHelperFunctions:
    """Test suite for helper functions."""
    
    def test_get_user_id_from_request_state(self):
        """Test extracting user ID from request state."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.user_id = "user_123"
        request.headers = {}
        
        user_id = get_user_id_from_request(request)
        assert user_id == "user_123"
    
    def test_get_user_id_from_header(self):
        """Test extracting user ID from header."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])  # No user_id attribute
        request.headers = {"X-User-ID": "user_456"}
        
        user_id = get_user_id_from_request(request)
        assert user_id == "user_456"
    
    def test_get_user_id_returns_none_when_not_present(self):
        """Test that None is returned when user ID is not present."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        request.headers = {}
        
        user_id = get_user_id_from_request(request)
        assert user_id is None
    
    def test_get_project_id_from_query_params(self):
        """Test extracting project ID from query parameters."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        request.query_params = {"project_id": "proj_123"}
        
        project_id = get_project_id_from_request(request)
        assert project_id == "proj_123"
    
    def test_get_project_id_from_path_params(self):
        """Test extracting project ID from path parameters."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        request.query_params = {}
        request.path_params = {"project_id": "proj_456"}
        
        project_id = get_project_id_from_request(request)
        assert project_id == "proj_456"
    
    def test_get_project_id_returns_none_when_not_present(self):
        """Test that None is returned when project ID is not present."""
        request = Mock(spec=Request)
        request.state = Mock(spec=[])
        request.query_params = {}
        
        project_id = get_project_id_from_request(request)
        assert project_id is None
    
    def test_get_cache_status_from_response_header(self):
        """Test extracting cache status from response header."""
        response = Mock(spec=Response)
        response.headers = {"X-Cache-Status": "HIT"}
        
        cache_status = get_cache_status_from_response(response)
        assert cache_status == "HIT"
    
    def test_get_cache_status_returns_none_when_not_present(self):
        """Test that None is returned when cache status is not present."""
        response = Mock(spec=Response)
        response.headers = {}
        
        cache_status = get_cache_status_from_response(response)
        assert cache_status is None


class TestGlobalExceptionHandler:
    """Test suite for global exception handler."""
    
    @pytest.mark.asyncio
    async def test_global_exception_handler_tracks_exception(self):
        """Test that global exception handler tracks exceptions in telemetry."""
        from fastapi.testclient import TestClient
        
        # Create mock telemetry service
        mock_service = Mock()
        mock_service.enabled = True
        mock_service.track_exception = Mock()
        
        # Create app with global exception handler
        app = FastAPI()
        
        # Import and register the exception handler with patched telemetry
        with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
            from main import global_exception_handler
            app.add_exception_handler(Exception, global_exception_handler)
            
            @app.get("/test-error")
            async def test_error():
                raise ValueError("Test exception")
            
            client = TestClient(app)
            
            # Make request that raises exception
            response = client.get("/test-error")
        
        # Verify response
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
        assert response.json()["error_type"] == "ValueError"
        assert "correlation_id" in response.json()
        
        # Verify exception was tracked in telemetry
        assert mock_service.track_exception.called
        call_args = mock_service.track_exception.call_args
        
        # Check exception
        exception = call_args[1]["exception"]
        assert isinstance(exception, ValueError)
        assert str(exception) == "Test exception"
        
        # Check properties include stack trace and context
        properties = call_args[1]["properties"]
        assert "exception_type" in properties
        assert properties["exception_type"] == "ValueError"
        assert "exception_message" in properties
        assert properties["exception_message"] == "Test exception"
        assert "stack_trace" in properties
        assert "ValueError" in properties["stack_trace"]
        assert "method" in properties
        assert properties["method"] == "GET"
        assert "path" in properties
        assert properties["path"] == "/test-error"
    
    @pytest.mark.asyncio
    async def test_global_exception_handler_includes_correlation_id(self):
        """Test that exception handler includes correlation ID in telemetry."""
        from fastapi.testclient import TestClient
        
        # Create mock telemetry service
        mock_service = Mock()
        mock_service.enabled = True
        mock_service.track_exception = Mock()
        mock_service.track_request = Mock()
        
        # Create app with middleware and exception handler
        app = FastAPI()
        
        with patch("middleware.telemetry.get_telemetry_service", return_value=mock_service):
            app.add_middleware(TelemetryMiddleware)
        
        with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
            from main import global_exception_handler
            app.add_exception_handler(Exception, global_exception_handler)
            
            @app.get("/test-error")
            async def test_error():
                raise RuntimeError("Test error with correlation")
            
            client = TestClient(app)
            
            # Make request
            response = client.get("/test-error")
        
        # Verify correlation ID in response
        assert "correlation_id" in response.json()
        correlation_id = response.json()["correlation_id"]
        
        # Verify exception telemetry includes correlation ID
        assert mock_service.track_exception.called
        call_args = mock_service.track_exception.call_args
        properties = call_args[1]["properties"]
        
        assert "correlation_id" in properties
        assert properties["correlation_id"] == correlation_id
    
    @pytest.mark.asyncio
    async def test_global_exception_handler_includes_user_and_project_context(self):
        """Test that exception handler includes user and project context."""
        from fastapi.testclient import TestClient
        
        # Create mock telemetry service
        mock_service = Mock()
        mock_service.enabled = True
        mock_service.track_exception = Mock()
        
        # Create app
        app = FastAPI()
        
        with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
            from main import global_exception_handler
            app.add_exception_handler(Exception, global_exception_handler)
            
            @app.get("/test-error")
            async def test_error(request: Request):
                # Simulate middleware setting user and project IDs
                request.state.user_id = "user_123"
                request.state.project_id = "proj_456"
                raise ValueError("Test with context")
            
            client = TestClient(app)
            
            # Make request
            response = client.get("/test-error")
        
        # Verify exception telemetry includes context
        assert mock_service.track_exception.called
        call_args = mock_service.track_exception.call_args
        properties = call_args[1]["properties"]
        
        assert "user_id" in properties
        assert properties["user_id"] == "user_123"
        assert "project_id" in properties
        assert properties["project_id"] == "proj_456"
    
    @pytest.mark.asyncio
    async def test_global_exception_handler_continues_on_telemetry_failure(self):
        """Test that exception handler continues even if telemetry fails."""
        from fastapi.testclient import TestClient
        
        # Create mock telemetry service that raises exception
        mock_service = Mock()
        mock_service.enabled = True
        mock_service.track_exception = Mock(side_effect=Exception("Telemetry error"))
        
        # Create app
        app = FastAPI()
        
        with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
            from main import global_exception_handler
            app.add_exception_handler(Exception, global_exception_handler)
            
            @app.get("/test-error")
            async def test_error():
                raise ValueError("Test exception")
            
            client = TestClient(app)
            
            # Make request - should still return error response
            response = client.get("/test-error")
        
        # Verify response is still returned despite telemetry failure
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"
        assert response.json()["error_type"] == "ValueError"

