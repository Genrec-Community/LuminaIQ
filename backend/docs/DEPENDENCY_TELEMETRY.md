# Dependency Telemetry Implementation

## Overview

This document describes the implementation of dependency telemetry tracking for external service calls in the LuminaIQ backend. All external dependencies (Redis, Supabase, Qdrant, LLM API) now track telemetry data including operation name, duration, success status, and relevant properties.

## Architecture

### Telemetry Service

The core telemetry service (`backend/core/telemetry.py`) provides the `track_dependency` method:

```python
def track_dependency(
    self,
    name: str,
    dependency_type: str,
    duration: float,
    success: bool,
    properties: Optional[Dict[str, Any]] = None
) -> None
```

This method sends dependency telemetry to Azure Application Insights using OpenTelemetry.

### Integration Points

#### 1. Redis Cache Manager (`backend/core/redis_manager.py`)

**Implementation:**
- Added telemetry tracking to `_execute_with_retry` method
- Tracks all Redis operations (GET, SET, DELETE, MGET, INCRBY, EXPIRE)
- Captures operation name, duration, success/failure, and error details

**Telemetry Properties:**
- `operation`: Redis command (GET, SET, etc.)
- `host`: Redis server hostname
- `db`: Redis database number
- `error`: Error message (if failed)

**Example:**
```python
# Tracked automatically when using Redis operations
await redis_manager.get("cache_key")
# Sends telemetry: name="Redis GET", type="redis", duration=5.2ms, success=True
```

#### 2. Qdrant Vector Database (`backend/services/qdrant_service.py`)

**Implementation:**
- Added telemetry tracking to `upsert_chunks` and `search` methods
- Tracks vector operations with collection name and result counts

**Telemetry Properties:**
- `operation`: Operation type (upsert, search)
- `collection`: Collection name
- `points_count`: Number of points (for upsert)
- `limit`: Search limit
- `results_count`: Number of results returned
- `error`: Error message (if failed)

**Example:**
```python
# Tracked automatically when searching
results = await qdrant_service.search(
    collection_name="project_123",
    query_vector=embedding,
    limit=5
)
# Sends telemetry: name="Qdrant search", type="qdrant", duration=45.3ms, success=True
```

#### 3. LLM Service (`backend/services/llm_service.py`)

**Implementation:**
- Added telemetry tracking to `chat_completion` method
- Tracks LLM API calls with model parameters and response metrics

**Telemetry Properties:**
- `operation`: Operation type (chat_completion)
- `deployment`: Azure OpenAI deployment name
- `temperature`: Temperature parameter
- `max_tokens`: Max tokens parameter
- `message_count`: Number of messages in request
- `response_length`: Length of response
- `error`: Error message (if failed)

**Example:**
```python
# Tracked automatically when calling LLM
response = await llm_service.chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7
)
# Sends telemetry: name="Azure OpenAI chat_completion", type="http", duration=1250ms, success=True
```

#### 4. Supabase Database (`backend/db/client.py`)

**Implementation:**
- Added telemetry tracking to `async_db` and `async_db_execute` wrappers
- Tracks all database queries executed through the async wrappers

**Telemetry Properties:**
- `operation`: Operation type (query)
- `error`: Error message (if failed)

**Example:**
```python
# Tracked automatically when using async_db wrapper
result = await async_db(
    lambda: client.table("documents").select("*").eq("id", doc_id).execute()
)
# Sends telemetry: name="Supabase query", type="supabase", duration=23.5ms, success=True
```

**Additional Wrapper:**
A dedicated telemetry wrapper module (`backend/db/telemetry_wrapper.py`) provides:
- `track_db_operation` decorator for custom tracking
- `track_supabase_query` function for explicit tracking

## Telemetry Data Structure

All dependency telemetry includes:

1. **name**: Human-readable operation name (e.g., "Redis GET", "Qdrant search")
2. **dependency_type**: Type of dependency (redis, supabase, qdrant, http)
3. **duration**: Operation duration in milliseconds
4. **success**: Boolean indicating success/failure
5. **properties**: Dictionary with operation-specific metadata

## Viewing Telemetry Data

### Azure Application Insights

Dependency telemetry can be viewed in Azure Application Insights:

1. **Dependencies View**: Shows all external service calls with duration and success rate
2. **Application Map**: Visualizes dependencies and their relationships
3. **Performance View**: Identifies slow dependencies
4. **Failures View**: Shows failed dependency calls with error details

### Query Examples

```kusto
// All Redis operations in the last hour
dependencies
| where timestamp > ago(1h)
| where type == "redis"
| project timestamp, name, duration, success, properties

// Failed Qdrant searches
dependencies
| where type == "qdrant"
| where success == false
| project timestamp, name, duration, properties.error

// Slow LLM API calls (>2 seconds)
dependencies
| where type == "http"
| where name contains "OpenAI"
| where duration > 2000
| project timestamp, name, duration, properties.deployment
```

## Performance Impact

The telemetry implementation has minimal performance impact:

- **Overhead**: <1ms per operation (telemetry is sent asynchronously)
- **Lazy Loading**: Telemetry service is loaded only when needed
- **Graceful Degradation**: If telemetry fails, operations continue normally
- **Sampling**: Configurable sampling rates to reduce volume

## Testing

Comprehensive unit tests verify telemetry tracking:

- `backend/tests/unit/test_dependency_telemetry.py`
- Tests cover all dependency types (Redis, Qdrant, LLM, Supabase)
- Tests verify both success and failure scenarios
- Tests validate telemetry properties are correctly captured

Run tests:
```bash
cd backend
python -m pytest tests/unit/test_dependency_telemetry.py -v
```

## Configuration

Telemetry is configured via environment variables:

```env
# Azure Application Insights connection string
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...

# Optional: Disable telemetry
TELEMETRY_ENABLED=false
```

## Best Practices

1. **Always use wrappers**: Use `async_db`, `redis_manager`, etc. to ensure telemetry is tracked
2. **Include context**: Add relevant properties to help with debugging
3. **Monitor regularly**: Set up alerts for high failure rates or slow operations
4. **Optimize based on data**: Use telemetry to identify bottlenecks

## Future Enhancements

Potential improvements:

1. **Custom metrics**: Track cache hit rates, queue lengths, etc.
2. **Distributed tracing**: Link dependencies across service boundaries
3. **Cost tracking**: Monitor API usage and costs
4. **Anomaly detection**: Automatically detect unusual patterns

## Related Documentation

- [Telemetry Service](../core/telemetry.py)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Azure Application Insights](https://docs.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
