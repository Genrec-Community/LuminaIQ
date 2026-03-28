"""Integration test for global exception handler.

**Validates: Requirement 20.2**

This test verifies that the global exception handler correctly tracks exceptions
in telemetry with full stack traces and context.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def test_exception_handler_integration():
    """
    Integration test to verify exception handler tracks exceptions.
    
    This test verifies that:
    1. The exception handler is called when an exception occurs
    2. Exception telemetry is tracked with stack trace and context
    3. A proper error response is returned to the client
    """
    # Create mock telemetry service
    mock_service = Mock()
    mock_service.enabled = True
    mock_service.track_exception = Mock()
    
    # Create app
    app = FastAPI()
    
    # Register exception handler with mocked telemetry
    with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
        from main import global_exception_handler
        app.add_exception_handler(Exception, global_exception_handler)
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Test exception for integration")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Make request
        response = client.get("/test")
    
    # Verify response
    assert response.status_code == 500
    json_response = response.json()
    assert json_response["detail"] == "Internal server error"
    assert json_response["error_type"] == "ValueError"
    assert "correlation_id" in json_response
    
    # Verify telemetry was called
    assert mock_service.track_exception.called, "Exception telemetry should be tracked"
    
    # Verify exception details
    call_args = mock_service.track_exception.call_args
    exception = call_args[1]["exception"]
    assert isinstance(exception, ValueError)
    assert str(exception) == "Test exception for integration"
    
    # Verify properties include required context
    properties = call_args[1]["properties"]
    assert "exception_type" in properties
    assert properties["exception_type"] == "ValueError"
    assert "exception_message" in properties
    assert "stack_trace" in properties
    assert "ValueError" in properties["stack_trace"]
    assert "method" in properties
    assert "path" in properties


def test_exception_handler_with_correlation_id():
    """
    Test that exception handler includes correlation ID from middleware.
    """
    from middleware.telemetry import TelemetryMiddleware
    
    # Create mock telemetry service
    mock_service = Mock()
    mock_service.enabled = True
    mock_service.track_exception = Mock()
    mock_service.track_request = Mock()
    
    # Create app with middleware
    app = FastAPI()
    
    with patch("middleware.telemetry.get_telemetry_service", return_value=mock_service):
        app.add_middleware(TelemetryMiddleware)
    
    with patch("core.telemetry.get_telemetry_service", return_value=mock_service):
        from main import global_exception_handler
        app.add_exception_handler(Exception, global_exception_handler)
        
        @app.get("/test")
        async def test_endpoint():
            raise RuntimeError("Test with correlation")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Make request
        response = client.get("/test")
    
    # Verify correlation ID in response
    assert "correlation_id" in response.json()
    correlation_id = response.json()["correlation_id"]
    assert correlation_id is not None
    
    # Verify exception telemetry includes correlation ID
    assert mock_service.track_exception.called
    call_args = mock_service.track_exception.call_args
    properties = call_args[1]["properties"]
    assert "correlation_id" in properties
    assert properties["correlation_id"] == correlation_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
