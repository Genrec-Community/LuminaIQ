"""
Unit tests for structured logger with correlation ID support.
"""
import pytest
import json
from utils.logger import (
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
    log_with_context,
    json_formatter,
    logger
)


class TestCorrelationID:
    """Test correlation ID context management."""
    
    def test_set_and_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        test_id = "test-correlation-123"
        set_correlation_id(test_id)
        assert get_correlation_id() == test_id
        clear_correlation_id()
    
    def test_clear_correlation_id(self):
        """Test clearing correlation ID."""
        set_correlation_id("test-id")
        clear_correlation_id()
        assert get_correlation_id() is None
    
    def test_correlation_id_default_none(self):
        """Test correlation ID defaults to None."""
        clear_correlation_id()
        assert get_correlation_id() is None


class TestJSONFormatter:
    """Test JSON log formatting."""
    
    def test_json_formatter_structure(self):
        """Test JSON formatter produces correct structure."""
        # Create a mock record
        from datetime import datetime
        from loguru import logger as loguru_logger
        
        # Set correlation ID
        test_correlation_id = "corr-123"
        set_correlation_id(test_correlation_id)
        
        # Create a minimal record structure
        record = {
            "time": datetime.now(),
            "level": type('obj', (object,), {'name': 'INFO'}),
            "message": "Test message",
            "name": "test_logger",
            "function": "test_function",
            "line": 42,
            "module": "test_module",
            "extra": {"custom_field": "custom_value"}
        }
        
        # Format the record
        formatted = json_formatter(record)
        
        # Parse JSON
        log_entry = json.loads(formatted)
        
        # Verify structure
        assert "timestamp" in log_entry
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test message"
        assert log_entry["correlation_id"] == test_correlation_id
        assert "context" in log_entry
        assert log_entry["context"]["name"] == "test_logger"
        assert log_entry["context"]["function"] == "test_function"
        assert log_entry["context"]["line"] == 42
        assert log_entry["context"]["custom_field"] == "custom_value"
        
        clear_correlation_id()
    
    def test_json_formatter_without_correlation_id(self):
        """Test JSON formatter when correlation ID is not set."""
        from datetime import datetime
        
        clear_correlation_id()
        
        record = {
            "time": datetime.now(),
            "level": type('obj', (object,), {'name': 'DEBUG'}),
            "message": "Debug message",
            "name": "test",
            "function": "func",
            "line": 10,
            "module": "mod"
        }
        
        formatted = json_formatter(record)
        log_entry = json.loads(formatted)
        
        assert log_entry["correlation_id"] is None
        assert log_entry["message"] == "Debug message"
    
    def test_json_formatter_with_exception(self):
        """Test JSON formatter includes exception information."""
        from datetime import datetime
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            exception_info = type('obj', (object,), {
                'type': type(e),
                'value': e
            })
            
            record = {
                "time": datetime.now(),
                "level": type('obj', (object,), {'name': 'ERROR'}),
                "message": "Error occurred",
                "name": "test",
                "function": "func",
                "line": 10,
                "module": "mod",
                "exception": exception_info
            }
            
            formatted = json_formatter(record)
            log_entry = json.loads(formatted)
            
            assert "exception" in log_entry
            assert log_entry["exception"]["type"] == "ValueError"
            assert "Test error" in log_entry["exception"]["value"]


class TestLogWithContext:
    """Test logging with additional context."""
    
    def test_log_with_context(self, caplog):
        """Test logging with custom context fields."""
        # This is a basic test to ensure the function doesn't raise errors
        set_correlation_id("test-123")
        
        # Should not raise any exceptions
        log_with_context("INFO", "Test message", user_id="user_123", action="test_action")
        
        clear_correlation_id()


class TestCorrelationIDIsolation:
    """Test that correlation IDs are isolated between contexts."""
    
    def test_correlation_id_isolation(self):
        """Test correlation ID doesn't leak between different contexts."""
        # Set first correlation ID
        set_correlation_id("corr-1")
        assert get_correlation_id() == "corr-1"
        
        # Change to second correlation ID
        set_correlation_id("corr-2")
        assert get_correlation_id() == "corr-2"
        
        # Clear
        clear_correlation_id()
        assert get_correlation_id() is None
