-- Durable background jobs, a shared cache and rate-limit counters, so any number
-- of web and worker processes can run side by side (AGENTS.md Phase 1).

CREATE TABLE IF NOT EXISTS jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind         TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued', 'running', 'done', 'failed')),
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),
    pinned_host  TEXT,            -- only this host may run it (the input file is on its disk)
    locked_by    TEXT,
    heartbeat_at TIMESTAMPTZ,
    result       JSONB,
    error        TEXT,
    user_id      UUID,
    dedupe_key   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs (status, run_after) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_jobs_running ON jobs (heartbeat_at) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id, created_at DESC);
-- One live job per dedupe key (a double-tapped upload queues once)
CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_live_dedupe ON jobs (dedupe_key)
    WHERE dedupe_key IS NOT NULL AND status IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS cache_entries (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires ON cache_entries (expires_at);

CREATE TABLE IF NOT EXISTS rate_limit_counters (
    key          TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_window ON rate_limit_counters (window_start);
