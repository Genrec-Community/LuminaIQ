-- ============================================================
-- LUMINA IQ - Learning engine (knowledge graph + learner model)
-- ============================================================
-- Additive only: the database is shared with production.
--
-- 1. topic_relations gains a typed relationship (kind), a confidence and the
--    source evidence. relation_type stays 'prerequisite' | 'related' so older
--    code keeps working: REQUIRES maps to 'prerequisite', every other kind to
--    'related'.
-- 2. learning_events: every piece of learning evidence (an answer, a recall,
--    a flashcard grade) with its difficulty and whether help was used.
-- 3. topic_mastery: the learner model per (user, project, topic) — Bayesian
--    Knowledge Tracing estimate plus a memory-stability estimate for spacing.
-- ============================================================

ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS kind TEXT;
ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;
ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS evidence TEXT;

CREATE TABLE IF NOT EXISTS learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'mcq',          -- mcq | quick_check | recall | flashcard | written | feed
    correct BOOLEAN NOT NULL,
    difficulty TEXT,                           -- easy | medium | hard
    hinted BOOLEAN NOT NULL DEFAULT FALSE,     -- answered with help (hint, worked solution)
    source TEXT,                               -- screen that produced it (power_hour, exam_tonight, quiz, feed…)
    p_known_before DOUBLE PRECISION,
    p_known_after DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_learning_events_user_project
    ON learning_events(user_id, project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_events_topic
    ON learning_events(user_id, project_id, topic);

CREATE TABLE IF NOT EXISTS topic_mastery (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    p_known DOUBLE PRECISION NOT NULL DEFAULT 0.15,  -- BKT P(known)
    attempts INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    evidence DOUBLE PRECISION NOT NULL DEFAULT 0,    -- weighted amount of evidence
    stability_days DOUBLE PRECISION NOT NULL DEFAULT 1,  -- memory half-life proxy
    review_days INTEGER NOT NULL DEFAULT 0,          -- distinct days with evidence
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    last_day DATE,
    next_review TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, project_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_topic_mastery_review
    ON topic_mastery(user_id, project_id, next_review);

-- The backend uses the service key; RLS keeps direct client access to own rows
ALTER TABLE learning_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_mastery ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
    CREATE POLICY "Own learning events" ON learning_events FOR SELECT USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    CREATE POLICY "Own topic mastery" ON topic_mastery FOR SELECT USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
