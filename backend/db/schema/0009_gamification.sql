-- Gamification that rewards learning (AGENTS.md Phase 7).

-- Every XP grant, so caps, toasts, weekly class boards and audits come from one place.
CREATE TABLE IF NOT EXISTS xp_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL,
    kind        TEXT NOT NULL,          -- mastery_gain | mistake_fixed | review_on_time | daily_goal | exam_plan_step | comeback
    xp          INTEGER NOT NULL,
    day         DATE NOT NULL,          -- the learner's local day (PLAN_TIMEZONE)
    dedupe_key  TEXT,                   -- the same achievement is never paid twice
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_xp_events_dedupe ON xp_events (user_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_xp_events_user_day ON xp_events (user_id, day, kind);
CREATE INDEX IF NOT EXISTS idx_xp_events_user_time ON xp_events (user_id, created_at DESC);

-- One adaptive goal per learner per day, fixed once created.
CREATE TABLE IF NOT EXISTS daily_goals (
    user_id       UUID NOT NULL,
    day           DATE NOT NULL,
    target        INTEGER NOT NULL,
    focus         JSONB NOT NULL DEFAULT '{}'::jsonb,   -- weakest topic, due reviews, why this size
    completed_at  TIMESTAMPTZ,
    PRIMARY KEY (user_id, day)
);
