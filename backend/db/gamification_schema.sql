-- Gamification Table
-- Run this SQL in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS user_gamification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL UNIQUE,
    total_xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    badges JSONB DEFAULT '[]'::jsonb,
    stats JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_user_gamification_user_id ON user_gamification(user_id);

-- Enable RLS
ALTER TABLE user_gamification ENABLE ROW LEVEL SECURITY;

-- Policy to allow service role full access
CREATE POLICY "Service role has full access to user_gamification"
    ON user_gamification
    FOR ALL
    USING (true)
    WITH CHECK (true);
