# Phase 4: Cost reduction — implementation plan

> For agentic workers: follow test-driven-development; check boxes as tasks finish.

**Goal:** every AI call is measured, shared books are paid for once, and no single account can run up unbounded costs.

**Architecture:** one `ai_calls` table records every model, embedding and rerank call (and every cache hit, with
the cost it saved). Shared-library and class books resolve to a *root document*; quizzes and flashcards for a root
come from a growing pool, notes and mindmaps from a one-per-key shared cache, and first chat questions from an
answer cache (exact hash, then pgvector similarity). Per-plan monthly token caps sit on top of feature limits.

**Builder's calls:**
- The pool is keyed by the book's root document (the bookstore original or the teacher's class book), not by
  hashes of retrieved chunks: copies share chunk hashes anyway, and a root id is stable when retrieval changes.
- Prices come from settings (`SMALL_LLM_PRICE_INPUT` etc., USD per 1M tokens), never a hard-coded model table.
- Langfuse is called over its public ingestion HTTP API (no SDK dependency).
- Flashcards and mindmaps stop generating a whole chat answer just to get context: they read passages directly.
- Pool explanations must not mention option letters, so options can be shuffled per student.

## Tasks
- [x] 1. Schema `0005_cost.sql`: `ai_calls`, `content_pool`, `content_pool_seen`, `shared_content`
      (one-per-key content), `answer_cache` (with embedding), `shared_root_documents()` SQL function.
- [x] 2. `services/telemetry.py`: pricing, buffered inserts, optional Langfuse; hooked into `llm_service`,
      `embedding_service`, `reranker`. Tests: cost maths, rows written, failures never break calls.
- [x] 3. `services/shared_content.py`: root lookup, pool take/add with per-user "seen", option shuffling,
      one-per-key assets. Tests against real Postgres.
- [x] 4. Quizzes, flashcards, notes, mindmaps use it; quota charged only for newly generated items.
- [x] 5. `services/answer_cache.py` + chat: first question on an all-shared scope, no hints/custom prompt;
      neutral voice; sources remapped to the student's own copies. Tests.
- [x] 6. Monthly token caps per plan (`MONTHLY_TOKENS` in `services/plans.py`), checked in `usage.consume/check`. Tests.
- [x] 7. `services/context_builder.py` token budgets, used by `rag_service.build_messages`. Tests.
- [x] 8. `GET /platform/costs` + "AI costs" section on the platform page (cost per user/feature/model,
      cache hit rate, money saved).
- [x] 9. Settings, `.env.example`, AGENTS.md status and §8; full test run; frontend build; push.
