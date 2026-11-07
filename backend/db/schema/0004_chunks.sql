-- Book passages for search (AGENTS.md Phase 3): pgvector replaces Qdrant.
-- {{EMBEDDING_DIMENSION}} is filled in by db/migrate.py from settings; changing
-- the embedding model's dimension later needs a fresh chunks table.

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    page         INTEGER,                -- 1-based page in the original PDF, when known
    heading      TEXT,                   -- "Chapter › Section" path
    content      TEXT NOT NULL,          -- the passage as shown and cited
    content_hash TEXT NOT NULL,          -- hash of model + embedded text: identical text is embedded once
    embedding    vector({{EMBEDDING_DIMENSION}}),
    tsv          tsvector GENERATED ALWAYS AS
                 (to_tsvector('english', coalesce(heading, '') || ' ' || content)) STORED,
    metadata     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_project_doc ON chunks (project_id, document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks (content_hash);
