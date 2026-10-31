# Phase 0: Security and Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the cross-user data access holes, then give the backend a reproducible dev setup (uv + Docker Compose with pgvector), production hygiene and CI.

**Architecture:** One FastAPI dependency (`enforce_resource_access`) is attached at router level to every authenticated router. It reads project and document IDs from the path, the query string and the JSON/form body, and checks ownership through `projects.user_id`. Endpoints addressing rows by their own ID (saved tests, review cards) get explicit checks. uv becomes the dependency source of truth; Compose runs web + Postgres (pgvector) + optional Redis.

**Tech Stack:** FastAPI 0.115, supabase-py (service key), pytest with `tests/fake_supabase.py`, uv, Docker Compose, GitHub Actions.

**Spec:** `AGENTS.md` §5 Phase 0

## Global Constraints
- Work on branch `production-grade`. Supabase stays (AGENTS.md owner decision 2).
- A non-owner gets **404** (not 403), so the API doesn't reveal which IDs exist.
- Everything must run without Redis or `VECTOR_DATABASE_URL` set.
- No AI model identifiers in commits or comments. Plain comments that say *why*.

## Review Focus
1. A project ID in the JSON body of a POST (chat/stream, mcq/generate, notes/generate) owned by someone else → 404. Covered by a body test in Task 1.
2. `selected_documents` holding a document from another user's project, while `project_id` is the caller's own → 404. Covered in Task 1.
3. Nested IDs in batch bodies (`/knowledge-graph/analytics/record-batch` items) → each checked. Covered in Task 1.
4. An unknown or malformed UUID → 404, not 500. Covered in Task 1.
5. Multipart uploads with a `project_id` form field → checked without breaking the upload. Covered in Task 1.

---

### Task 1: Router-level access guard

**Files:**
- Create: `backend/api/access.py`
- Modify: `backend/api/v1/api.py` (add `dependencies=[Depends(enforce_resource_access)]` to the guarded routers)
- Test: `backend/tests/test_access.py`

**Interfaces:**
- Produces: `async def enforce_resource_access(request: Request, current_user: dict = Depends(get_current_user)) -> None`.
  Also `async def assert_project_owner(project_id: str, user_id: str) -> None` and
  `async def assert_documents_in_project(document_ids: list[str], user_id: str, project_id: str | None) -> None`, both raising `HTTPException(404)`.
- Guarded routers: projects, documents, chat, mcq, evaluation, notes, learning, study_modes, lessons, knowledge_graph, user_data, flashcards, mindmaps, jobs, books.
- **Not** guarded (they have their own checks or are public): auth, billing, webhook, progress, institutions, platform.
- ID keys: project keys `{"project_id"}`. Document keys `{"document_id", "selected_documents", "document_ids"}`.
  Found in path params, query params and the JSON body (recursively through dicts and lists) or the form body.

- [ ] Step 1: write `tests/test_access.py`.
  Build an app with the real routers, override `get_current_user` to return user B, and seed the fake Supabase with user A's project `PA` and document `DA` and user B's project `PB`. Tests:
  - `test_path_project_of_other_user_404`: `GET /api/v1/chat/history/PA` → 404
  - `test_every_path_route_with_project_id_404`: iterate every route of the guarded routers whose path contains `{project_id}` or `{document_id}`, fill in A's IDs, call as B → status 404
  - `test_body_project_of_other_user_404`: `POST /api/v1/chat/stream` with `{"project_id": PA, "message": "hi"}` → 404
  - `test_selected_documents_from_other_project_404`: `{"project_id": PB, "selected_documents": [DA], "message": "x"}` → 404
  - `test_nested_batch_ids_checked`: `POST /api/v1/knowledge-graph/analytics/record-batch` with an item carrying `project_id: PA` → 404
  - `test_malformed_id_404`: `GET /api/v1/chat/history/not-a-uuid` → 404
  - `test_owner_passes_guard`: the guard called directly with user A and `PA` returns `None`
  - `test_query_project_id_checked`: `DELETE /api/v1/documents/DA?project_id=PA` as B → 404
- [ ] Step 2: run `cd backend && uv run pytest tests/test_access.py -q`. Expected: failures (no guard yet).
- [ ] Step 3: implement `api/access.py`.
  - Collect IDs, then batch one `projects` lookup (`select id,user_id ... in_("id", ids)`) and one `documents` lookup (`select id,project_id`).
  - Cache confirmed `(user, project)` pairs in-process for 60 s.
  - Read the body only when the content type is JSON or form. FastAPI has already read and cached it on the same `Request`.
  - Wire it into `api/v1/api.py`.
- [ ] Step 4: run the full suite with `uv run pytest -q`. Expected: all pass, including the 28 existing tests.
- [ ] Step 5: commit `fix(security): enforce project/document ownership on every authenticated router`.

### Task 2: Rows addressed by their own ID
**Files:** modify `services/mcq_service.py`, `services/evaluation_service.py`, `services/learning_service.py`, `api/v1/endpoints/{mcq,evaluation,learning,progress}.py`. Test: `tests/test_access.py`.
- `get_saved_test(test_id, user_id)` / `delete_saved_test(test_id, user_id)` in the MCQ and evaluation services: load the row's `project_id`, then call `assert_project_owner`.
- `spaced_repetition.record_review(card_id, quality, user_id)` / `delete_card(card_id, user_id)`: filter `.eq("user_id", user_id)`. A missing row → 404.
- `progress.stream_document_progress`: after decoding the token, call `assert_documents_in_project([document_id], user_id, None)`.
- [ ] Tests (written first, failing, then passing): `test_saved_mcq_test_other_user_404`, `test_saved_subjective_test_other_user_404`, `test_delete_review_card_other_user_404`, `test_progress_stream_other_user_404`.
- [ ] Commit `fix(security): check ownership for saved tests, review cards and progress stream`.

### Task 3: uv project
**Files:** create `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version` (`3.11`). Regenerate `backend/requirements.txt` with `uv export --no-hashes --no-dev`.
- The runtime deps are exactly today's `requirements.txt`. The dev group has `pytest`.
- [ ] Verify: `uv sync && uv run pytest -q` passes, and `uv run run.py` starts (`curl localhost:8000/health` returns 200).
- [ ] Commit `build: manage backend dependencies with uv`.

### Task 4: Docker Compose dev stack
**Files:** create `docker-compose.yml` (repo root), `.env.example` (root, every setting from `config/settings.py` plus `VECTOR_DATABASE_URL`, `REDIS_URL`), and `backend/.dockerignore`. Modify `backend/Dockerfile` to install with uv (`uv sync --frozen --no-dev`) and run `uv run run.py`.
- Services:
  - `web`: builds `backend/`, `env_file: .env`, port 8000, healthcheck `/health`
  - `postgres`: `pgvector/pgvector:pg16`, named volume, healthcheck `pg_isready`
  - `redis`: `redis:7-alpine`, `profiles: ["redis"]`
- `web` defaults `VECTOR_DATABASE_URL=postgresql://lumina:lumina@postgres:5432/lumina`.
- [ ] Verify: `docker compose config` is valid. If Docker is available, `docker compose up -d postgres web` gives a healthy `/health`.
- [ ] Commit `build: docker compose dev stack with pgvector and optional redis`.

### Task 5: Production hygiene
**Files:** modify `backend/main.py`, `backend/config/settings.py`, `backend/utils/logger.py`. Test: `backend/tests/test_app_health.py`.
- Remove the `DEBUG:` prints and the `log_all_requests` print middleware.
- Add a request-id middleware: it reads `X-Request-ID` or generates one, sets it on the response, and includes it in log records.
- `GET /ready` checks Supabase (a cheap select) and, if set, `VECTOR_DATABASE_URL` and `REDIS_URL`. It returns 200 `{"status":"ready","checks":{...}}` or 503.
- `settings.validate_production()` runs at startup: when `ENVIRONMENT == "production"` and `SECRET_KEY`, `WEBHOOK_SECRET` or `MAIN_API_WEBHOOK_SECRET` still hold their defaults, it raises `RuntimeError` naming them.
- [ ] Tests first:
  - `test_health_ok`
  - `test_response_has_request_id` (echoes the incoming `X-Request-ID`)
  - `test_ready_503_when_supabase_fails`
  - `test_validate_production_rejects_default_secrets`
  - `test_validate_production_allows_dev_defaults`
- [ ] Commit `feat: request ids, readiness check, fail fast on default secrets`.

### Task 6: Cleanup and CI
- Delete `backend/main_backup.py`, `fix_db_calls.py`, `fix_execute.py` and `measure_time.py` (grep confirms nothing imports them).
- Create `.github/workflows/backend-tests.yml`: on push/PR touching `backend/**`, `astral-sh/setup-uv`, `uv sync`, `uv run pytest -q`.
- [ ] Verify the full suite passes. Commit `chore: remove dead scripts, run backend tests in CI`.
