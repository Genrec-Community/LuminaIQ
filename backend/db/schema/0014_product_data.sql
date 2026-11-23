-- Product data: funnel events, quiz attempts, where users came from, consent, feedback,
-- and export/deletion requests. Feeds the admin analytics (investor view).
-- Privacy: no chat text, no free-form profiling. Acquisition data names a channel, not a person.

-- 1. Product events: a small, fixed set of names (services/product_analytics.py EVENTS)
CREATE TABLE IF NOT EXISTS product_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID,                       -- null before sign-up
    anon_id     TEXT,                       -- random browser id; links pre-sign-up events to the user
    session_id  TEXT,
    name        TEXT NOT NULL,
    project_id  UUID,
    props       JSONB NOT NULL DEFAULT '{}',
    platform    TEXT,                       -- web | android
    path        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_product_events_created ON product_events (created_at);
CREATE INDEX IF NOT EXISTS idx_product_events_user ON product_events (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_product_events_name ON product_events (name, created_at);
CREATE INDEX IF NOT EXISTS idx_product_events_anon ON product_events (anon_id) WHERE anon_id IS NOT NULL;

-- 2. Assessment attempts: one row per finished test, one response row per question
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL,
    project_id       UUID,
    kind             TEXT NOT NULL,         -- mcq | subjective | flashcards | exam | review
    source_id        UUID,                  -- mcq_tests.id etc.
    topic            TEXT,
    difficulty       TEXT,
    status           TEXT NOT NULL DEFAULT 'completed',   -- started | completed | abandoned
    question_count   INT NOT NULL DEFAULT 0,
    answered_count   INT NOT NULL DEFAULT 0,
    correct_count    INT NOT NULL DEFAULT 0,
    score_pct        NUMERIC(5,2),
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at     TIMESTAMPTZ,
    duration_seconds INT
);
CREATE INDEX IF NOT EXISTS idx_attempts_user ON assessment_attempts (user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_attempts_started ON assessment_attempts (started_at);
CREATE INDEX IF NOT EXISTS idx_attempts_source ON assessment_attempts (source_id);

CREATE TABLE IF NOT EXISTS attempt_responses (
    attempt_id     UUID NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    position       INT NOT NULL,
    topic          TEXT,
    chosen         TEXT,
    correct_answer TEXT,
    is_correct     BOOLEAN,
    PRIMARY KEY (attempt_id, position)
);

-- 3. Where a user came from (first touch, saved once at sign-up)
CREATE TABLE IF NOT EXISTS signup_attribution (
    user_id        UUID PRIMARY KEY,
    channel        TEXT NOT NULL,           -- derived: paid | social | search | referral | school | email | direct | other
    utm_source     TEXT,
    utm_medium     TEXT,
    utm_campaign   TEXT,
    utm_content    TEXT,
    utm_term       TEXT,
    referrer_host  TEXT,                    -- host only, never the full URL
    landing_path   TEXT,
    referral_code  TEXT,
    invite_code    TEXT,
    platform       TEXT,
    country        TEXT,                    -- from the CDN/proxy header when present
    first_seen_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_signup_attribution_channel ON signup_attribution (channel, created_at);

-- 4. Consent: append-only and versioned. The latest row per (user, kind) is the current state.
CREATE TABLE IF NOT EXISTS consent_records (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL,
    kind        TEXT NOT NULL,              -- terms | privacy | marketing_email | parental
    version     TEXT NOT NULL,
    granted     BOOLEAN NOT NULL,
    method      TEXT,                       -- sign_in_notice | settings | guardian_declaration | school_admin
    granted_by  TEXT NOT NULL DEFAULT 'self',   -- self | guardian | institution
    guardian_name  TEXT,
    guardian_email TEXT,
    ip_hash     TEXT,                       -- salted hash, never the raw address
    user_agent  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records (user_id, kind, created_at DESC);

-- 5. Feedback: thumbs on AI answers, NPS, bug reports
CREATE TABLE IF NOT EXISTS feedback (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID,
    kind        TEXT NOT NULL,              -- answer_rating | nps | bug | idea
    target_type TEXT,                       -- chat_message | note | quiz | flashcards | mindmap
    target_id   TEXT,
    rating      SMALLINT,                   -- -1 / 1 for thumbs, 0..10 for NPS
    comment     TEXT,
    context     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback (kind, created_at);
-- one thumbs per user per answer (changing your mind replaces it)
CREATE UNIQUE INDEX IF NOT EXISTS uq_feedback_answer_rating
    ON feedback (user_id, target_type, target_id) WHERE kind = 'answer_rating';

-- 6. Export / deletion requests
CREATE TABLE IF NOT EXISTS data_requests (
    id           BIGSERIAL PRIMARY KEY,
    user_id      UUID NOT NULL,
    kind         TEXT NOT NULL,             -- export | delete
    status       TEXT NOT NULL DEFAULT 'pending',   -- pending | done | rejected
    note         TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_data_requests_status ON data_requests (status, requested_at);
