# LuminaIQ Agent Notes

## Working Directories

- Treat `frontend/` and `backend/` as separate applications; there is no root task runner or workspace manifest.
- Run backend commands from `backend/`. Imports are rooted there, Pydantic loads `.env` relative to the current directory, and uploads create `temp/` relative to it.
- The React entrypoint is `frontend/src/main.tsx`, but most application code is JSX. The FastAPI entrypoint is `backend/main.py`; routes are assembled in `backend/api/v1/api.py`.

## Commands

Frontend, from `frontend/`:

```bash
npm ci
npm run dev
npm run lint
npm run build
```

- `npm run build` runs `tsc -b` before Vite.
- ESLint currently matches only `*.ts` and `*.tsx`; it does not check the repository's JSX application files.
- There is no frontend test script.

Backend, from `backend/`:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
.venv/bin/python -m unittest discover -s tests -v
```

- Backend regression tests use standard-library `unittest` under `backend/tests/`; `pytest` is not a dependency. Root `test_signed_url.py` is a live Supabase diagnostic and `test_ocr.py` has a hard-coded Windows path, so neither belongs in the automated suite.
- For a focused syntax check, run `.venv/bin/python -m py_compile path/to/file.py` from `backend/`.
- Docker production startup is `backend/Dockerfile` -> `backend/startup.sh`, which hard-codes four Gunicorn workers. This overrides the three-worker default in `settings.py` and the configurable path in `run.py`.

## Completion And Commits

- After a feature or fix is implemented and verified, commit all related meaningful changes. Split unrelated concerns into separate commits rather than combining them.
- Use Conventional Commits messages such as `feat(scope): ...`, `fix(scope): ...`, `test(scope): ...`, or `docs(scope): ...`.
- Before each commit, inspect `git status` and the staged diff, stage only the intended files, and never include secrets, generated artifacts, or unrelated worktree changes.
- Do not commit partial work or known failing verification unless the user explicitly requests a checkpoint commit.

## Runtime Topology

- The frontend authenticates with Supabase, exchanges that session for a custom backend JWT, and stores the app JWT in `localStorage`; changes to auth normally span `AuthContext.jsx`, `api.js`, `auth_service.py`, and `api/deps.py`.
- `frontend/src/api.js` hard-codes the production backend URL. `VITE_MAIN_API_URL` in `.env.example` currently has no effect; only the Supabase frontend variables are read from Vite env.
- Supabase is the relational store and file store. Qdrant uses one collection per project named `project_{project_id}`. LlamaIndex owns LLM, embedding, chunking, and RAG orchestration over the existing Qdrant payload schema; Azure OpenAI supplies the models and Azure CV handles OCR.
- Document processing runs extraction -> extracted-text storage -> chunking -> embeddings -> topics -> knowledge graph in `backend/services/document_service.py`.
- Background jobs, document progress, caches, queues, semaphores, and `asyncio.create_task` work are process-local. They are not shared across Gunicorn workers and do not survive restarts; do not describe them as durable or globally limited.

## Data And Security Constraints

- The backend Supabase client uses `SUPABASE_SERVICE_KEY`, which bypasses RLS. Every operation receiving a `project_id` or `document_id` must enforce ownership in backend code; authentication alone is insufficient.
- EventSource progress auth puts the JWT in a query parameter. Avoid logging request URLs or propagating this pattern to new endpoints.
- The current upload pipeline stores extracted text in the `texts` bucket and deletes the original temp file. The PDF URL path expects originals in the `documents` bucket, so preserve or explicitly resolve this mismatch when changing uploads or document viewing.
- The checked-in SQL is not a complete, ordered migration history. `supabase_schema_all_tables.sql` references a missing `supabase_schema_flashcards_mindmaps.sql`, while runtime code uses additional tables/columns not created by the available files. Confirm the live schema and add an explicit migration; do not treat the aggregate schema file as authoritative.
- Frontend environment files are ignored except `.env.example`; configure production values in Vercel and never commit credential values.

## High-Coupling Areas

- `frontend/src/pages/ProjectView.jsx` coordinates workspace navigation, uploads, SSE, chat, generation tools, and feature state. `frontend/src/api.js` combines transport, auth refresh, streaming, and all domain calls. Read both call sites before changing shared behavior.
- Many async backend paths call the synchronous Supabase client. Use `db.client.async_db` for blocking database/storage work; do not add `time.sleep` or direct `.execute()` calls inside async request paths.
- Keep changes compatible with explicit CORS origins in `backend/config/settings.py` and SPA rewrites in `frontend/vercel.json`.
