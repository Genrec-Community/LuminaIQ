# Structured Logging with Correlation IDs

## Overview

The LuminaIQ backend now supports structured logging with correlation ID tracking for improved observability and debugging. This allows you to trace requests across all services and log entries.

## Features

- **JSON Structured Logging**: Logs can be output in JSON format for production environments
- **Correlation ID Support**: Unique identifiers track requests across the system
- **Context Variables**: Thread-safe correlation ID storage using Python's `contextvars`
- **Flexible Formatting**: Human-readable console logs, JSON file logs
- **Additional Context**: Add custom fields to log entries

## Configuration

### Enable JSON Logging

Set the `JSON_LOGS` environment variable to enable JSON structured logging:

```bash
# Development (human-readable logs)
JSON_LOGS=false

# Production (JSON structured logs)
JSON_LOGS=true
```

## Usage

### Basic Logging

```python
from utils.logger import logger

logger.info("User logged in successfully")
logger.warning("Cache miss for key: user_123")
logger.error("Failed to connect to database")
```

### Setting Correlation ID

```python
from utils.logger import set_correlation_id, logger
import uuid

# Generate and set correlation ID for a request
correlation_id = str(uuid.uuid4())
set_correlation_id(correlation_id)

logger.info("Processing request")
# Log output will include: correlation_id=<uuid>
```

### Getting Correlation ID

```python
from utils.logger import get_correlation_id

# Retrieve current correlation ID
current_id = get_correlation_id()
if current_id:
    print(f"Current correlation ID: {current_id}")
```

### Clearing Correlation ID

```python
from utils.logger import clear_correlation_id

# Clear correlation ID after request completes
clear_correlation_id()
```

### Logging with Additional Context

```python
from utils.logger import log_with_context

log_with_context(
    "INFO",
    "User action completed",
    user_id="user_123",
    action="document_upload",
    project_id="proj_456",
    duration_ms=1234
)
```

## Middleware Integration

### FastAPI Middleware Example

```python
from fastapi import Request
from utils.logger import set_correlation_id, clear_correlation_id, logger
import uuid

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    # Generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    
    # Set in context
    set_correlation_id(correlation_id)
    
    try:
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
    finally:
        # Clean up
        clear_correlation_id()
```

## Log Output Formats

### Console Output (Human-Readable)

```
10:30:45 | INFO     | lumina | corr_id=abc-123-def | Processing document upload
10:30:46 | WARNING  | lumina | corr_id=abc-123-def | Cache miss for embedding
10:30:47 | INFO     | lumina | corr_id=abc-123-def | Document processed successfully
```

### JSON File Output (Production)

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "INFO",
  "message": "Processing document upload",
  "correlation_id": "abc-123-def",
  "context": {
    "name": "lumina",
    "function": "upload_document",
    "line": 42,
    "module": "document_service",
    "user_id": "user_123",
    "project_id": "proj_456"
  }
}
```

### JSON with Exception

```json
{
  "timestamp": "2024-01-15T10:30:47.123456",
  "level": "ERROR",
  "message": "Failed to process document",
  "correlation_id": "abc-123-def",
  "context": {
    "name": "lumina",
    "function": "process_document",
    "line": 89,
    "module": "document_service"
  },
  "exception": {
    "type": "ValueError",
    "value": "Invalid document format"
  }
}
```

## Best Practices

1. **Always set correlation ID at request entry point**: Use middleware to automatically set correlation IDs for all incoming requests

2. **Propagate correlation IDs**: Pass correlation IDs to background jobs and external service calls

3. **Include relevant context**: Add user_id, project_id, and other relevant fields to logs

4. **Clean up after requests**: Always clear correlation ID in a finally block to prevent leakage

5. **Use structured logging in production**: Enable JSON_LOGS=true for production environments to facilitate log aggregation and analysis

6. **Log at appropriate levels**:
   - DEBUG: Detailed diagnostic information
   - INFO: General informational messages
   - WARNING: Warning messages for potentially harmful situations
   - ERROR: Error messages for serious problems
   - CRITICAL: Critical messages for very severe errors

## Integration with Azure Application Insights

The structured logs with correlation IDs integrate seamlessly with Azure Application Insights:

- Correlation IDs link logs, traces, and telemetry
- JSON format enables easy parsing and querying
- Custom context fields become searchable properties
- Exception information is automatically captured

## Troubleshooting

### Correlation ID not appearing in logs

Ensure you've called `set_correlation_id()` before logging:

```python
from utils.logger import set_correlation_id, logger

set_correlation_id("test-123")
logger.info("This will include correlation ID")
```

### JSON logs not being created

Check the `JSON_LOGS` environment variable:

```python
import os
print(os.getenv("JSON_LOGS"))  # Should be "true" for JSON logging
```

### Correlation ID leaking between requests

Always clear correlation ID after request completion:

```python
try:
    set_correlation_id(correlation_id)
    # Process request
finally:
    clear_correlation_id()
```
