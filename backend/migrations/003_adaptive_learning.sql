-- ============================================================
-- LUMINA IQ - Adaptive Learning System Database Migration
-- ============================================================
-- Run this in Supabase SQL Editor
-- 
-- Tables Created:
-- 1. user_performance - Track quiz scores per topic
-- 2. review_cards - Spaced repetition cards (SM-2 algorithm)
-- 3. topic_relations - Knowledge graph edges
-- ============================================================

-- ============================================================
-- 1. USER PERFORMANCE TABLE
-- ============================================================
-- Tracks quiz performance per topic for weakness detection
-- DSA: HashMap lookups via (user_id, project_id, topic) index

CREATE TABLE IF NOT EXISTS user_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    last_attempt TIMESTAMPTZ DEFAULT NOW(),
    history JSONB DEFAULT '[]'::jsonb,  -- Sliding window of recent attempts
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint for upsert pattern
    CONSTRAINT unique_user_project_topic UNIQUE(user_id, project_id, topic)
);

-- Index for fast lookups by user and project
CREATE INDEX IF NOT EXISTS idx_performance_user_project 
    ON user_performance(user_id, project_id);

-- Index for finding weak topics (sorted by wrong_count)
CREATE INDEX IF NOT EXISTS idx_performance_weakness 
    ON user_performance(user_id, project_id, wrong_count DESC);

-- RLS Policies
ALTER TABLE user_performance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own performance" 
    ON user_performance FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own performance" 
    ON user_performance FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own performance" 
    ON user_performance FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own performance" 
    ON user_performance FOR DELETE 
    USING (auth.uid() = user_id);


-- ============================================================
-- 2. REVIEW CARDS TABLE
-- ============================================================
-- Spaced repetition cards using SM-2 algorithm
-- DSA: Priority Queue behavior via next_review index

CREATE TABLE IF NOT EXISTS review_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    
    -- SM-2 Algorithm fields
    easiness_factor FLOAT DEFAULT 2.5,  -- EF: 1.3 to 2.5
    interval_days INTEGER DEFAULT 0,     -- Days until next review
    repetition INTEGER DEFAULT 0,        -- Number of successful reviews
    next_review TIMESTAMPTZ DEFAULT NOW(),
    last_reviewed TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Priority Queue index: Get cards due for review (earliest first)
CREATE INDEX IF NOT EXISTS idx_review_cards_due 
    ON review_cards(user_id, next_review ASC);

-- Index for filtering by project
CREATE INDEX IF NOT EXISTS idx_review_cards_project 
    ON review_cards(user_id, project_id, next_review ASC);

-- Index for finding cards by topic
CREATE INDEX IF NOT EXISTS idx_review_cards_topic 
    ON review_cards(user_id, project_id, topic);

-- RLS Policies
ALTER TABLE review_cards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own cards" 
    ON review_cards FOR SELECT 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own cards" 
    ON review_cards FOR INSERT 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own cards" 
    ON review_cards FOR UPDATE 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own cards" 
    ON review_cards FOR DELETE 
    USING (auth.uid() = user_id);


-- ============================================================
-- 3. TOPIC RELATIONS TABLE
-- ============================================================
-- Knowledge Graph edges (Adjacency List storage)
-- DSA: Graph representation for BFS/DFS/Topological Sort

CREATE TABLE IF NOT EXISTS topic_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_topic TEXT NOT NULL,
    to_topic TEXT NOT NULL,
    relation_type TEXT DEFAULT 'related' CHECK (relation_type IN ('prerequisite', 'related', 'subtopic')),
    weight FLOAT DEFAULT 0.5 CHECK (weight >= 0.1 AND weight <= 1.0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicate edges
    CONSTRAINT unique_project_edge UNIQUE(project_id, from_topic, to_topic)
);

-- Adjacency List index: Get all edges from a topic
CREATE INDEX IF NOT EXISTS idx_topic_relations_from 
    ON topic_relations(project_id, from_topic);

-- Index for reverse lookups (prerequisites)
CREATE INDEX IF NOT EXISTS idx_topic_relations_to 
    ON topic_relations(project_id, to_topic);

-- Index for filtering by relation type
CREATE INDEX IF NOT EXISTS idx_topic_relations_type 
    ON topic_relations(project_id, relation_type);

-- RLS Policies (project-based access)
ALTER TABLE topic_relations ENABLE ROW LEVEL SECURITY;

-- Users can view relations for projects they own
CREATE POLICY "Users can view project topic relations" 
    ON topic_relations FOR SELECT 
    USING (
        EXISTS (
            SELECT 1 FROM projects 
            WHERE projects.id = topic_relations.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert project topic relations" 
    ON topic_relations FOR INSERT 
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects 
            WHERE projects.id = topic_relations.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update project topic relations" 
    ON topic_relations FOR UPDATE 
    USING (
        EXISTS (
            SELECT 1 FROM projects 
            WHERE projects.id = topic_relations.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete project topic relations" 
    ON topic_relations FOR DELETE 
    USING (
        EXISTS (
            SELECT 1 FROM projects 
            WHERE projects.id = topic_relations.project_id 
            AND projects.user_id = auth.uid()
        )
    );


-- ============================================================
-- VERIFICATION QUERIES
-- ============================================================
-- Run these to verify tables were created correctly

-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('user_performance', 'review_cards', 'topic_relations');

-- Check indexes
SELECT indexname, tablename FROM pg_indexes 
WHERE tablename IN ('user_performance', 'review_cards', 'topic_relations');

-- ============================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================
/*
-- Insert sample performance data
INSERT INTO user_performance (user_id, project_id, topic, correct_count, wrong_count)
VALUES 
    ('your-user-id', 'your-project-id', 'Introduction', 8, 2),
    ('your-user-id', 'your-project-id', 'Chapter 1', 5, 5),
    ('your-user-id', 'your-project-id', 'Chapter 2', 3, 7);

-- Insert sample topic relations
INSERT INTO topic_relations (project_id, from_topic, to_topic, relation_type, weight)
VALUES
    ('your-project-id', 'Introduction', 'Chapter 1', 'prerequisite', 0.9),
    ('your-project-id', 'Chapter 1', 'Chapter 2', 'prerequisite', 0.8),
    ('your-project-id', 'Chapter 1', 'Chapter 3', 'prerequisite', 0.7);
*/
