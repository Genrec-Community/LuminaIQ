# Phase 3: RAG Quality — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax.

**Goal:** Better answers from the student's book. Follow-up questions find the right passages, search combines meaning and keywords, citations point to pages, and every AI piece talks to any OpenAI-compatible API.

**Architecture:**
- **AI clients:** `llm_service` (the plain `openai` client, with `SMALL_LLM_*` / `BIG_LLM_*`, routed by `resolve_model(task)`), `embedding_service` (OpenAI-compatible `/embeddings`) and `reranker` (Cohere/Jina-style `/rerank`, optional).
- **Storage:** `chunks` table in Postgres (pgvector HNSW plus a generated `tsvector`), behind `services/vector_store.py`.
- **Ingestion:** `services/chunking.py` splits by structure, keeps maths, tables and lists whole, tags pages using `\f`, adds contextual headers, and stores a content hash.
- **Retrieval:** `services/retrieval.py`: rewrite → hybrid (dense + full-text, Reciprocal Rank Fusion) → optional rerank → merge neighbours → grounding score. Deep mode decomposes the question.
- **Answers:** `rag_service` without LangChain. Same public functions and stream protocol (text plus `__SOURCES__:`), so the frontend is unchanged.

**Spec:** `AGENTS.md` §5 Phase 3, owner decisions 4, 7 and 7a, and "keep everything OpenAI-compatible" (2026-10-31).

## Global Constraints
- No Qdrant, no LangChain, no Azure-specific code paths. Azure works through its OpenAI-compatible `/openai/v1` URL.
- Old `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` still work as a fallback for `SMALL_LLM_*`, so existing deployments keep running.
- Free plan → `SMALL_LLM` for everything. `BIG_LLM` for `deep`, `lab` and paid `vision`.
- Embedding dimension comes from `EMBEDDING_DIMENSION` (templated into the schema). Changing it later needs a fresh index.
- Everything degrades gracefully: no reranker key → RRF order; embeddings down → keyword search; no chunks → stored-text fallback.

## Review Focus
1. A follow-up question ("explain that again") → rewritten using history before searching. Covered by `test_followup_is_rewritten`.
2. A formula or table spanning a size boundary → never split. Covered by `test_math_block_not_split`.
3. A book whose pages include blank ones → page numbers stay correct. Covered by `test_pages_counted_with_blank_pages`.
4. The reranker returns an error → falls back to fused order, and the answer still works. Covered by `test_rerank_failure_falls_back`.
5. Copying a book into another project (bookstore, class) → no re-embedding. Covered by `test_copy_document_reuses_vectors`.

---

- [x] **Task 1: OpenAI-compatible AI clients.** `llm_service` rewrite (`chat_completion`, `chat_completion_stream`, `resolve_model(task, plan)`, token usage recording, reasoning-tag filter, temperature fallback for reasoning models), `embedding_service` rewrite (batching, concurrency limit, optional `dimensions`), `services/reranker.py`. Settings `SMALL_LLM_*`, `BIG_LLM_*`, `RERANK_*`; remove Azure/LangChain LLM settings. Tests use a fake HTTP transport.
- [x] **Task 2: chunks table and vector store.** `db/schema/0004_chunks.sql` (dimension templated by `db/migrate.py`); `vector_store`: `upsert_chunks`, `search_dense`, `search_keyword`, `delete_document`, `copy_document`, `count`, `first_chunks`. Real-Postgres tests.
- [x] **Task 3: chunker.** Structure- and page-aware, maths/table safe, overlap, contextual header, content hash. Unit tests.
- [x] **Task 4: retrieval pipeline.** Rewrite, hybrid with RRF, rerank, neighbour merge, grounding, Deep decomposition, plus `search_passages` / `passages_text` for the study tools. Tests with fakes.
- [x] **Task 5: ingestion and every caller moved off Qdrant.** document_service (embed and index, reindex, delete), book_service / institution_service (copy), graph_analytics, topic_outline, self_check, study_modes and the auth endpoint. Delete `qdrant_service.py`, `utils/embedding_queue.py` (if unused), `utils/text_chunker.py`, the Qdrant settings and the qdrant/langchain dependencies.
- [x] **Task 6: rag_service without LangChain.** Same signatures and stream protocol. Sources carry `page`. The grounding score switches on the outside-book rule.
- [x] **Task 7: evaluation harness.** `scripts/rag_eval/`: synthetic question set from a sample text, recall@5, MRR, faithfulness / citation judge (`SMALL_LLM`). Record "not run: no keys" in §8 until keys exist.
