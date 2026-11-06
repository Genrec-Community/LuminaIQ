# AGENTS.md: LuminaIQ production-grade

The working guide for any agent or developer building on the `production-grade` branch.
It records **what we are building, why, what is already decided, and the order of work**.
Read it fully before you change anything.

> Decisions were settled with the product owner on 2026-10-31.
> "Owner decision" means don't change it without asking. "Builder's call" means it
> was a reasonable default; change it if you find a better reason, and note it here.

---

## 1. Mission

LuminaIQ must make **every learner study**, from a Class 6 child to a PhD researcher.
The same product adapts to who is using it:

- **Answers** change with the learner's level: simpler words and step-by-step for kids, dense and technical for research.
- **The app itself** changes: fewer, bigger, guided tools for school students and the full toolset for advanced learners.
- **Tools** are controlled by people responsible for the learner: the platform admin per level, and the institution admin per class.

Anti-goals (a failure even if it "works"):
- A Class 6 student sees a cluttered app or gets a wall of jargon.
- Costs grow linearly with users because nothing is cached or shared.
- One user can read another user's data.
- Answers invent "facts from the book" that aren't in the book.

---

## 2. How to work in this repo

- **Branch:** all work goes to `production-grade`. Don't push to `main`.
- **Skills:** project skills live in `.claude/skills/`, from superpowers and grill-me.
  For each phase: `brainstorming` (only if scope is unclear) → `writing-plans` → `test-driven-development` →
  `verification-before-completion` → `requesting-code-review`. Use `systematic-debugging` for any bug.
- **Backend:** FastAPI, Python 3.11, in `backend/`. Run locally (after Phase 0) with `docker compose up`,
  or `uv run run.py` (web) and `uv run worker.py` (background worker).
- **Frontend:** React 19 + Vite + Tailwind 4, in `frontend/`. `npm run dev`, `npm run build`, `npm run lint`.
  Android is a Capacitor wrapper around the same build (`ANDROID.md`).
- **Landing site:** `frontend/website/` (Next.js). Leave its design alone. Decorative pieces belong there, not in the app.
- **Tests:** `cd backend && uv run pytest`. `tests/fake_supabase.py` fakes Supabase. Add tests for every
  backend change. RAG changes must also pass the eval in §6 (Phase 3).
- **Migrations:**
  - One database (`DATABASE_URL`): `backend/db/schema/NNNN_name.sql`, applied in order on startup by `db/migrate.py`
    (or `uv run python -m db.migrate`). `0001_init.sql` is the fresh-start schema; the latest is `0010_analytics.sql`, so the next file is `0011_`.
    Never edit an applied file; add a new one.
  - `backend/db/supabase_auth.sql` is the only SQL that runs in Supabase (the Google sign-up allowlist on `auth.users`).
- **Database access:** services call `get_supabase_client().table(...)` / `.rpc(...)` as before. That now goes to our
  Postgres through `db/pg.py` (same call shape as supabase-py). `.auth` and `.storage` still go to Supabase.
  New code may use the same builder; anything it can't express goes in a SQL function (called with `.rpc`).
- **Style:** small focused modules, and plain comments that say *why*. Every new feature works when optional parts are off
  (no Redis, no cloud OCR, no vision model) and degrades gracefully.
- **Never** commit secrets or `.env` files. Never put AI model identifiers in commit messages or code comments.

---

## 3. The system today (as of `main` @ 635db37)

| Area | Today | Problem |
| --- | --- | --- |
| Hosting | Azure Container Apps `luminaiq-api` (deployed from `main` by `azure.yml`); website on Azure Static Web Apps. (Render before 2026-10-30.) | Stays on Azure (owner decision 1); the app database moves to Azure Database for PostgreSQL. |
| Main DB / auth / files | Supabase for everything, via the service key, so access rules were bypassed | Now: data in our own Postgres (`DATABASE_URL`), Supabase only for sign-in and files. Endpoints check ownership in `api/access.py`. |
| Vectors | Qdrant, one collection per project (`services/qdrant_service.py`) | Separate server. No keyword search alongside. |
| RAG chat | `services/rag_service.py`: LangChain `create_retrieval_chain`, pure dense top-5 | Follow-ups ("explain that more") search with the raw text and retrieve junk. No rerank, no hybrid, no eval. |
| Study-tool retrieval | `services/retrieval.py`: vector, falling back to keyword over stored text | Reasonable. Make it share the new hybrid search. |
| Cache | `utils/cache.py`: in-process dict | Not shared across processes. Lost on restart. Only the project summary is persisted. |
| Background work | `utils/background_jobs.py`, `utils/progress_manager.py`, `utils/embedding_queue.py`: in-memory | Jobs and progress are lost on restart and invisible to other processes. |
| Memory | Last 12 messages of the project chat + static profile from settings | No cross-session or cross-book memory. Long chats forget everything. (Fixed in Phase 5.) |
| Levels | `ageGroup` (teen/young/adult/mature) + `selfLevel` (beginner/intermediate/advanced) | Doesn't map to school standards. Barely changes answers. |
| Tool access | `services/plans.py` + `usage_service.metered()` gate by **plan** only | No per-level or per-class control. |
| Maths | `react-markdown` + `remark-gfm` only | LaTeX shows as raw `$...$`. (Fixed in Phase 6.) |
| Image input | None in chat | n/a (Added in Phase 6.) |
| Gamification | `services/gamification_service.py`: XP per action, badges, streak | Rewards activity, not learning. Easy to farm. Same for every age. (Fixed in Phase 7.) |
| App clutter | `MemoryCurve` (`.lumina-curve`) in Dashboard, AdaptivePlan, mobile Home | Landing-page decoration inside the app. |
| Chat streaming | Plain text stream, sources appended as `__SOURCES__:<json>` | Fragile. No room for metadata like "outside the book". |

---

## 4. Decisions

### Owner decisions
1. **Scale target:** design for horizontal scaling. We build software that is stateless per process and configured by environment variables.
   **Hosting (owner, updated 2026-11-06): Azure.** The API runs on Azure Container Apps (`luminaiq-api`, autoscaling 1–10),
   the website on Azure Static Web Apps (`luminaiq-web`), and the app database is Azure Database for PostgreSQL (`luminaiq-db`).
   (An earlier plan said AWS EC2; the owner chose Azure, where production already runs.)
2. **Supabase is only for sign-in (and, for now, file storage).** All data lives in our own Postgres (`DATABASE_URL`):
   Docker in development, Azure Database for PostgreSQL in production. Moving files off Supabase Storage is a later project.
   **Updated 2026-11-05 (owner): the live data is migrated, not dropped.** Production already has real users, books,
   paid plans and schools in Supabase. `backend/scripts/migrate_from_supabase.py` copies every table into the new
   database (see `AZURE_DATABASE_MIGRATION.md`).
3. **Docker Compose is for local development only.** It runs the backend (web + worker) plus Postgres with pgvector, and Redis (optional).
   Production never runs the compose file or its Postgres: it deploys the backend image and uses Azure Database for PostgreSQL.
   The backend also runs directly with `uv run run.py`. The frontend, the OCR setup and the Render config stay as they are.
4. **Qdrant is replaced by pgvector** in the **same Postgres** (`DATABASE_URL`):
   Docker in development, **Azure Database for PostgreSQL** in production. Old vectors are not copied: the data migration queues a
   `reindex_document` job per book and the worker rebuilds passages from the stored text. Remove Qdrant code completely.
5. **Redis is optional.** Everything must work without it.
6. **OCR stays as it is now.**
7. **AI provider:** any **OpenAI-compatible API**, with **two models**:
   - **`BIG_LLM`:** interactive live demos (Visual Lab simulations), Deep mode answers, Deep-mode multi-step retrieval,
     and image input for paid users.
   - **`SMALL_LLM`:** everything else (normal chat, quizzes, flashcards, notes, mindmaps, query rewriting, memory
     extraction, summaries, moderation), and **every request from free users**, Deep mode included.

   Each model has its own `*_MODEL`, `*_BASE_URL` and `*_API_KEY`, so they can come from different providers.
   These replace `LLM_LIGHT_MODEL` / `LLM_DEEP_*` / `LLM_TIER_MODELS`. All routing lives in **one** function
   (`resolve_model(task, user)`). **Embeddings come from an API only** (no self-hosted models).
7a. **RAG:** use current best practice. The owner will judge answer quality later.
   **Reranking is optional**: it switches on automatically when its API key is set (`RERANK_API_KEY`, `RERANK_BASE_URL`,
   `RERANK_MODEL`) and is skipped otherwise. Citations stay.
8. **Learner levels:** `school` (Class 5–10), `higher_secondary` (Class 11–12), `ugpg` (UG/PG), `research` (PhD/Research), `general`.
   - Individual users pick their level at sign-up (onboarding).
   - **Institution students get their level from their class and can't change it.** A Class 8 student stays in Class 5–10.
9. **Tool control:**
   - The **platform admin** (owner) sets which tools each level gets, on a **separate admin page per level**.
   - **Institution admins** turn tools on or off **per class**, only within what the platform allows for that level and what the plan includes.
   - Individual users get the platform defaults for their level.
10. **Hints-first mode:** optional. A toggle in the chat menu, **off by default**.
    Institution admins set it per class: `always_on` / `always_off` / `student_choice`.
11. **Outside-the-book answers:** when the book doesn't cover a question (text or photo), answer from the model's own
    knowledge with a clear **"Not from your book"** label. Institution admins can turn this off per class.
12. **Image input:** students photograph a question or diagram in chat and get it explained, using the book first and then general knowledge (rule 11).
13. **Memory:** per student, three layers (Phase 5).
    - **Automatic memory** (the AI noting facts from chats) is for **Class 11 and above only**. Class 5–10 memory comes only from quiz and mastery data.
    - **Memory across books:** the user decides, with a setting.
    - **Teachers** see a student's progress (mastery, stuck topics, mistakes) but **never their chats or memory notes**.
    - **Chats** stay until the student deletes them. Memory notes unused for **6 months** fade out.
13a. **Cost:**
    - Quizzes and flashcards for shared-library and class books come from a **shared pool** per book + topic + level.
      Each student gets a random selection with shuffled options, and the pool grows only when a student runs out.
    - **Cached chat answers** apply only to **first questions on shared books**, served in a neutral voice.
      Personal books and follow-ups always get fresh, in-character answers.
    - Every AI call is tracked (tokens, cost, cache hit, latency) in our own table and admin dashboard, with **optional Langfuse** turned on by settings.
14. **Child safety:** stricter guardrails for the `school` level now. Parental consent is a later item.
15. **Remove `MemoryCurve` and similar landing-style decoration from the app.** Keep it on the landing page.
16. **Order of work:** Phase 0 → 7 in §5.

### Builder's calls (reviewable)
- **One Docker image, two commands:** `web` (`uv run run.py`, with gunicorn + uvicorn workers in production) and `worker` (`uv run worker.py`).
- **One Postgres holds everything:** app tables, vectors, the job queue, LLM cache and usage telemetry.
- **Job queue on Postgres** (`SELECT ... FOR UPDATE SKIP LOCKED`). Redis, when set, is used only for the hot cache, rate limits and progress pub/sub.
- **Driver:** `psycopg` 3 with a connection pool (`db/pg.py`), migrations as numbered SQL files. No ORM.
- **uv for Python deps:** `backend/pyproject.toml` + `uv.lock` is the source of truth. `requirements.txt` is exported from it so the existing Dockerfile and Render keep working.
- **Drop LangChain from the chat path.** Direct calls are simpler, easier to cache and easier to order for provider prompt caching.
  Keep `langchain-text-splitters` only if still useful for chunking.
- **The chat stream becomes JSON events** (`token`, `sources`, `meta`, `done`, `error`). The frontend parser and the Android build are updated together.
- **Any user without a level** (e.g. accounts created before this work) picks one in a blocking one-question modal. No other legacy handling.
- **Deep mode multi-step retrieval:** splits a complex question into 2–4 sub-questions, searches for each, then answers with `BIG_LLM`. Normal chat uses a single search.
- **Study content is generated on demand and cached.** Pre-generation (via the provider's batch API where available) applies only to shared-library and class books and is off by default (`PREGENERATE_SHARED=false`).
- **Citations open the book at the cited page**, with the passage highlighted (`DocumentReader`).
- **Memory across books defaults to on.** The setting lets the user turn it off.
- **The `general` level** gets plain-language answers with the `ugpg` toolset by default.
- **Gamification design:** see Phase 7.
- **Android (Capacitor)** only needs to keep working; a separate phone app comes later. The web app must work well on phone browsers.

---

## 5. Roadmap

Each phase ends in a working, deployable state. Within a phase, write a plan (`writing-plans` skill) before coding.

### Phase 0: Security and foundations (do first)
1. **Access control audit.** Add a reusable dependency, e.g. `require_project_access(project_id, user)`, and use it on
   **every** endpoint that takes a `project_id` / `document_id` / class id.
   - Confirmed hole: `api/v1/endpoints/chat.py` (`/history/{project_id}`, `/message`, `/stream`, `/summary`) never checks ownership.
   - Sweep every endpoint file and add a test per endpoint proving that user B gets 403/404 on user A's resources.
2. **Docker Compose** at the repo root: `web`, `worker`, `postgres` (image `pgvector/pgvector:pg16`), `redis` (in a compose **profile**, so it's off by default).
   Add `.env.example` covering every setting in `config/settings.py`, plus `DATABASE_URL` and `REDIS_URL` (optional).
3. **uv migration:** `pyproject.toml` + `uv.lock`, and `uv run run.py` works. Update the Dockerfile to install with uv. Keep a working `requirements.txt` export.
4. **Production hygiene:**
   - Remove the `DEBUG` prints in `main.py` and the per-request `print` middleware. Use structured logging with a request id.
   - Split `/health` (liveness) from `/ready` (checks the database, Supabase sign-in, Redis if set).
   - Fail fast at startup in production if `SECRET_KEY` / webhook secrets are still the defaults.
5. **Remove the dead files** `main_backup.py`, `fix_db_calls.py`, `fix_execute.py` and `measure_time.py` once confirmed unused.

**Done when:** `docker compose up` gives a working app against Supabase plus local pgvector, every endpoint has an ownership test, and CI runs pytest.

### Phase 1: Scale foundations
1. **Stateless processes.** Move these out of process memory:
   - background jobs → Postgres queue + `worker.py`
   - upload / OCR / embedding progress → Postgres rows (Redis pub/sub when available, polling otherwise)
   - `utils/cache.py` → a `Cache` interface with Redis and Postgres/in-process backends
2. **The worker** runs OCR, parsing, embedding, topic/graph generation and the heavy study-tool generation. The web process only enqueues.
   Jobs are retryable and idempotent, with a visible status. A stuck job gets reclaimed after a timeout.
3. **Rate limits:** per user and per IP, on chat, uploads and generation. Redis token bucket when available, otherwise a Postgres-backed fallback.
   This is separate from plan quotas in `usage_service`.
4. **Concurrency:** gunicorn + uvicorn workers in production (`run.py` already supports `GUNICORN=1`).
   Make the thread-pool size for `async_db` configurable (the Postgres pool size is `DB_POOL_SIZE`).
   Remove N+1 queries (e.g. the per-chunk document-name lookups in `rag_service.py`).
5. **Load test:** a `k6` or `locust` script in `backend/scripts/loadtest/` covering login → open book → chat stream → quiz.
   Record p95 latency and errors at 50/200/500 virtual users in this file.

**Done when:** two web processes and one worker run together under compose, a restart loses no jobs, and the load-test numbers are recorded.

### Phase 2: Learner levels, tool control and a simpler UI
1. **Data (`db/schema/NNNN_levels_and_tools.sql`):**
   - user setting `studyLevel` (one of the 5 levels)
   - `institution_classes.level`, `institution_classes.hint_mode`, `institution_classes.allow_outside_book`
   - `level_tool_policies(level, tool, enabled)`: platform defaults
   - `class_tool_policies(class_id, tool, enabled)`: institution overrides
2. **Tool catalog** (one source of truth, `backend/services/tools_catalog.py`, served by `GET /levels/catalog`).
   Keys are the app's tab ids: `chat`, `deep`, `image`, `qa`, `quiz`, `flashcards`, `notes`, `mindmap`, `knowledge`,
   `path`, `cram` (Exam Tonight), `power` (Power Hour), `lab` (Visual Lab), `analytics`, `pomodoro`, `bookstore`,
   `companion`, `leaderboard`.
3. **Effective tools** = platform level defaults, narrowed by class overrides (institution students only).
   Plan quotas (`services/plans.py`) stay a separate check on top (builder's call: one rule system each).
   - Computed in one backend function and cached per user.
   - **Enforced on the backend** (403 with a friendly message) and **hidden on the frontend**.
   - `GET /me/tools` returns the effective set.
4. **Platform admin UI:** in `pages/Platform.jsx`, a "Levels & tools" section with **one page per level** (`/platform/levels/:level`):
   toggles per tool, the default hint mode, outside-book on/off, and a preview of what that level's home screen looks like.
5. **Institution admin UI:** in `pages/Institution.jsx`, per class: level, tool toggles (only platform-allowed ones are shown), hint mode, and outside-book.
6. **Onboarding:** a level step first, with big friendly cards. Individuals choose. Institution students skip it and see "Your class: Class 8 (Class 5–10)".
7. **Level-aware answers:** one prompt module (`backend/services/prompts/levels.py`) used by chat, notes, quizzes, flashcards and lessons:

   | Level | Answer style |
   | --- | --- |
   | school | Very simple words, short sentences, one idea per step, numbered steps, an everyday example, a check question at the end. Safety guardrails on. |
   | higher_secondary | Clear steps, board-exam and entrance framing, formulas with units, common mistakes. |
   | ugpg | Concise and rigorous, derivations when useful, exam-oriented. |
   | research | Dense and technical, precise terminology, assumptions and limitations stated, points to related concepts. |
   | general | Plain language for adults, practical, no exam framing. |

8. **Hints-first mode:** when on, the tutor gives a hint or guiding question first and offers "Show the next step" / "Show full solution".
   A chat-menu toggle for individuals. Class policy can force it on or off.
9. **Simpler app for `school`:**
   - A home screen with 3–4 large cards ("Ask a question", "Practise", "Revise", "Today's goal").
   - Bigger text using the existing Atkinson Hyperlegible font, and fewer nav items.
   - Step-by-step answers rendered as revealable steps.
   Advanced levels keep the current dense layout.
10. **Child safety (`school`):**
    - System-prompt guardrails, plus input moderation (an OpenAI-compatible moderation endpoint if configured, otherwise a `SMALL_LLM` classifier).
    - Off-topic and unsafe requests get a gentle redirect. The tutor never asks for personal details.
    - Distress gets a caring reply with the Tele-MANAS helpline (14416).
    - Store only counts of flagged events, not the content.
11. **Cleanup (owner decision 15):**
    - Remove `MemoryCurve` from `pages/Dashboard.jsx`, `components/AdaptivePlan.jsx` and `mobile/screens/Home.jsx`, and drop the `.lumina-curve` styles from `lumina.css` if the landing page doesn't need them.
    - Audit the other decorative or animated pieces inside the app (GSAP and Lenis usage outside `pages/Landing.jsx` and the website) and remove those that don't help studying. Keep functional motion such as XP toasts and card flips.

**Done when:** an admin can change a level's tools and see the effect immediately, an institution admin can restrict a class, a Class 8 student sees the simple home screen and simple answers, and backend tests cover the effective-tools rules.

**Status (2026-10-31): done.** Backend: `services/levels.py`, `services/tools_catalog.py`, `services/prompts/levels.py`,
`services/safety.py`, `utils/tools.py`, schema `0003`. Frontend: `context/ToolsContext.jsx`, `LevelPicker`, `LevelGate`,
`SchoolHome`, `pages/PlatformLevel.jsx`, `components/institution/ClassSettings.jsx`. Checked in a browser with Playwright
(onboarding → level saved → school home; level gate; hidden tools; Hints toggle; admin and class pages).
Not done yet: per-level styling beyond text size; ESLint only covers `.ts/.tsx`, so `.jsx` files aren't linted.

### Phase 3: RAG quality (pgvector, fresh start)
1. **Vector store** `services/vector_store.py` (`upsert`, `search_dense`, `search_keyword`, `delete_document`, `copy_document`, `count`), backed by pgvector.
   - Replace every `qdrant_service.` call, then **delete** `qdrant_service.py`, the Qdrant settings and the `qdrant-client` / `langchain-qdrant` dependencies.
   - Today those calls are in `document_service`, `book_service`, `rag_service`, `retrieval`, `institution_service`, `graph_analytics_service`,
     `topic_outline_service`, `self_check`, `study_modes`, and the auth endpoint.
2. **Schema (`db/schema/NNNN_chunks.sql`):**
   - `chunks(id, project_id, document_id, chunk_index, page, heading, content, content_hash, embedding vector(1536), tsv tsvector GENERATED, metadata jsonb)`
   - indexes: HNSW (`vector_cosine_ops`) on `embedding`, GIN on `tsv`, btree on `(project_id, document_id)`
   - one table for all projects (no collection per project)
   - shared-library and class-book copies become `INSERT ... SELECT` (no re-embedding)
3. **Ingestion and chunking (best practice):**
   - Structure-aware splitting: by heading and section first, then token-based (~400–600 tokens, ~15% overlap).
   - Never split inside `$...$` / `$$...$$`, tables or lists.
   - Keep the page number and heading path on every chunk. Prepend a short context line ("Book › Chapter › Section") to each chunk before embedding (contextual chunk headers).
   - Store `content_hash` so identical text is never embedded twice.
4. **Retrieval pipeline**, one module shared by chat and every study tool:
   1. **Query rewriting** (`SMALL_LLM`): turn the latest message plus recent history into a standalone search query. This fixes the follow-up bug.
      Skip it for first-turn questions that already stand alone.
   2. **Hybrid search:** pgvector dense top-k (~30) plus Postgres full-text top-k (~30), fused with Reciprocal Rank Fusion.
   3. **Rerank (optional):** when `RERANK_API_KEY` is set, call an OpenAI-style/Cohere-style rerank endpoint on the fused top ~30 and keep the best 5–8.
      Without a key, take the top RRF results. Reranker failures fall back silently to RRF order.
   4. **Diversity:** drop near-duplicates and merge adjacent chunks from the same page into one passage.
   5. **Grounding check:** if relevance is below a threshold, answer as outside-book (owner decision 11) instead of forcing citations.
   6. **Deep mode:** split the question into 2–4 sub-questions, retrieve for each, then answer with `BIG_LLM`.
5. **Prompt:** level-aware (Phase 2). Citations `[1](1)` map to passages with page numbers, and clicking one opens the book at that page.
   The static parts come first so provider prompt caching works (Phase 4).
6. **Evaluation harness** `backend/scripts/rag_eval/`: the metrics (retrieval recall@5, MRR, faithfulness and citation correctness by LLM judge, outside-book precision)
   and a small synthetic question set generated from a sample book. It's ready for the owner to add real books later.
   Run it before and after RAG changes and record the results in §8.

**Done when:** Qdrant is gone from code and config, follow-up questions retrieve the right passages, reranking switches on just by adding its key, and the eval harness runs.

**Status (2026-10-31): done.** `services/llm_service.py` (plain `openai` client, `SMALL_LLM_*` / `BIG_LLM_*`,
`resolve_model`), `embedding_service.py`, `reranker.py`, `chunking.py`, `vector_store.py`, `indexing.py`,
`retrieval.py`, `rag_service.py`; schema `0004_chunks.sql` (dimension templated by `db/migrate.py`).
Qdrant, LangChain and Azure-specific LLM code are gone. PDF text keeps page breaks (`\f`) so citations carry pages,
and the reader opens the cited page first. `scripts/fake_openai.py` is an OpenAI-compatible stand-in for local work
without keys. Verified end to end with it (upload → worker indexing → chat; follow-up rewritten; pages 1/3/4 with a
blank page 2). Builder's calls: a new section starts a new chunk once the current one has ~8 tokens; neighbour merging
stays within a section (max 3 chunks); when the book doesn't cover a question, passages below half the similarity
threshold are dropped so no irrelevant citations show.

### Phase 4: Cost reduction
1. **Model routing** (owner decision 7): `SMALL_LLM` / `BIG_LLM`, chosen in one `resolve_model(task, user)` function. Free users always get `SMALL_LLM`.
   Per-plan monthly token caps act as a safety net on top of the per-feature limits.
2. **Cache layers:**
   - **Generated study content** (quizzes, flashcards, notes, mindmaps, lessons): keyed by `(content_hash of source chunks, tool, level, prompt_version)` and persisted.
     Shared-library books (`services/book_library.py`) and class books use a **shared pool** (owner decision 13a). This is the biggest saving.
   - **Answer cache** (owner decision 13a): first questions on shared books only, in a neutral voice.
     Exact match on `hash(book, level, normalised question, prompt_version)`, then semantic match (pgvector similarity ≥ ~0.95). Store a TTL and the prompt version.
   - **Embedding cache:** chunk `content_hash` and query-text hash, so we never re-embed the same text.
   - **Hot cache** in Redis when available. Postgres is the source of truth.
3. **Prompt caching:** fixed prompt order (static system → level → profile/memory → retrieved context → history → question) so OpenAI-compatible providers' automatic prefix caching works.
4. **Token budgets:** a context builder with hard budgets per part (retrieved context, memory, history). Summarise long history (Phase 5) instead of sending raw turns.
5. **Usage telemetry:** record tokens, estimated cost and latency per AI call (user, feature, model, cache hit) in the database.
   Add a cost dashboard on the platform admin page with cost per user, per feature and per model, plus the cache hit rate.
   **Optional Langfuse** tracing turns on when `LANGFUSE_*` keys are set.

**Done when:** the dashboard shows the cache hit rate, and generating study tools for a shared book a second time costs nothing.

**Status (2026-10-31): done.** `services/telemetry.py` (every model, embedding and rerank call plus every cache hit →
`ai_calls`, buffered writes, optional Langfuse over its HTTP API), `services/shared_content.py` (shared-book scope,
quiz/flashcard pools with per-student "seen" and shuffled options, one-per-key notes and mindmaps),
`services/answer_cache.py` (first questions, exact then semantic), `services/context_builder.py` (token budgets),
`services/cost_report.py` + `GET /platform/costs` + the "AI costs" tab, monthly token caps (`MONTHLY_TOKENS` in
`services/plans.py`), `PREGENERATE_SHARED` job for class books; schema `0005_cost.sql`.
Builder's calls:
- A *shared book* is a bookstore import or class-book copy (or its original), found through `book_imports` /
  `class_book_copies` (`shared_root_documents()` in SQL). Pools are keyed by that root document, not by retrieved chunk
  hashes: copies share chunks anyway and the root is stable when retrieval changes.
- A project mixing a shared book with a personal upload counts as personal (nothing shared).
- Pool explanations never mention option letters, so options can be shuffled per student.
- Students are charged quota only for newly generated quiz questions / flashcard sets; chat answers from the cache
  still count as a chat answer (the limit is about use, not cost).
- Flashcards and mindmaps no longer generate a whole chat answer just to get context: they read passages directly
  (one model call per generation instead of two or three).
- Prices come from `*_PRICE_*` settings, never a hard-coded table. A mindmap the model botched (fallback) is never shared.

### Phase 5: Memory and context across all states
1. **Layer 1: profile.** Level, goals, exam date and preferred explanation style (existing settings plus level).
2. **Layer 2: learner model.** Weak and strong topics, mastery and common mistakes, built from the existing learning data
   (`learning_engine.py`, `learning_service.py`, quiz results, `003_adaptive_learning.sql` and `013_learning_engine.sql` tables).
   Wrong answers are tagged with the misconception when one can be identified.
3. **Layer 3: conversation memory.**
   - A rolling **summary per project chat**, refreshed by `SMALL_LLM` every ~10 turns. The summary plus the last ~6 turns go to the model.
   - **Long-term memory facts** (`user_memories`: user_id, kind, content, source, last_used_at, updated_at):
     - extracted by `SMALL_LLM` in batches (every ~10 messages), deduplicated and capped per user
     - **Class 11 and above only**: Class 5–10 gets layers 1–2 and the chat summary, never automatic facts
     - pruned after 6 months unused
   - **Memory across books** is a user setting (default on). When it's off, memory facts and the learner model are used only within the book they came from.
   - **Teachers never see** chats or memory facts, only the learner model (mastery, stuck topics, mistakes).
4. **Context builder** (`services/context_builder.py`) assembles profile + learner model + relevant memories + summary + recent turns within a token budget.
   It's used by chat and by every generator, so quizzes target weak topics and notes match the student's level.
5. **App state continuity:** save and restore the last book, last view, in-progress quiz and lesson position on the server, so a student resumes on any device (web or Android).
6. **"What Lumina remembers about you"** in Settings: view, edit and delete memories, plus a "clear all" button.

**Done when:** a student's weak topics from a quiz shape the next chat and quiz, a 100-turn chat still remembers turn 3 through the summary, and memories can be viewed and deleted.

**Status (2026-11-01): done.** `services/learner_model.py` (weak/strong topics from `topic_mastery`, open mistakes in
`learner_mistakes`, misconceptions tagged by the `tag_mistakes` job, mistakes marked fixed when answered right),
`services/memory.py` (rolling `chat_summaries` and `user_memories` facts, refreshed by the `refresh_memory` job every
~10 messages; facts only for `higher_secondary` and above incl. `general`; deduplicated, capped at 60, pruned by
worker housekeeping after 6 months unused), `context_builder.learner_block()` (`CONTEXT_BUDGET_MEMORY`), chat
integration, `api/v1/endpoints/memory.py`, `/user-data/state`; schema `0006_memory.sql`. Frontend: Settings → Memory
(`components/MemorySettings.jsx`), `utils/resume.js` (last book, view per book, unfinished quiz with a Resume banner).
Checked in a browser with Playwright (notes added/edited/deleted, phone layout, unfinished quiz resumed on a "new
device" at the right question) and end to end (chat turns → summary job ran on the worker).
Builder's calls:
- Recent turns = everything after the summary's cut-off (at most 16, never fewer than 6), so there's no gap.
- Memory notes are picked by word overlap with the question, then recency (no embeddings at 60 short notes).
- Prompt order: profile, what we know about the student, then the level rules. Cached shared answers (Phase 4) never
  include memory: they keep the neutral voice.
- `memoryAcrossBooks` and `autoMemory` live in user settings (the Settings page saves the whole settings object, so
  the toggles go through it). With across-books off, notes and mistakes from other books aren't used; notes the
  student typed in themselves apply everywhere.
- The quiz screen scores in the browser; it now also sends the answers to `/mcq/submit` so the learner model learns
  which answers were wrong. `/mcq/submit` now checks the test belongs to the caller.
- A quiz started with no topic targets the student's weakest topic.
- Memory notes are only extracted when the student's messages contain something personal (a cheap word check,
  `memory.worth_noting`); plain questions about the book never trigger the note-taking call.

**Follow-up (2026-11-01): several chats per book**, like ChatGPT's "New chat" (`services/chat_threads.py`,
`components/chat/ChatThreads.jsx`, schema `0007_chat_threads.sql`). Each message belongs to a thread; summaries are per
thread. A message without `thread_id` goes to the book's latest chat, so the Android shell and the tutor panel keep
working; streamed answers return the chat in an `X-Thread-Id` header. New chats are titled from their first question
(no model call). Messages saved before threads existed became one "Earlier chat" per book (checked on a real database).
Deleting a chat deletes its messages and summary.

### Phase 6: LaTeX and image input
1. **Rendering:**
   - One shared `<Markdown>` component (`remark-gfm` + `remark-math` + `rehype-katex`, KaTeX CSS) replaces every direct `ReactMarkdown` use. There are 9 files today.
   - Also use it in flashcards, quiz options and explanations, notes, mindmap labels, lessons and PDF export (`html2pdf.js` must include the KaTeX CSS).
   - Normalise `\( \)` / `\[ \]` to `$` / `$$`.
   - Streaming must not break on half-finished formulas: only render a formula once it's closed.
2. **Generation:** every prompt tells the model to write maths as `$...$` / `$$...$$`. Quizzes, flashcards and notes generators keep the LaTeX through JSON (escape it properly) and are covered by tests.
3. **Image input in chat** (tool `image_input`, metered feature `image` in `services/plans.py`):
   - **Frontend:** an attach/camera button. Resize to ≤1600px and compress to JPEG on the client, show a preview, and use the camera on Android.
   - **Storage:** a Supabase storage bucket `chat-images`, private and owner-only.
   - **Backend:** an OpenAI-compatible vision call (`BIG_LLM` for paid users, `SMALL_LLM` for free users; both must be vision-capable, and if one isn't, the feature is hidden for that group):
     1. Extract the question and describe the diagram.
     2. Use that as the retrieval query against the book.
     3. Answer at the student's level. If the book doesn't cover it, answer from general knowledge with the "Not from your book" label (if the class allows it).
   - Moderation applies to images for the `school` level.
   - Chat history stores the image reference and shows a thumbnail.

**Done when:** physics and maths answers render cleanly on web and Android, and a photographed textbook question gets a correct, cited (or labelled) answer.

**Status (2026-11-01): done.** Frontend: `components/Markdown.jsx` (remark-gfm + remark-math + rehype-katex, KaTeX CSS)
replaces every `ReactMarkdown`; `utils/math.js` turns `\( \)` / `\[ \]` and one-line `$$…$$` into what KaTeX expects and
holds back an unfinished formula while an answer streams; quiz options, flashcard sides, mindmap labels and Power Hour
questions render maths inline; PDF export carries the rendered KaTeX. Backend: `utils/json_latex.py` keeps LaTeX intact
when parsing model JSON (`\frac` would otherwise become a form feed + "rac"), used by quizzes, flashcards, mindmaps,
cram cards and written-answer grading; one `MATH_RULE` in `services/prompts/levels.py` for every generator.
Photo questions: `services/photo_questions.py`, `_attach_photo` in `api/v1/endpoints/chat.py`, `utils/image.js`
(client shrink to ≤1600 px JPEG), schema `0008_chat_images.sql`. Checked in a browser with Playwright (formulas render
as display/inline maths, no raw `$$`; photo → preview → answer; transcript hidden from the student; phone layout).
Builder's calls:
- Vision capability is declared per model (`SMALL_LLM_VISION`, `BIG_LLM_VISION`, default false); the photo button is
  hidden (and the backend refuses) for a learner whose model can't read images. `GET /levels/me` drops `image` then.
- Only the transcription uses the vision model; the answer is the normal tutor answer, with the transcript appended to
  the student's message after a `[From the student's photo]` marker (the app shows only the student's own words).
- Photo questions never use the shared answer cache. A bad photo doesn't use up the `image` quota.
- Class 5–10: the vision step answers `UNSAFE` for unsuitable images (gentle redirect, nothing stored); the transcript
  also goes through the normal safety screen.
- If storage is unavailable the answer still works; only the thumbnail is missing when the chat is reopened.
- Chat history now returns each answer's sources, so citations still work in a reopened chat.

### Phase 7: Intelligent gamification
1. **XP for learning, not clicking.** XP sources:
   - `mastery_gain`: a topic's mastery goes up
   - `mistake_fixed`: getting right a question you previously got wrong
   - `review_on_time`: finishing a due spaced-repetition review
   - `daily_goal`
   - `exam_plan_step`

   Cap XP per action type per day to stop farming. Opening pages and re-reading earn nothing.
2. **Adaptive daily goal:** one goal a day, generated from the learner model. It's sized to the level, the student's recent pace and the days left to their exam.
3. **Streaks with kindness:** one "streak freeze" per week, and a **comeback bonus** after a break instead of a punishing reset.
4. **Presentation by level:**
   - `school`: characters, badges, celebrations, class leaderboard (`leaderboard` tool, which institutions can turn off)
   - `higher_secondary`: exam countdown and goal tracking
   - `ugpg` and `general`: quiet progress stats
   - `research`: milestones only, no confetti
5. **Teacher view:** in the institution dashboard, which students are **stuck** (falling mastery, repeated mistakes, inactive), not just XP rankings.
6. Rework the existing `gamification_service.py`, `GamificationContext.jsx`, `GamificationPanel.jsx` and `XPToast.jsx` rather than starting a parallel system. No legacy XP migration is needed (fresh start).

**Done when:** XP correlates with mastery gains in tests, farming is capped, and each level shows its own style.

**Status (2026-11-01): done.** `services/gamification_service.py` reworked: an append-only `xp_events` ledger and one
`award()` (daily cap per kind, dedupe keys, streak, badges, levels in one transaction). XP is granted only on the
server where learning is measured: `mastery_gain` (`learning_engine.record`: XP = the rise in a topic's mastery, in
points), `mistake_fixed` (`learner_model.mark_fixed`), `review_on_time` (`record_review` while the card was due),
`exam_plan_step` (a learning-path topic completed the first time), `daily_goal`, and `comeback` (first learning after a
3+ day break). The old `award-xp` endpoint grants nothing: it returns XP earned since the client's last sync, so the
existing hooks show toasts only for real rewards. `services/daily_goal.py` (answer N questions; sized by level, the
last week's pace and days to the exam; focus = weakest topic and due reviews; fixed for the day). Streaks count days
with any XP, with one automatic freeze per week. `services/leaderboard.py` (weekly class board, first names,
`leaderboard` tool), `services/teacher_insights.py` ("Needs help" in the class dashboard: inactive, mastery slipping,
unfixed mistakes; learning data only). Schema `0009_gamification.sql`. Frontend: `GamificationContext` syncs instead
of granting; `XPToast` celebrates only for `school`, calm for exam/quiet, milestones only for `research`;
`GamificationPanel` per style (exam countdown, daily goal, streak with freeze, learning stats, class board); the
adaptive goal on the dashboard and the school home; "Needs help" on the institution class page.
Checked end to end and in a browser with Playwright (practice → XP and toast; chatting earns 0; the daily mastery cap
held in the real flow; class board; teacher view; phone layout).
Builder's calls:
- Daily caps: mastery 150, mistakes fixed 90 (15 each), reviews 60 (4 each), goal 30, plan steps 50 (10 each),
  comeback 20. Level thresholds were lowered (top level at 8,000 XP) because learning XP comes slower than click XP.
- Badges are learning milestones only (mastery points, mistakes fixed, on-time reviews, goals, streaks, plan steps,
  levels); the old activity badges (chats, notes, pomodoros) are gone.
- Streaks count learning days (any XP), not app opens.
- A goal created by a background check uses the learner's real level; it stays fixed for the day.

### Follow-up (2026-11-01): phone UX pass (phone browsers and the app shell)
Audited every main screen at 390×844 with Playwright (overflow, tap targets, text size, page errors), then:
- **Book page header on phones:** book name + Search + one labelled "More" menu (progress, documents, summary, focus
  timer, bookmarks, tutor, back). The progress panel was unreachable on phones before; it now opens and fits.
- **Tools are always visible:** the labelled tool-chip row (everyday tools first) is used in phone browsers too, not
  only in the app shell; the open tool's chip scrolls into view.
- **Chat:** starter suggestions (adapt to hints mode); Photo / Hints first / Deep answer behind one "+" with labels and
  ON/OFF state, shown as removable pills when on; wider 16px input (no iOS zoom); "Your chats (n)" instead of a second
  "New chat" label; shorter welcome.
- **Tool pages:** compact headers that wrap instead of squeezing; button labels never break; stacked empty-state actions.
- **Settings on phones:** a list of sections with one-line descriptions, each opening on its own page with a back
  button (replaces a 10-item sideways tab bar).
- **App shell home:** the adaptive daily goal leads (ring shows questions); bigger tap targets (checklist close, Skip,
  document delete/select); tab labels 11.5px.
- No coach-mark tours on phone-size screens (one clear next step instead). Dark-mode colours for the new menus.
- Fixed: the Knowledge Graph view crashed (it animated style properties this cytoscape version doesn't have).

### Follow-up (2026-11-03): platform analytics dashboard
The admin console now opens on **Analytics** (`components/platform/Analytics.jsx`, `GET /platform/analytics?days=7|30|90`,
`services/analytics_report.py`, schema `0010_analytics.sql`). Each number is compared with the previous period.
- **Overview:** learners, sign-ups, active learners, questions, chats, books, revenue, AI spend (+ per active learner).
- **Growth:** active today / 7 days / 30 days, stickiness, daily charts (sign-ups, actives, questions, chats, revenue,
  AI spend) with hover/tap values, a table view and CSV download.
- **Activation funnel** for the period's sign-ups: level → book → ready → chat → practice → came back → paid.
- **Retention:** weekly sign-up cohorts × weeks 0–7.
- **Engagement:** visit frequency, practice per tool, AI features used, most active learners.
- **Learning:** accuracy, hints, mastery points, topics mastered, mistakes opened/fixed, daily-goal rate, review
  backlog, by level, hardest topics, XP by reason.
- **Revenue:** collected, personal MRR (yearly ÷ 12), school MRR (live paid seats × seat price), new payers, payments,
  subscriptions (incl. cancelling), schools by status.
- **Health:** job queue now, job failures and times, book-processing failures, AI error rate and p95 latency,
  child-safety flag counts.
Builder's calls:
- "Active" = used the app that day: `user_active_days`, written by the auth dependency at most once an hour per
  process (and again on a new day). Backfilled from earlier activity.
- A sign-up is a user's first signed-in request (`app_users.created_at`).
- Counts and learning data only: no chat text or memory notes appear on this page.

---

## 6. Configuration (new settings)

| Setting | Purpose | Default |
| --- | --- | --- |
| `DATABASE_URL` | The app database (all tables, pgvector, jobs, caches, telemetry). Docker in dev, Azure Database for PostgreSQL in prod. | required |
| `SOURCE_DATABASE_URL` | Only for the one-off copy from Supabase (`scripts/migrate_from_supabase.py`) | empty |
| `DB_POOL_SIZE` / `RUN_MIGRATIONS` | Connections per process / apply `db/schema` on startup | `10` / `true` |
| `SMALL_LLM_MODEL` / `SMALL_LLM_BASE_URL` / `SMALL_LLM_API_KEY` | Small model (most tasks, all free users) | required |
| `BIG_LLM_MODEL` / `BIG_LLM_BASE_URL` / `BIG_LLM_API_KEY` | Big model (Visual Lab, Deep mode, paid image input) | falls back to small |
| `EMBEDDING_*` | Embedding API (existing settings) | required |
| `REDIS_URL` | Optional hot cache, rate limits, progress pub/sub | empty (off) |
| `RERANK_API_KEY` / `RERANK_BASE_URL` / `RERANK_MODEL` | Reranking, on only when the key is set | empty (off) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Optional AI-call tracing | empty (off) |
| `PREGENERATE_SHARED` | Pre-generate study content for shared/class books | `false` |
| `SEMANTIC_CACHE_THRESHOLD` | Similarity for the semantic answer cache | `0.95` |
| `ANSWER_CACHE_ENABLED` / `ANSWER_CACHE_TTL_DAYS` | First-question answer cache on shared books | `true` / `30` |
| `SHARED_CONTENT_ENABLED` | Shared quiz/flashcard pools, notes and mindmaps for shared books | `true` |
| `SMALL_LLM_PRICE_*` / `BIG_LLM_PRICE_*` / `EMBEDDING_PRICE_INPUT` / `RERANK_PRICE_PER_CALL` | USD per 1M tokens (per call for rerank), for cost estimates | `0` (unknown) |
| `CONTEXT_BUDGET_EXCERPTS` / `_HISTORY` / `_PROFILE` / `_MEMORY` | Token budgets per prompt part | `6000` / `2500` / `1200` / `900` |
| `SMALL_LLM_VISION` / `BIG_LLM_VISION` | Whether each model can read images (photo questions) | `false` |
| `CHAT_IMAGE_MAX_BYTES` / `CHAT_IMAGES_BUCKET` | Photo size limit / private storage bucket | `3000000` / `chat-images` |
| `MODERATION_ENABLED` | Input moderation for the school level | `true` |
| `RATE_LIMIT_*` | Per-user / per-IP limits | sensible defaults |

The owner will provide the real `.env`. Keep `.env.example` complete and up to date.

---

## 7. Later (out of scope now)
- **A separate native phone app** (owner decision, 2026-10-31). Don't invest in the Capacitor shell in `frontend/src/mobile/`
  beyond keeping it working; the web app must work well in phone browsers.
- Moving sign-in and file storage off Supabase (owner decision 2).
- Parental consent flow for under-13 users.
- Per-student tool exceptions inside a class.
- Azure infrastructure as code (today `azure.yml` and `azure-ops.yml` create what they need with the Azure CLI).

## 8. Results log
Record load-test numbers (Phase 1), RAG eval baselines and results (Phase 3), and cache hit rates (Phase 4) here, with the date and commit.

### 2026-10-31 · Phase 4 shared-book reuse (end-to-end, fake model server)
A teacher's 4-page book published to a class; two students (same level) each generate a 5-question quiz, 5
flashcards, Summary notes and a mindmap on "Respiration", then ask the same first chat question. Run against
`scripts/fake_openai.py` with the real app, worker and Postgres.

| Tool | Model calls, student 1 | Model calls, student 2 |
| --- | --- | --- |
| Quiz (5 questions) | 1 | **0** (same questions, options reshuffled) |
| Flashcards (5) | 1 | **0** |
| Notes | 1 | **0** |
| Mindmap | 1 | **0** |
| First chat question | 1 | **0** (citations point at student 2's own copy) |

Dashboard (`/platform/costs`): cache hit rate 45% overall (50% per tool: one generation, one reuse). Real hit rates
depend on class sizes; re-measure in production and record them here. (Bookstore import couldn't be exercised
here because it copies text through Supabase Storage; class copies use the same sharing code.)

### 2026-10-31 · Phase 3 RAG eval (`uv run python -m scripts.rag_eval`)
**Not run with real models yet: no keys in this environment.** The harness was smoke-tested against
`scripts/fake_openai.py` (3 questions: recall@5 100%, MRR 0.61, off-book precision 100%; meaningless for quality).
To record a baseline: set `SMALL_LLM_*` / `EMBEDDING_*` (and optionally `RERANK_*`), upload a real book, then
`make --n 40` and `run --judge`, and add the table here with the date, commit and model names. Tune
`RAG_MIN_SIMILARITY` for your embedding model using the in-book grounded rate and off-book precision.

### 2026-10-31 · Phase 1 load test (`backend/scripts/loadtest/locustfile.py`)
Non-AI paths (projects, book, documents, chat history, settings, XP, bookmarks), each simulated user with its own
account. One 4-CPU / 15 GB machine running Postgres, the app *and* Locust together, so treat the numbers as a floor.

| Setup | Users | Req/s | p50 | p95 | p99 | Failures |
| --- | --- | --- | --- | --- | --- | --- |
| 1 uvicorn process | 50 | 60 | 4 ms | 17 ms | 180 ms | 0 / 2,651 |
| 1 uvicorn process | 200 | 223 | 4 ms | 44 ms | 130 ms | 0 / 9,814 |
| gunicorn, 4 workers | 200 | 235 | 3 ms | 22 ms | 180 ms | 0 / 10,331 |
| gunicorn, 4 workers (old `max_requests=1000`) | 500 | 540 | 6 ms | 53 ms | 140 ms | 29 / 24,324 (worker recycling cut connections) |
| gunicorn, 4 workers (`GUNICORN_MAX_REQUESTS=20000`) | 500 | 535 | 4 ms | 39 ms | 130 ms | **0 / 23,568** |

AI-backed endpoints (chat, generation) are bound by the model provider's latency and rate limits, not by this
server. Re-run with real keys once the LLM/embedding provider is set (Phase 3), and on the production Container App size.
