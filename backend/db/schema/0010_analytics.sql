-- Platform analytics (admin dashboard).

-- One row per user per local day (PLAN_TIMEZONE) on which they used the app. Written by the
-- auth dependency at most once an hour per process, so it costs nothing per request.
-- Active users, stickiness and retention all come from here.
CREATE TABLE IF NOT EXISTS user_active_days (
    user_id  UUID NOT NULL,
    day      DATE NOT NULL,
    PRIMARY KEY (user_id, day)
);
CREATE INDEX IF NOT EXISTS idx_user_active_days_day ON user_active_days (day);

-- Seed from activity recorded before this table existed
INSERT INTO user_active_days (user_id, day)
SELECT user_id, day FROM (
    SELECT id AS user_id, (last_seen_at AT TIME ZONE 'Asia/Kolkata')::date AS day FROM app_users WHERE last_seen_at IS NOT NULL
    UNION SELECT user_id, (created_at AT TIME ZONE 'Asia/Kolkata')::date FROM ai_calls WHERE user_id IS NOT NULL
    UNION SELECT user_id, (created_at AT TIME ZONE 'Asia/Kolkata')::date FROM learning_events
    UNION SELECT user_id, day FROM xp_events
) seen
ON CONFLICT DO NOTHING;

-- Time-range scans for the dashboard
CREATE INDEX IF NOT EXISTS idx_app_users_created ON app_users (created_at);
CREATE INDEX IF NOT EXISTS idx_learning_events_created ON learning_events (created_at);
CREATE INDEX IF NOT EXISTS idx_payments_created ON payments (created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs (created_at);
CREATE INDEX IF NOT EXISTS idx_safety_events_created ON safety_events (created_at);
