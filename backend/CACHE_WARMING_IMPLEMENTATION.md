# Cache Warming Implementation

## Overview

This document describes the implementation of cache warming functionality for the high-performance backend refactoring (Task 2.3).

## Requirements Addressed

**Validates: Requirements 4.5, 28.1, 28.2, 28.3, 28.4**

- **Requirement 4.5**: Support cache warming for frequently accessed projects on startup
- **Requirement 28.1**: Preload document metadata for the 10 most active projects
- **Requirement 28.2**: Preload topic lists for the 10 most active projects
- **Requirement 28.3**: Complete cache warming within 30 seconds of startup
- **Requirement 28.4**: Log cache warming progress and completion

## Implementation Details

### 1. VectorSearchCache.warm_cache() Method

**Location**: `backend/core/vector_cache.py`

The `warm_cache()` method implements the following logic:

1. **Query Top 10 Active Projects**
   - Queries Supabase for projects ordered by `updated_at` DESC
   - Limits results to 10 most recently active projects

2. **Preload Document Metadata**
   - For each project, fetches all documents
   - Caches each document's metadata with key: `doc:{doc_id}`
   - Caches document list for project with key: `docs:{project_id}`
   - TTL: 6 hours (21600 seconds)

3. **Preload Topic Lists**
   - Extracts unique topics from all documents in each project
   - Caches topic list with key: `topics:{project_id}`
   - TTL: 6 hours (21600 seconds)

4. **Timeout Protection**
   - Entire warming process wrapped in `asyncio.wait_for()` with 30-second timeout
   - If timeout occurs, logs warning and returns gracefully

5. **Error Handling**
   - Catches exceptions per project (partial failures don't stop warming)
   - Logs warnings for individual project failures
   - Returns success/failure status with statistics

### 2. Startup Integration

**Location**: `backend/main.py`

The cache warming is integrated into the `startup_event()` function:

```python
@app.on_event("startup")
async def startup_event():
    # ... Redis initialization ...
    
    # Warm cache with top 10 active projects
    try:
        from core.vector_cache import VectorSearchCache
        vector_cache = VectorSearchCache(redis_manager)
        warming_result = await vector_cache.warm_cache()
        
        if warming_result.get("success"):
            logger.info(f"Cache warming completed successfully: ...")
        else:
            logger.warning(f"Cache warming failed: ...")
    except Exception as e:
        logger.warning(f"Cache warming failed: {e}")
        logger.info("Application will continue without cache warming")
```

**Key Features**:
- Runs after Redis initialization
- Non-blocking (uses async/await)
- Graceful degradation (application continues if warming fails)
- Detailed logging of results

### 3. Cache Key Structure

The implementation uses the following cache key patterns:

- **Document Metadata**: `doc:{doc_id}`
  - Stores: id, filename, project_id, topics, upload_status, created_at
  - TTL: 6 hours

- **Document List**: `docs:{project_id}`
  - Stores: Array of document IDs for the project
  - TTL: 6 hours

- **Topic List**: `topics:{project_id}`
  - Stores: Array of unique topic names for the project
  - TTL: 6 hours

## Testing

### Manual Test Script

**Location**: `backend/test_cache_warming_manual.py`

Run the manual test to verify cache warming:

```bash
cd backend
python test_cache_warming_manual.py
```

The test script:
1. Initializes Redis manager
2. Creates VectorSearchCache instance
3. Executes cache warming
4. Validates all requirements
5. Reports results

### Expected Output

```
============================================================
Testing Cache Warming Functionality
============================================================

1. Initializing Redis manager...
✓ Redis manager connected successfully

2. Creating VectorSearchCache instance...
✓ VectorSearchCache created

3. Starting cache warming...

============================================================
Cache Warming Results:
============================================================
Success: True
Duration: 2.45 seconds
Projects warmed: 10
Documents cached: 45
Topics cached: 23

============================================================
Requirements Validation:
============================================================
✓ Requirement 28.1: Preloaded top 10 active projects
✓ Requirement 28.2: Preloaded topic lists
✓ Requirement 28.3: Completed within 30 seconds (2.45s)
✓ Requirement 28.4: Logged progress and completion

✓ All requirements validated successfully!
```

## Performance Characteristics

- **Typical Duration**: 2-5 seconds for 10 projects with 50-100 documents
- **Maximum Duration**: 30 seconds (enforced by timeout)
- **Memory Impact**: Minimal (only metadata cached, not full documents)
- **Network Impact**: 1 query for projects + 1 query per project for documents

## Error Handling

The implementation handles the following error scenarios:

1. **Redis Unavailable**: Logs warning, application continues without caching
2. **Database Timeout**: Returns after 30 seconds with partial results
3. **Database Error**: Logs error, returns failure status
4. **Partial Failures**: Continues warming other projects, logs warnings
5. **Empty Projects**: Returns success with zero items cached

## Monitoring

Cache warming emits the following log messages:

- **INFO**: "Starting cache warming for top 10 active projects..."
- **DEBUG**: "Warming project X/Y: {project_name} ({project_id})"
- **DEBUG**: "Cached N documents for project {project_name}"
- **DEBUG**: "Cached N topics for project {project_name}"
- **INFO**: "Cache warming completed in Xs - Projects: N, Documents: N, Topics: N"
- **WARNING**: "Cache warming timed out after Xs"
- **WARNING**: "Failed to cache documents for project {project_id}: {error}"
- **ERROR**: "Cache warming failed after Xs: {error}"

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable Project Count**: Make the "10" configurable via environment variable
2. **Activity Metrics**: Use actual activity metrics (views, queries) instead of updated_at
3. **Incremental Warming**: Warm cache incrementally in background after startup
4. **Cache Preheating**: Pre-generate common query embeddings
5. **Metrics Export**: Export warming statistics to Application Insights

## Related Files

- `backend/core/vector_cache.py` - Cache warming implementation
- `backend/main.py` - Startup integration
- `backend/core/redis_manager.py` - Redis connection management
- `backend/db/client.py` - Supabase database client
- `backend/config/settings.py` - Configuration settings
- `.kiro/specs/high-performance-backend-refactoring/requirements.md` - Requirements
- `.kiro/specs/high-performance-backend-refactoring/design.md` - Design document
