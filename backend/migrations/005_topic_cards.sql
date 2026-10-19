-- Cache for Exam Tonight cram cards, Visual Lab simulations and per-book topic
-- coverage (see api/v1/endpoints/study_modes.py). Purely additive: the backend
-- works without this table, it just regenerates instead of caching.
CREATE TABLE IF NOT EXISTS topic_cards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    kind        TEXT NOT NULL,              -- 'cram' | 'visual' | 'coverage'
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, topic, kind)
);

-- Only the backend (service role, which bypasses RLS) reads and writes it
ALTER TABLE topic_cards ENABLE ROW LEVEL SECURITY;
