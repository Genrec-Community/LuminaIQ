# Phase 1: Scale Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Any number of web and worker processes can run side by side. A restart loses no work. One user can't flood the AI endpoints.

**Architecture:**
- **Durable job queue** in Postgres (`jobs` table, `FOR UPDATE SKIP LOCKED`). The web process enqueues and a worker loop runs handlers.
  The same loop also runs inside the web process when `WORKER_INLINE=true` (default), so `uv run run.py` alone still does everything in dev and on a single box.
- **Upload handoff:** the uploaded file is staged in Supabase Storage before queueing. If staging fails, the job is pinned to the host that has the temp file.
- **Cache:** `utils/cache.py` keeps its API, with storage in Redis when `REDIS_URL` is set and Postgres otherwise, plus a small in-process layer.
- **Rate limits:** fixed-window counters (Redis or Postgres) through one FastAPI dependency.

**Tech Stack:** psycopg pool (`db/pg.py`), Postgres 16, optional redis-py, FastAPI dependencies.

**Spec:** `AGENTS.md` §5 Phase 1, with the owner's change: Supabase is for sign-in and files only, and all data is in `DATABASE_URL`.

## Global Constraints
- Works with no Redis. Works as a single process (`WORKER_INLINE=true`) and as separate web + worker processes.
- Jobs are idempotent per `dedupe_key`, retried with backoff up to `max_attempts`, and reclaimed when their heartbeat is older than `JOB_STALE_SECONDS`.
- Response shapes of the existing endpoints don't change.

## Review Focus
1. Two workers claim at the same moment → each job runs once. Covered by `test_claim_is_exclusive`.
2. A worker dies mid-job (no heartbeat) → the job is retried by another worker. Covered by `test_stale_job_is_reclaimed`.
3. A host-pinned upload job is never claimed by another host. Covered by `test_pinned_job_only_claimed_by_its_host`.
4. The same document is queued twice (double tap) → one job. Covered by `test_dedupe_key_returns_existing_job`.
5. A user hitting chat past the limit → 429 with `Retry-After`, while other users are unaffected. Covered by `test_rate_limit_is_per_user`.

---

### Task 1: Queue tables and queue API
**Files:** create `db/schema/0002_jobs_cache_rate_limits.sql`, `utils/job_queue.py`. Add `PgClient.fetch(query, params) -> list[dict]` to `db/pg.py`. Test: `tests/test_job_queue.py` (real Postgres).
- `jobs(id uuid pk, kind text, payload jsonb, status text check in (queued,running,done,failed), attempts int, max_attempts int, run_after timestamptz, pinned_host text, locked_by text, heartbeat_at timestamptz, result jsonb, error text, user_id uuid, dedupe_key text unique where status in (queued,running), created_at, updated_at, finished_at)`; index `(status, run_after)`.
- `cache_entries(key text pk, value jsonb, expires_at timestamptz)`.
- `rate_limit_counters(key text, window_start timestamptz, count int, pk(key, window_start))`.
- API (sync functions over the pool, called through `async_db`):
  - `enqueue(kind, payload, *, user_id=None, dedupe_key=None, max_attempts=3, pinned_host=None) -> dict`
  - `claim(worker_id, host, kinds) -> dict | None`
  - `heartbeat(job_id, worker_id)`
  - `complete(job_id, result)`
  - `fail(job_id, error) -> dict` (requeues with backoff `min(300, 10·2^attempts)` s until `max_attempts`)
  - `reclaim_stale(stale_seconds) -> int`
  - `get(job_id) -> dict | None`
  - `list_for_user(user_id, limit) -> list[dict]`
- [ ] Tests:
  - `test_enqueue_and_claim`
  - `test_claim_is_exclusive` (two threads, 20 jobs, each claimed once)
  - `test_fail_retries_then_fails`
  - `test_stale_job_is_reclaimed`
  - `test_pinned_job_only_claimed_by_its_host`
  - `test_dedupe_key_returns_existing_job`
  - `test_complete_stores_result`

### Task 2: Worker loop and handlers
**Files:** create `utils/worker.py` (registry plus `Worker` with `concurrency`, a heartbeat task and graceful stop), `worker.py` (entrypoint: `uv run worker.py`), `services/jobs.py` (handler registrations). Modify `main.py` (start an inline worker on startup when `WORKER_INLINE`, stop it on shutdown).
- Handlers:
  - `process_document`: download the staged file, or use the pinned local path, then `document_service.process_document`; delete the staged copy afterwards
  - `book_clone`: `book_service._background_clone`
  - `reindex_document`: `document_service._reindex_from_storage`
- [ ] Tests: `test_worker_runs_handler_and_completes`, `test_worker_retries_failed_handler`, `test_unknown_kind_fails_job`.

### Task 3: Move call sites onto the queue
**Files:** `api/v1/endpoints/documents.py` (upload, upload-from-storage, retry), `services/document_service.py` (`stage_upload`, reindex enqueue), `services/book_service.py` (clone enqueue), `api/v1/endpoints/jobs.py` (status / my-jobs / poll from the `jobs` table; submit only accepts registered kinds).
- `document_service.stage_upload(document_id, project_id, temp_path, filename) -> dict` returns `{"staged": "uploads/<project>/<doc><ext>"}` or `{"local_path": path}` with `pinned_host`.
- [ ] Tests: `test_upload_enqueues_process_document_job` (fake storage), `test_staging_failure_pins_to_host`.

### Task 4: Shared cache
**Files:** rewrite `utils/cache.py` (keeping `content_cache`, `get/set/delete/clear_prefix`). Backends: `RedisCache`, `PostgresCache`, and an in-process L1 (≤ 5 s). Test: `tests/test_cache.py`.
- [ ] Tests: `test_set_get_expire`, `test_clear_prefix`, `test_shared_between_two_instances`.

### Task 5: Rate limits
**Files:** create `utils/rate_limit.py` (`rate_limit(bucket: str)` dependency). Settings `RATE_LIMIT_CHAT_PER_MIN=20`, `RATE_LIMIT_GENERATE_PER_MIN=10`, `RATE_LIMIT_UPLOAD_PER_HOUR=30`, `RATE_LIMITS_ENABLED=true`.
Apply it to:
- chat: `/chat/message`, `/chat/stream`
- generate: mcq, notes, flashcards, mindmap, lessons, cram, visualize, evaluation generate, jobs submit
- upload: `/documents/upload`, `/upload-url`, `/upload-from-storage`
- [ ] Tests: `test_rate_limit_returns_429_with_retry_after`, `test_rate_limit_is_per_user`, `test_rate_limit_disabled`.

### Task 6: Concurrency settings, compose worker, N+1
- `DB_THREADS` (default 32) sizes the `async_db` executor.
- Compose: `worker` service (same image, `uv run worker.py`, `WORKER_INLINE=false` on web).
- `rag_service`: one batched filename lookup per answer instead of one query per chunk.
- [ ] Verify the full suite passes and compose config is valid.

### Task 7: Load test
**Files:** `backend/scripts/loadtest/locustfile.py` and `README.md`. Scenario: list projects → open a book → chat history → settings → gamification → enqueue (the LLM-free paths; chat streaming needs real keys).
- [ ] Run at 50 and 200 users against local compose and record p50/p95/error rate in AGENTS.md §8.
