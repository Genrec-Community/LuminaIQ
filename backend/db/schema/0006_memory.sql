-- Memory and context across sessions (AGENTS.md Phase 5).
-- Teachers never read these tables: only the student (and the tutor on their behalf).

-- Rolling summary of one project's chat: everything up to covered_until is summarised.
CREATE TABLE IF NOT EXISTS chat_summaries (
    project_id     UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL,
    summary        TEXT NOT NULL DEFAULT '',
    covered_until  TIMESTAMPTZ,                 -- created_at of the last summarised message
    covered_count  INTEGER NOT NULL DEFAULT 0,  -- messages summarised so far
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Long-term facts about a learner ("preparing for NEET in May", "likes cricket examples").
CREATE TABLE IF NOT EXISTS user_memories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL,
    project_id    UUID REFERENCES projects(id) ON DELETE SET NULL,   -- the book it came from (NULL = general)
    kind          TEXT NOT NULL DEFAULT 'fact',   -- goal | preference | struggle | interest | fact
    content       TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'chat',   -- chat (extracted) | user (typed in by the student)
    last_used_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_memories_user ON user_memories (user_id, last_used_at DESC);

-- Wrong answers, tagged with the likely misconception (filled in by a background job).
CREATE TABLE IF NOT EXISTS learner_mistakes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic           TEXT NOT NULL DEFAULT '',
    question        TEXT NOT NULL,
    wrong_answer    TEXT NOT NULL DEFAULT '',
    correct_answer  TEXT NOT NULL DEFAULT '',
    misconception   TEXT,                         -- NULL = not tagged yet, '' = none identified
    fixed_at        TIMESTAMPTZ,                  -- answered correctly later
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_learner_mistakes_user ON learner_mistakes (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learner_mistakes_project ON learner_mistakes (user_id, project_id, created_at DESC);

-- Where the student left off (last book, view, in-progress quiz, lesson position), for any device.
CREATE TABLE IF NOT EXISTS app_state (
    user_id     UUID PRIMARY KEY,
    state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
