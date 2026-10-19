-- Shared book library (see services/book_library.py): study assets generated
-- from a book (Visual Lab simulations, cram cards) are reused by everyone who
-- uploads the same book. Purely additive; the backend works without it.

-- One row per distinct book, identified by a bottom-k MinHash sketch of its text
CREATE TABLE IF NOT EXISTS shared_books (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sketch       JSONB NOT NULL,          -- smallest 128 shingle hashes
    sketch_keys  BIGINT[] NOT NULL,       -- smallest 16, for candidate lookup
    title        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shared_books_sketch_keys ON shared_books USING GIN (sketch_keys);

-- Which shared book each uploaded document is
CREATE TABLE IF NOT EXISTS document_books (
    document_id  UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    book_id      UUID NOT NULL REFERENCES shared_books(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_document_books_book ON document_books (book_id);

-- Generated assets per book + topic. Visual Lab HTML lives in the
-- shared-assets storage bucket (storage_path); small JSON assets in content.
CREATE TABLE IF NOT EXISTS shared_topic_assets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id       UUID NOT NULL REFERENCES shared_books(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    topic_key     TEXT NOT NULL,          -- normalised topic name
    kind          TEXT NOT NULL,          -- 'visual' | 'cram'
    content       JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_path  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_id, topic_key, kind)
);

-- Backend-only (service role bypasses RLS); never exposed to clients
ALTER TABLE shared_books ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_books ENABLE ROW LEVEL SECURITY;
ALTER TABLE shared_topic_assets ENABLE ROW LEVEL SECURITY;

-- Private bucket for the shared .html simulations
INSERT INTO storage.buckets (id, name, public)
VALUES ('shared-assets', 'shared-assets', false)
ON CONFLICT (id) DO NOTHING;
