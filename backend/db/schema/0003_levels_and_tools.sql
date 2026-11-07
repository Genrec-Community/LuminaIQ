-- Learner levels and tool control (AGENTS.md Phase 2).
-- Defaults live in services/tools_catalog.py; these rows only record changes.

-- Platform admin: which tools each level gets
CREATE TABLE IF NOT EXISTS level_tool_policies (
    level      TEXT NOT NULL,
    tool       TEXT NOT NULL,
    enabled    BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (level, tool)
);

-- Platform admin: other per-level switches
CREATE TABLE IF NOT EXISTS level_settings (
    level         TEXT PRIMARY KEY,
    hints_default BOOLEAN NOT NULL DEFAULT false,   -- hints-first starts on for this level
    outside_book  BOOLEAN NOT NULL DEFAULT true,    -- may answer beyond the book (labelled)
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Institution admin: per class
ALTER TABLE institution_classes ADD COLUMN IF NOT EXISTS level TEXT;
ALTER TABLE institution_classes ADD COLUMN IF NOT EXISTS hint_mode TEXT NOT NULL DEFAULT 'student_choice'
    CHECK (hint_mode IN ('always_on', 'always_off', 'student_choice'));
ALTER TABLE institution_classes ADD COLUMN IF NOT EXISTS allow_outside_book BOOLEAN NOT NULL DEFAULT true;

CREATE TABLE IF NOT EXISTS class_tool_policies (
    class_id   UUID NOT NULL REFERENCES institution_classes(id) ON DELETE CASCADE,
    tool       TEXT NOT NULL,
    enabled    BOOLEAN NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (class_id, tool)
);

-- Child-safety screening: counts only, never message content
CREATE TABLE IF NOT EXISTS safety_events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID,
    level      TEXT,
    category   TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_safety_events_created ON safety_events (created_at);
