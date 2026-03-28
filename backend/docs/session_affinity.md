# Session Affinity Configuration for Horizontal Scaling

## Overview

This document describes the session affinity (sticky sessions) configuration required for horizontal scaling of the LuminaIQ backend. Session affinity ensures that requests from the same user session are routed to the same backend instance, which is critical for WebSocket and Server-Sent Events (SSE) connections.

**Key Point:** Regular REST API requests do NOT require session affinity because all session data is stored in Redis and accessible from any backend instance. Session affinity is ONLY needed for long-lived streaming connections (SSE/WebSocket).

## Session Storage Architecture

### Redis-Based Session Storage

All session data is stored in Redis, making sessions accessible from any backend instance:

- **Session Data**: Stored in Redis with key format `session:{session_id}`
- **Session TTL**: 24 hours
- **Message Limit**: Last 50 messages per session
- **Cross-Instance Access**: Any backend instance can read/write session data
- **No Instance Lock-In**: Sessions are NOT tied to specific backend instances

### Session Migration Support

Sessions are fully migratable across backend instances:

1. **Session ID in Request**: Client includes `session_id` in request payload or header
2. **Redis Lookup**: Backend instance retrieves session from Redis using session_id
3. **No Instance Lock-In**: Sessions are not tied to specific backend instances
4. **Automatic Failover**: If an instance fails, another instance can serve the session
5. **Instance Tracking**: Session metadata tracks which instance created/served the session (for debugging only)

### Instance Metadata

Each session includes metadata for debugging and monitoring:

```json
{
  "session_id": "sess_abc123",
  "user_id": "user_456",
  "project_id": "proj_789",
  "metadata": {
    "created_by_instance": "instance-1",
    "last_served_by_instance": "instance-2"
  }
}
```

This metadata helps track session migration patterns but does NOT affect functionality.

## Load Balancer Configuration

### Azure Load Balancer Settings

Configure the Azure Load Balancer with the following settings:

```yaml
load_balancer:
  algorithm: round_robin
  health_probe:
    endpoint: /health/ready
    interval: 10s
    unhealthy_threshold: 3
  timeout: 90s
  
  # Session affinity for SSE/WebSocket endpoints
  session_affinity:
    enabled: true
    cookie_name: lb-affinity
    cookie_ttl: 3600  # 1 hour
    
    # Endpoints requiring sticky sessions
    sticky_endpoints:
      - /api/v1/chat/stream
      - /api/v1/progress/*
```

### Session Affinity Rules

**Endpoints Requiring Sticky Sessions:**

1. **Chat Streaming** (`/api/v1/chat/stream`)
   - Uses Server-Sent Events (SSE)
   - Requires persistent connection to same instance
   - Cookie-based affinity with 1-hour TTL

2. **Progress Streaming** (`/api/v1/progress/*`)
   - Uses Server-Sent Events (SSE)
   - Streams real-time progress updates
   - Cookie-based affinity with 1-hour TTL

**Endpoints NOT Requiring Sticky Sessions:**

- All REST API endpoints (GET, POST, PUT, DELETE)
- Health check endpoints (`/health`, `/health/ready`)
- Job status endpoints (`/api/v1/jobs/*`)

### Cookie-Based Affinity

The load balancer uses a cookie named `lb-affinity` to track session affinity:

```http
Set-Cookie: lb-affinity=instance-1; Path=/; Max-Age=3600; HttpOnly; Secure
```

**Cookie Properties:**
- **Name**: `lb-affinity`
- **Value**: Backend instance identifier
- **Max-Age**: 3600 seconds (1 hour)
- **HttpOnly**: Yes (prevents JavaScript access)
- **Secure**: Yes (HTTPS only)
- **SameSite**: Lax (allows cross-site navigation)

## Backend Instance Configuration

### Instance Identification

Each backend instance should have a unique identifier for debugging and monitoring:

```bash
# Environment variable (recommended for production)
INSTANCE_ID=backend-instance-1

# Or auto-generated from hostname (default)
INSTANCE_ID=$(hostname)

# Or auto-generated from process ID (fallback)
# Automatically set to "instance-{pid}" if INSTANCE_ID not provided
```

**Note:** The instance ID is used ONLY for debugging and monitoring. It does NOT affect session routing or functionality.

### Session Metadata

The SessionManager automatically includes instance information in session metadata:

```python
# Automatically added by SessionManager
session_metadata = {
    "created_by_instance": os.getenv("INSTANCE_ID", f"instance-{os.getpid()}"),
    "last_served_by_instance": os.getenv("INSTANCE_ID", f"instance-{os.getpid()}")
}
```

This helps track:
- Which instance created the session
- Which instance last served the session
- Session migration patterns across instances
- Instance failover scenarios

## Testing Session Migration

### Test Scenario 1: Session Failover

**Purpose:** Verify sessions survive instance failures and can be served by other instances.

**Steps:**
1. Create session on instance A
   ```bash
   curl -X POST http://instance-a/api/v1/chat/session \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user_123", "project_id": "proj_456"}'
   # Response: {"session_id": "sess_abc123"}
   ```

2. Send message and verify response
   ```bash
   curl -X POST http://instance-a/api/v1/chat/message \
     -H "Content-Type: application/json" \
     -d '{"session_id": "sess_abc123", "message": "Hello"}'
   # Response: {"answer": "...", "session_id": "sess_abc123"}
   ```

3. Stop instance A (simulate failure)
   ```bash
   # Stop instance A or remove from load balancer
   ```

4. Send another message with same session_id to instance B
   ```bash
   curl -X POST http://instance-b/api/v1/chat/message \
     -H "Content-Type: application/json" \
     -d '{"session_id": "sess_abc123", "message": "Are you there?"}'
   # Response: {"answer": "...", "session_id": "sess_abc123"}
   ```

5. Verify chat history is preserved
   ```bash
   curl http://instance-b/api/v1/chat/history/sess_abc123
   # Response should include both messages
   ```

**Expected Result:** Instance B successfully serves the session created by instance A, with full chat history preserved.

### Test Scenario 2: Load Balancing Without Affinity

**Purpose:** Verify sessions work correctly when requests are distributed across instances.

**Steps:**
1. Create 10 concurrent sessions through load balancer
2. Verify sessions distributed across instances (check logs for instance_id)
3. Send messages to each session through load balancer
4. Verify each session maintains its history regardless of which instance serves it
5. Verify no cross-session data leakage

**Expected Result:** All sessions work correctly regardless of which instance serves each request.

### Test Scenario 3: SSE Connection Persistence

**Purpose:** Verify sticky sessions work for SSE streaming endpoints.

**Steps:**
1. Start SSE stream on instance A
   ```bash
   curl -N http://load-balancer/api/v1/chat/stream?session_id=sess_abc123
   # Should set lb-affinity cookie pointing to instance A
   ```

2. Verify cookie sets affinity to instance A
   ```bash
   # Check response headers for Set-Cookie: lb-affinity=instance-1
   ```

3. Send multiple messages during stream
   ```bash
   # All requests should route to instance A due to cookie
   ```

4. Verify all requests route to instance A (check logs)

5. Close stream and verify cookie expires

**Expected Result:** SSE stream maintains connection to same instance via sticky session cookie.

### Test Scenario 4: Instance Metadata Tracking

**Purpose:** Verify instance metadata is tracked correctly for debugging.

**Steps:**
1. Create session on instance A
2. Retrieve session from instance B
3. Check session metadata:
   ```json
   {
     "created_by_instance": "instance-1",
     "last_served_by_instance": "instance-2"
   }
   ```

**Expected Result:** Metadata correctly tracks which instances created and served the session.

## Monitoring and Debugging

### Session Metrics

Track the following metrics per instance:

- **Active Sessions**: Number of sessions currently active
- **Session Creates**: Rate of new session creation
- **Session Migrations**: Number of sessions served by different instance
- **Session Persistence**: Number of sessions persisted to Supabase

### Logging

Include session and instance information in logs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Session served",
  "session_id": "sess_abc123",
  "instance_id": "backend-instance-1",
  "user_id": "user_456",
  "project_id": "proj_789"
}
```

### Troubleshooting

**Problem**: Sessions not migrating between instances

**Solution**:
1. Verify Redis is accessible from all instances
2. Check Redis connection pooling configuration
3. Verify session_id is included in requests
4. Check Redis key expiration (TTL)

**Problem**: SSE connections dropping

**Solution**:
1. Verify load balancer timeout (should be > 90s)
2. Check session affinity cookie is set
3. Verify sticky session configuration
4. Check instance health probes

**Problem**: Session data loss

**Solution**:
1. Verify Redis persistence is enabled
2. Check session TTL configuration
3. Verify session persistence to Supabase on expiration
4. Check Redis memory limits

## Best Practices

1. **Always Include Session ID**: Client should include session_id in all requests
2. **Handle Session Expiration**: Client should handle 404 errors and create new session
3. **Persist Important Sessions**: Explicitly persist sessions before user logout
4. **Monitor Session Metrics**: Track session creation, migration, and persistence rates
5. **Test Failover**: Regularly test instance failover scenarios
6. **Use Health Checks**: Configure proper health checks for load balancer
7. **Set Appropriate TTLs**: Balance between memory usage and user experience

## Configuration Checklist

### Redis Configuration
- [ ] Redis accessible from all backend instances
- [ ] Redis connection pooling configured (min=10, max=50)
- [ ] Redis password/authentication configured
- [ ] Redis persistence enabled (AOF or RDB)
- [ ] Redis memory limits configured appropriately

### Load Balancer Configuration
- [ ] Load balancer configured with round-robin algorithm
- [ ] Health check endpoints implemented (`/health`, `/health/ready`)
- [ ] Session affinity enabled for SSE endpoints only
- [ ] Cookie-based affinity configured (`lb-affinity` cookie)
- [ ] Load balancer timeout set to > 90 seconds
- [ ] Unhealthy instance threshold configured (3 consecutive failures)

### Backend Instance Configuration
- [ ] All instances use same Redis connection string
- [ ] INSTANCE_ID environment variable set (optional, for debugging)
- [ ] Session persistence to Supabase implemented
- [ ] Session TTL configured (24 hours)
- [ ] Max messages per session configured (50)

### Monitoring and Observability
- [ ] Session metrics tracked in telemetry
  - Active sessions per instance
  - Session creation rate
  - Session migration count
  - Session persistence rate
- [ ] Instance metadata logged for debugging
- [ ] Session migration patterns monitored
- [ ] Failover scenarios tested and documented

### Testing and Validation
- [ ] Session migration tested (instance failover scenario)
- [ ] Load balancing tested (multiple concurrent sessions)
- [ ] SSE endpoints use sticky sessions
- [ ] REST endpoints work without sticky sessions
- [ ] Session data persists across instance restarts
- [ ] No session data loss during failover
- [ ] Instance metadata tracking verified

### Documentation
- [ ] Load balancer configuration documented
- [ ] Session affinity rules documented
- [ ] Instance identification strategy documented
- [ ] Monitoring and debugging procedures documented
- [ ] Troubleshooting guide created

## Verification Commands

### Check Redis Connectivity from All Instances

```bash
# On each backend instance
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping
# Expected: PONG
```

### Verify Session Storage in Redis

```bash
# Check session keys
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD KEYS "session:*"

# Get session data
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD GET "session:sess_abc123"
```

### Monitor Session Metrics

```bash
# Count active sessions
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD KEYS "session:*" | wc -l

# Check session TTL
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD TTL "session:sess_abc123"
```

### Test Load Balancer Health Checks

```bash
# Test health endpoint
curl http://load-balancer/health
# Expected: {"status": "healthy", "service": "lumina-backend"}

# Test readiness endpoint
curl http://load-balancer/health/ready
# Expected: {"status": "ready", "dependencies": {...}}
```

## References

- [Azure Load Balancer Documentation](https://docs.microsoft.com/en-us/azure/load-balancer/)
- [Redis Session Store Best Practices](https://redis.io/docs/manual/patterns/session-store/)
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [Example Environment Configuration](./session_affinity_example.env) - Complete example of environment variables for horizontal scaling

## Summary

**Key Takeaways:**

1. **Sessions are fully migratable** - All session data stored in Redis, accessible from any instance
2. **No instance lock-in** - Sessions are NOT tied to specific backend instances
3. **Session affinity ONLY for SSE/WebSocket** - Regular REST API requests work without sticky sessions
4. **Instance metadata for debugging** - Track which instances created/served sessions
5. **Automatic failover** - If an instance fails, another instance can serve the session
6. **Zero configuration needed in application** - Session migration works automatically via Redis

**Implementation Status:**
- ✅ SessionManager stores all data in Redis
- ✅ Sessions accessible from any backend instance
- ✅ Instance metadata tracked for debugging
- ✅ Session migration tested and verified
- ✅ Load balancer configuration documented
- ✅ Example environment configuration provided
