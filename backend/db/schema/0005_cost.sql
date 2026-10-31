-- Cost reduction (AGENTS.md Phase 4): per-call AI telemetry, shared study-content
-- pools for shared-library and class books, and the first-question answer cache.

-- One row per AI call (model, embedding, rerank) and per cache hit.
CREATE TABLE IF NOT EXISTS ai_calls (
    id             BIGSERIAL PRIMARY KEY,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id        UUID,
    feature        TEXT NOT NULL DEFAULT 'other',
    kind           TEXT NOT NULL,                 -- llm | embedding | rerank | cache
    model          TEXT NOT NULL DEFAULT '',
    role           TEXT NOT NULL DEFAULT '',      -- small | big | embedding | rerank | pool | answer
    input_tokens   INTEGER NOT NULL DEFAULT 0,
    output_tokens  INTEGER NOT NULL DEFAULT 0,
    cached_tokens  INTEGER NOT NULL DEFAULT 0,    -- prompt tokens the provider served from its prefix cache
    cost_usd       NUMERIC(12, 6) NOT NULL DEFAULT 0,
    saved_usd      NUMERIC(12, 6) NOT NULL DEFAULT 0,  -- for cache hits: what the call would have cost
    latency_ms     INTEGER NOT NULL DEFAULT 0,
    cache_hit      BOOLEAN NOT NULL DEFAULT false,
    ok             BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_ai_calls_created ON ai_calls (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_calls_user ON ai_calls (user_id, created_at DESC);

-- Monthly tokens per user (for plan caps): one cheap indexed sum.
CREATE OR REPLACE FUNCTION user_month_tokens(p_user UUID, p_since TIMESTAMPTZ)
RETURNS BIGINT LANGUAGE sql STABLE AS $$
    SELECT COALESCE(SUM(input_tokens + output_tokens), 0)::bigint
    FROM ai_calls WHERE user_id = p_user AND created_at >= p_since AND NOT cache_hit;
$$;

-- The shared original behind a document: the bookstore book or teacher's class book it
-- was copied from, the document itself when it *is* such an original, otherwise NULL
-- (a personal upload, which never shares generated content).
CREATE OR REPLACE FUNCTION shared_root_documents(p_docs UUID[])
RETURNS TABLE (document_id UUID, root_id UUID) LANGUAGE sql STABLE AS $$
    SELECT d.id, COALESCE(
        (SELECT b.document_id FROM book_imports bi JOIN books b ON b.id = bi.book_id
          WHERE bi.document_id = d.id AND b.document_id IS NOT NULL LIMIT 1),
        (SELECT cb.source_document_id FROM class_book_copies c JOIN class_books cb ON cb.id = c.class_book_id
          WHERE c.document_id = d.id LIMIT 1),
        (SELECT d.id WHERE EXISTS (SELECT 1 FROM books b WHERE b.document_id = d.id)
                        OR EXISTS (SELECT 1 FROM class_books cb WHERE cb.source_document_id = d.id))
    )
    FROM unnest(p_docs) AS d(id);
$$;

-- Quiz questions and flashcards for a shared book, one item per row. Students draw
-- items they haven't seen; the pool grows only when someone runs out.
CREATE TABLE IF NOT EXISTS content_pool (
    id             BIGSERIAL PRIMARY KEY,
    pool_key       TEXT NOT NULL,     -- hash of (root docs, tool, topic, level, variant, prompt version)
    tool           TEXT NOT NULL,
    root_ids       UUID[] NOT NULL,
    topic          TEXT NOT NULL DEFAULT '',
    level          TEXT NOT NULL DEFAULT '',
    item           JSONB NOT NULL,
    item_hash      TEXT NOT NULL,
    cost_usd       NUMERIC(12, 6) NOT NULL DEFAULT 0,   -- generation cost per item (what a reuse saves)
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pool_key, item_hash)
);
CREATE INDEX IF NOT EXISTS idx_content_pool_key ON content_pool (pool_key);

CREATE TABLE IF NOT EXISTS content_pool_seen (
    user_id  UUID NOT NULL,
    item_id  BIGINT NOT NULL REFERENCES content_pool(id) ON DELETE CASCADE,
    seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, item_id)
);

-- One generated asset per key for shared books (notes, mindmaps).
CREATE TABLE IF NOT EXISTS shared_content (
    key         TEXT PRIMARY KEY,
    tool        TEXT NOT NULL,
    root_ids    UUID[] NOT NULL,
    content     JSONB NOT NULL,
    cost_usd    NUMERIC(12, 6) NOT NULL DEFAULT 0,
    hits        INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Answers to first questions on shared books, in a neutral voice.
CREATE TABLE IF NOT EXISTS answer_cache (
    id              BIGSERIAL PRIMARY KEY,
    scope_key       TEXT NOT NULL,      -- hash of (root docs, level, deep, outside-book rule, prompt version)
    question_hash   TEXT NOT NULL,      -- hash of the normalised question
    question        TEXT NOT NULL,
    embedding       vector({{EMBEDDING_DIMENSION}}),
    answer          TEXT NOT NULL,
    sources         JSONB NOT NULL DEFAULT '[]'::jsonb,   -- doc_id holds the root document id
    cost_usd        NUMERIC(12, 6) NOT NULL DEFAULT 0,
    hits            INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (scope_key, question_hash)
);
CREATE INDEX IF NOT EXISTS idx_answer_cache_scope ON answer_cache (scope_key, expires_at);
