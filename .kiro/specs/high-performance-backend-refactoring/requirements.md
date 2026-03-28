# Requirements Document: High-Performance Backend Refactoring

## Introduction

This document specifies the requirements for refactoring the LuminaIQ backend into a high-performance, Azure-optimized, production-grade architecture. The current system processes educational documents through a pipeline (upload → extract → chunk → embed → topics → knowledge graph) and provides RAG-powered features including chat, quiz generation, notes, flashcards, and knowledge graphs. While the system has basic async operations, it lacks comprehensive caching, persistent background job management, horizontal scalability, and production-grade observability. This refactoring will transform the backend into a system capable of supporting 100+ concurrent users with sub-300ms API response times, zero data loss on restarts, and 90%+ cache hit rates for repeated queries.

## Glossary

- **Backend_System**: The FastAPI-based LuminaIQ backend application
- **Redis_Cache**: Redis in-memory data store used for caching and session management
- **Background_Worker**: Celery or ARQ worker process that executes long-running tasks asynchronously
- **Job_Queue**: Persistent queue system (Redis-backed) for managing background tasks
- **RAG_Pipeline**: Retrieval-Augmented Generation pipeline combining vector search with LLM responses
- **Vector_DB**: Qdrant vector database storing document embeddings
- **Supabase_DB**: PostgreSQL database managed by Supabase for relational data
- **Semantic_Cache**: Cache that stores LLM responses indexed by semantic similarity of queries
- **Embedding_Cache**: Cache storing vector embeddings to avoid regenerating identical embeddings
- **Session_Store**: Redis-based storage for active user sessions and chat history
- **Distributed_Lock**: Redis-based locking mechanism for coordinating operations across multiple instances
- **Connection_Pool**: Reusable database connection pool to reduce connection overhead
- **Horizontal_Scaling**: Ability to run multiple backend instances behind a load balancer
- **Application_Insights**: Azure monitoring service for telemetry, logs, and distributed tracing
- **Health_Endpoint**: API endpoint reporting service health status for load balancer checks
- **Correlation_ID**: Unique identifier tracking a request across all services and logs
- **Knowledge_Graph**: Graph structure representing relationships between educational topics
- **Document_Pipeline**: Complete processing flow from document upload to knowledge graph generation
- **Batch_Operation**: Processing multiple items together to reduce API calls and improve throughput
- **Rate_Limiter**: Component controlling request frequency to prevent API quota exhaustion
- **Auto_Scaling**: Automatic adjustment of compute resources based on load metrics

## Requirements

### Requirement 1: Redis Caching Infrastructure

**User Story:** As a backend developer, I want a Redis caching layer integrated into the system, so that repeated queries and expensive computations are served from cache instead of recomputing.

#### Acceptance Criteria

1. THE Backend_System SHALL establish a connection pool to Redis_Cache on startup
2. WHEN Redis_Cache is unavailable, THE Backend_System SHALL log a warning and continue operating without cache
3. THE Backend_System SHALL implement cache key namespacing to prevent collisions between different data types
4. THE Backend_System SHALL support configurable TTL (time-to-live) values for different cache entry types
5. THE Backend_System SHALL provide cache statistics (hit rate, miss rate, total entries) via a monitoring endpoint

### Requirement 2: Embedding Result Caching

**User Story:** As a system administrator, I want embedding generation results cached, so that identical text chunks do not require redundant API calls to the embedding service.

#### Acceptance Criteria

1. WHEN an embedding is generated for text, THE Embedding_Cache SHALL store the result with the text hash as the key
2. WHEN an embedding is requested for text, THE Backend_System SHALL check Embedding_Cache before calling the embedding API
3. THE Embedding_Cache SHALL use a TTL of 30 days for embedding entries
4. THE Backend_System SHALL track cache hit rate for embeddings and log it every 100 requests
5. WHEN cache hit rate exceeds 80%, THE Backend_System SHALL log a success metric

### Requirement 3: Semantic Caching for RAG Queries

**User Story:** As a user, I want similar questions to return cached answers instantly, so that I don't wait for redundant LLM calls when asking questions that have been answered before.

#### Acceptance Criteria

1. WHEN a RAG query is processed, THE Semantic_Cache SHALL store the query embedding, answer, and sources
2. WHEN a new RAG query arrives, THE Backend_System SHALL search Semantic_Cache for queries with cosine similarity > 0.95
3. IF a semantically similar cached query exists, THE Backend_System SHALL return the cached answer within 50ms
4. THE Semantic_Cache SHALL use a TTL of 7 days for query-answer pairs
5. THE Backend_System SHALL include a cache metadata field indicating whether the response was cached

### Requirement 4: Vector Search Result Caching

**User Story:** As a backend developer, I want vector search results cached, so that identical searches against Vector_DB do not require redundant database queries.

#### Acceptance Criteria

1. WHEN a vector search is performed, THE Backend_System SHALL generate a cache key from the query vector and filter parameters
2. THE Backend_System SHALL store vector search results in Redis_Cache with a TTL of 1 hour
3. WHEN an identical vector search is requested, THE Backend_System SHALL return cached results within 20ms
4. THE Backend_System SHALL invalidate vector search cache entries when documents are added or deleted from the collection
5. THE Backend_System SHALL support cache warming for frequently accessed projects on startup

### Requirement 5: Session Management with Redis

**User Story:** As a user, I want my active chat sessions stored in fast memory, so that my conversation history loads instantly without database queries.

#### Acceptance Criteria

1. WHEN a user starts a chat session, THE Session_Store SHALL create a session entry in Redis_Cache
2. THE Session_Store SHALL store the last 50 messages per session with a TTL of 24 hours
3. WHEN a user sends a message, THE Backend_System SHALL retrieve chat history from Session_Store instead of Supabase_DB
4. WHEN a session expires or user logs out, THE Backend_System SHALL persist the full chat history to Supabase_DB
5. THE Backend_System SHALL support session migration between backend instances for horizontal scaling

### Requirement 6: Document Metadata Caching

**User Story:** As a backend developer, I want document metadata cached, so that repeated queries for document names and topics do not hit the database.

#### Acceptance Criteria

1. WHEN document metadata is queried, THE Backend_System SHALL check Redis_Cache before querying Supabase_DB
2. THE Backend_System SHALL cache document metadata (id, filename, topics, status) with a TTL of 6 hours
3. WHEN a document is updated or deleted, THE Backend_System SHALL invalidate the corresponding cache entry
4. THE Backend_System SHALL support batch cache retrieval for multiple documents in a single Redis operation
5. THE Backend_System SHALL preload document metadata for active projects into cache

### Requirement 7: Persistent Background Job System

**User Story:** As a system administrator, I want long-running operations processed by persistent background workers, so that jobs survive server restarts and API responses remain fast.

#### Acceptance Criteria

1. THE Backend_System SHALL integrate a background job system (Celery or ARQ) with Redis_Cache as the broker
2. THE Background_Worker SHALL process jobs from Job_Queue independently of the API server process
3. WHEN a job is enqueued, THE Job_Queue SHALL persist the job state to Redis_Cache
4. IF the Backend_System restarts, THE Background_Worker SHALL resume processing incomplete jobs from Job_Queue
5. THE Backend_System SHALL support at least 3 concurrent Background_Worker processes

### Requirement 8: Knowledge Graph Generation as Background Job

**User Story:** As a user, I want knowledge graph generation to happen in the background, so that my document upload completes quickly without waiting 30+ seconds for graph building.

#### Acceptance Criteria

1. WHEN document topics are generated, THE Backend_System SHALL enqueue a knowledge graph build job to Job_Queue
2. THE Background_Worker SHALL execute knowledge graph generation asynchronously
3. THE Backend_System SHALL return a job_id to the client immediately after enqueuing
4. THE Backend_System SHALL provide a job status endpoint returning (pending, processing, completed, failed)
5. WHEN knowledge graph generation completes, THE Backend_System SHALL update the job status to completed

### Requirement 9: Batch Notes Generation as Background Job

**User Story:** As a user, I want to generate notes for multiple topics without blocking, so that I can continue using the application while notes are being created.

#### Acceptance Criteria

1. WHEN batch notes generation is requested, THE Backend_System SHALL enqueue a background job for each note type
2. THE Background_Worker SHALL process notes generation jobs with a concurrency limit of 2 LLM calls
3. THE Backend_System SHALL track progress for each notes generation job (0-100%)
4. THE Backend_System SHALL store completed notes in Supabase_DB and notify the client via webhook or polling
5. IF a notes generation job fails, THE Background_Worker SHALL retry up to 3 times with exponential backoff

### Requirement 10: Job Status Tracking and Persistence

**User Story:** As a user, I want to see the status of my background jobs, so that I know when my knowledge graphs and notes are ready.

#### Acceptance Criteria

1. THE Job_Queue SHALL store job metadata (id, type, status, progress, created_at, started_at, completed_at) in Redis_Cache
2. THE Backend_System SHALL provide a GET /api/v1/jobs/{job_id} endpoint returning job status
3. THE Backend_System SHALL provide a GET /api/v1/jobs?project_id={id} endpoint listing all jobs for a project
4. WHEN a job completes, THE Backend_System SHALL persist the final status to Supabase_DB for historical tracking
5. THE Backend_System SHALL automatically clean up completed job records from Redis_Cache after 24 hours

### Requirement 11: Job Retry Logic and Failure Handling

**User Story:** As a system administrator, I want failed jobs to retry automatically with exponential backoff, so that transient errors do not require manual intervention.

#### Acceptance Criteria

1. WHEN a background job fails, THE Background_Worker SHALL retry the job up to 3 times
2. THE Background_Worker SHALL use exponential backoff delays (2s, 4s, 8s) between retries
3. IF a job fails after all retries, THE Background_Worker SHALL mark the job as failed and log the error
4. THE Backend_System SHALL store failure details (error message, stack trace, retry count) in the job record
5. THE Backend_System SHALL provide an admin endpoint to manually retry failed jobs

### Requirement 12: Distributed Locking for Concurrent Operations

**User Story:** As a backend developer, I want distributed locks to prevent race conditions, so that concurrent operations on the same resource do not corrupt data.

#### Acceptance Criteria

1. THE Backend_System SHALL implement distributed locks using Redis_Cache with automatic expiration
2. WHEN a knowledge graph build is triggered, THE Backend_System SHALL acquire a lock for the project_id
3. IF a lock cannot be acquired within 5 seconds, THE Backend_System SHALL return an error indicating the operation is already in progress
4. WHEN an operation completes, THE Backend_System SHALL release the distributed lock
5. THE Distributed_Lock SHALL automatically expire after 5 minutes to prevent deadlocks from crashed processes

### Requirement 13: Horizontal Scalability Support

**User Story:** As a system administrator, I want to run multiple backend instances behind a load balancer, so that the system can handle increased user load.

#### Acceptance Criteria

1. THE Backend_System SHALL store all state (sessions, cache, job queue) in external services (Redis_Cache, Supabase_DB)
2. THE Backend_System SHALL NOT use in-memory state that cannot be shared across instances
3. WHEN multiple backend instances are running, THE Backend_System SHALL coordinate using Distributed_Lock for exclusive operations
4. THE Backend_System SHALL support session affinity (sticky sessions) for WebSocket and SSE connections
5. THE Backend_System SHALL provide health check endpoints for load balancer health probes

### Requirement 14: Redis-Based Rate Limiting

**User Story:** As a system administrator, I want rate limiting enforced using Redis, so that rate limits work correctly across multiple backend instances.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL use Redis_Cache to track request counts per user per time window
2. THE Rate_Limiter SHALL enforce limits of 100 requests per minute per user for API endpoints
3. WHEN a user exceeds the rate limit, THE Backend_System SHALL return HTTP 429 with a Retry-After header
4. THE Rate_Limiter SHALL use sliding window algorithm for accurate rate limiting
5. THE Rate_Limiter SHALL support different rate limits for different endpoint categories (read vs write)

### Requirement 15: Connection Pooling for Supabase

**User Story:** As a backend developer, I want connection pooling for database connections, so that database operations do not suffer from connection overhead.

#### Acceptance Criteria

1. THE Backend_System SHALL configure a connection pool for Supabase_DB with a minimum of 5 and maximum of 20 connections
2. THE Backend_System SHALL reuse connections from the pool instead of creating new connections per request
3. THE Backend_System SHALL monitor connection pool metrics (active, idle, waiting)
4. WHEN the connection pool is exhausted, THE Backend_System SHALL queue requests with a timeout of 10 seconds
5. THE Backend_System SHALL log a warning when connection pool utilization exceeds 80%

### Requirement 16: Query Result Caching with TTL

**User Story:** As a backend developer, I want frequently accessed database queries cached, so that read-heavy operations do not overload the database.

#### Acceptance Criteria

1. THE Backend_System SHALL cache results of GET /api/v1/documents/{project_id} with a TTL of 5 minutes
2. THE Backend_System SHALL cache results of GET /api/v1/mcq/topics/{project_id} with a TTL of 10 minutes
3. WHEN a document is uploaded or deleted, THE Backend_System SHALL invalidate related query caches
4. THE Backend_System SHALL use cache-aside pattern (check cache, query DB on miss, populate cache)
5. THE Backend_System SHALL include cache metadata in response headers (X-Cache-Status: HIT or MISS)

### Requirement 17: Database Index Optimization

**User Story:** As a database administrator, I want optimized indexes on frequently queried columns, so that database queries execute in under 50ms.

#### Acceptance Criteria

1. THE Supabase_DB SHALL have an index on documents(project_id, upload_status)
2. THE Supabase_DB SHALL have an index on chat_messages(project_id, created_at)
3. THE Supabase_DB SHALL have an index on topic_relations(project_id, from_topic, to_topic)
4. THE Supabase_DB SHALL have an index on notes(project_id, user_id, created_at)
5. THE Backend_System SHALL log slow queries (>100ms) for performance analysis

### Requirement 18: Batch Operations for Efficiency

**User Story:** As a backend developer, I want batch operations for bulk data processing, so that API calls and database operations are minimized.

#### Acceptance Criteria

1. WHEN generating embeddings, THE Backend_System SHALL batch up to 50 text chunks per API call
2. WHEN inserting vectors into Vector_DB, THE Backend_System SHALL batch up to 100 points per upsert operation
3. WHEN querying document metadata, THE Backend_System SHALL use batch queries instead of N+1 queries
4. THE Backend_System SHALL support batch deletion of documents with a single API call
5. THE Backend_System SHALL log batch operation metrics (batch size, duration, throughput)

### Requirement 19: Request and Response Compression

**User Story:** As a user, I want API responses compressed, so that large payloads (like knowledge graphs) transfer faster over the network.

#### Acceptance Criteria

1. THE Backend_System SHALL support gzip compression for API responses larger than 1KB
2. WHEN a client sends Accept-Encoding: gzip, THE Backend_System SHALL compress the response
3. THE Backend_System SHALL include Content-Encoding: gzip header in compressed responses
4. THE Backend_System SHALL compress SSE (Server-Sent Events) streams for chat responses
5. THE Backend_System SHALL log compression ratio for responses larger than 10KB

### Requirement 20: Azure Application Insights Integration

**User Story:** As a system administrator, I want telemetry sent to Azure Application Insights, so that I can monitor performance, errors, and usage patterns.

#### Acceptance Criteria

1. THE Backend_System SHALL send request telemetry (duration, status code, endpoint) to Application_Insights
2. THE Backend_System SHALL send exception telemetry with stack traces to Application_Insights
3. THE Backend_System SHALL send custom metrics (cache hit rate, job queue length, embedding throughput) to Application_Insights
4. THE Backend_System SHALL send dependency telemetry for external calls (Redis_Cache, Vector_DB, Supabase_DB, LLM API)
5. THE Backend_System SHALL include Correlation_ID in all telemetry for request tracing

### Requirement 21: Structured Logging with Correlation IDs

**User Story:** As a developer debugging issues, I want structured logs with correlation IDs, so that I can trace a request across all services and log entries.

#### Acceptance Criteria

1. THE Backend_System SHALL generate a unique Correlation_ID for each incoming request
2. THE Backend_System SHALL include Correlation_ID in all log entries related to that request
3. THE Backend_System SHALL log in JSON format with fields (timestamp, level, correlation_id, message, context)
4. THE Backend_System SHALL propagate Correlation_ID to Background_Worker jobs
5. THE Backend_System SHALL include Correlation_ID in API response headers (X-Correlation-ID)

### Requirement 22: Distributed Tracing

**User Story:** As a system administrator, I want distributed tracing across services, so that I can identify performance bottlenecks in the request flow.

#### Acceptance Criteria

1. THE Backend_System SHALL create trace spans for each major operation (embedding, vector search, LLM call, database query)
2. THE Backend_System SHALL send trace data to Application_Insights using OpenTelemetry
3. THE Backend_System SHALL include span attributes (operation name, duration, status, resource)
4. THE Backend_System SHALL link child spans to parent spans using trace context propagation
5. THE Backend_System SHALL support trace sampling (100% for errors, 10% for successful requests)

### Requirement 23: Health Check and Readiness Probes

**User Story:** As a system administrator, I want health check endpoints, so that load balancers can route traffic only to healthy instances.

#### Acceptance Criteria

1. THE Backend_System SHALL provide GET /health endpoint returning 200 OK when the service is running
2. THE Backend_System SHALL provide GET /health/ready endpoint checking dependencies (Redis_Cache, Supabase_DB, Vector_DB)
3. WHEN any dependency is unavailable, THE Health_Endpoint SHALL return 503 Service Unavailable
4. THE Health_Endpoint SHALL respond within 1 second to avoid load balancer timeouts
5. THE Health_Endpoint SHALL include dependency status details in the response body

### Requirement 24: Auto-Scaling Configuration

**User Story:** As a system administrator, I want auto-scaling policies configured, so that the system automatically scales based on load.

#### Acceptance Criteria

1. THE Backend_System SHALL expose metrics (CPU usage, memory usage, request rate) for auto-scaling decisions
2. THE Backend_System SHALL support scaling from 2 to 10 instances based on CPU utilization > 70%
3. THE Backend_System SHALL support scaling based on custom metrics (job queue length > 50)
4. THE Backend_System SHALL gracefully handle shutdown signals (SIGTERM) to complete in-flight requests
5. THE Backend_System SHALL drain connections over 30 seconds during shutdown

### Requirement 25: Monitoring Dashboards and Alerts

**User Story:** As a system administrator, I want pre-configured monitoring dashboards and alerts, so that I am notified of issues before users are impacted.

#### Acceptance Criteria

1. THE Backend_System SHALL provide an Application_Insights dashboard showing request rate, error rate, and response time
2. THE Backend_System SHALL configure alerts for error rate > 5% over 5 minutes
3. THE Backend_System SHALL configure alerts for average response time > 1 second over 5 minutes
4. THE Backend_System SHALL configure alerts for Redis_Cache connection failures
5. THE Backend_System SHALL configure alerts for Background_Worker job failure rate > 10%

### Requirement 26: Performance Optimization for API Responses

**User Story:** As a user, I want API responses in under 300ms, so that the application feels fast and responsive.

#### Acceptance Criteria

1. THE Backend_System SHALL respond to GET /api/v1/documents/{project_id} in under 100ms (with cache hit)
2. THE Backend_System SHALL respond to POST /api/v1/chat/message in under 300ms (excluding LLM streaming time)
3. THE Backend_System SHALL respond to GET /api/v1/knowledge_graph/{project_id} in under 200ms (with cache hit)
4. THE Backend_System SHALL use async I/O for all database and external API calls
5. THE Backend_System SHALL log requests exceeding 500ms as slow requests for investigation

### Requirement 27: Zero Data Loss on Restart

**User Story:** As a system administrator, I want zero data loss when the backend restarts, so that in-progress operations resume correctly.

#### Acceptance Criteria

1. WHEN the Backend_System restarts, THE Job_Queue SHALL retain all pending and in-progress jobs
2. WHEN the Backend_System restarts, THE Background_Worker SHALL resume processing jobs from Job_Queue
3. WHEN the Backend_System restarts, THE Session_Store SHALL retain active sessions for 24 hours
4. THE Backend_System SHALL persist critical state (job status, progress) to Redis_Cache with persistence enabled
5. THE Backend_System SHALL log a recovery message on startup indicating the number of jobs resumed

### Requirement 28: Cache Warming on Startup

**User Story:** As a system administrator, I want frequently accessed data preloaded into cache on startup, so that the first requests after restart are fast.

#### Acceptance Criteria

1. WHEN the Backend_System starts, THE Backend_System SHALL preload document metadata for the 10 most active projects
2. WHEN the Backend_System starts, THE Backend_System SHALL preload topic lists for the 10 most active projects
3. THE Backend_System SHALL complete cache warming within 30 seconds of startup
4. THE Backend_System SHALL log cache warming progress and completion
5. IF cache warming fails, THE Backend_System SHALL continue startup and log a warning

### Requirement 29: Graceful Degradation

**User Story:** As a user, I want the system to continue functioning when Redis is unavailable, so that temporary cache failures do not cause complete outages.

#### Acceptance Criteria

1. WHEN Redis_Cache is unavailable, THE Backend_System SHALL log a warning and continue without caching
2. WHEN Redis_Cache is unavailable, THE Backend_System SHALL serve requests directly from Supabase_DB and Vector_DB
3. WHEN Redis_Cache is unavailable, THE Backend_System SHALL disable background job enqueuing and process operations synchronously
4. WHEN Redis_Cache recovers, THE Backend_System SHALL automatically reconnect and resume caching
5. THE Backend_System SHALL include a cache status indicator in health check responses

### Requirement 30: Configuration Management

**User Story:** As a system administrator, I want all performance settings configurable via environment variables, so that I can tune the system without code changes.

#### Acceptance Criteria

1. THE Backend_System SHALL support environment variables for Redis_Cache connection settings (host, port, password, db)
2. THE Backend_System SHALL support environment variables for cache TTL values (embedding_ttl, query_ttl, session_ttl)
3. THE Backend_System SHALL support environment variables for concurrency limits (max_workers, max_db_connections, max_embedding_concurrency)
4. THE Backend_System SHALL support environment variables for rate limiting (requests_per_minute, burst_size)
5. THE Backend_System SHALL validate configuration on startup and fail fast with clear error messages for invalid values
