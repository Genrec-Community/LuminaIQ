-- =====================================================
-- Supabase Schema for Flashcards and Mindmaps Storage
-- =====================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- FLASHCARD SETS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS flashcard_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for faster queries
    CONSTRAINT flashcard_sets_user_project_idx UNIQUE (user_id, project_id, title)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_user_id ON flashcard_sets(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_project_id ON flashcard_sets(project_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sets_created_at ON flashcard_sets(created_at DESC);

-- =====================================================
-- FLASHCARDS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS flashcards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    set_id UUID NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_flashcards_set_id ON flashcards(set_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_position ON flashcards(set_id, position);

-- =====================================================
-- FLASHCARD STUDY SESSIONS TABLE (Optional - for tracking progress)
-- =====================================================
CREATE TABLE IF NOT EXISTS flashcard_study_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    set_id UUID NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    cards_studied INTEGER DEFAULT 0,
    cards_correct INTEGER DEFAULT 0,
    cards_incorrect INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_user_id ON flashcard_study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_set_id ON flashcard_study_sessions(set_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_started_at ON flashcard_study_sessions(started_at DESC);

-- =====================================================
-- MINDMAPS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS mindmaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Store the mindmap data as JSONB for flexibility
    -- Structure: { nodes: [...], edges: [...], layout: {...} }
    data JSONB NOT NULL,
    
    -- Metadata
    document_ids UUID[] DEFAULT '{}',  -- Array of document IDs used to generate
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexes for faster queries
    CONSTRAINT mindmaps_user_project_title_idx UNIQUE (user_id, project_id, title)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_mindmaps_user_id ON mindmaps(user_id);
CREATE INDEX IF NOT EXISTS idx_mindmaps_project_id ON mindmaps(project_id);
CREATE INDEX IF NOT EXISTS idx_mindmaps_topic ON mindmaps(topic);
CREATE INDEX IF NOT EXISTS idx_mindmaps_created_at ON mindmaps(created_at DESC);

-- GIN index for JSONB data queries (optional, for advanced queries)
CREATE INDEX IF NOT EXISTS idx_mindmaps_data_gin ON mindmaps USING GIN (data);

-- =====================================================
-- MINDMAP INTERACTIONS TABLE (Optional - for analytics)
-- =====================================================
CREATE TABLE IF NOT EXISTS mindmap_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    mindmap_id UUID NOT NULL REFERENCES mindmaps(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,  -- 'view', 'export', 'edit', etc.
    duration_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_user_id ON mindmap_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_mindmap_id ON mindmap_interactions(mindmap_id);
CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_created_at ON mindmap_interactions(created_at DESC);

-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE flashcard_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;
ALTER TABLE flashcard_study_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mindmaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE mindmap_interactions ENABLE ROW LEVEL SECURITY;

-- Flashcard Sets Policies
DROP POLICY IF EXISTS "Users can view their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can view their own flashcard sets"
    ON flashcard_sets FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can create their own flashcard sets"
    ON flashcard_sets FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can update their own flashcard sets"
    ON flashcard_sets FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own flashcard sets" ON flashcard_sets;
CREATE POLICY "Users can delete their own flashcard sets"
    ON flashcard_sets FOR DELETE
    USING (auth.uid() = user_id);

-- Flashcards Policies
DROP POLICY IF EXISTS "Users can view flashcards from their sets" ON flashcards;
CREATE POLICY "Users can view flashcards from their sets"
    ON flashcards FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM flashcard_sets
        WHERE flashcard_sets.id = flashcards.set_id
        AND flashcard_sets.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "Users can create flashcards in their sets" ON flashcards;
CREATE POLICY "Users can create flashcards in their sets"
    ON flashcards FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM flashcard_sets
        WHERE flashcard_sets.id = flashcards.set_id
        AND flashcard_sets.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "Users can update flashcards in their sets" ON flashcards;
CREATE POLICY "Users can update flashcards in their sets"
    ON flashcards FOR UPDATE
    USING (EXISTS (
        SELECT 1 FROM flashcard_sets
        WHERE flashcard_sets.id = flashcards.set_id
        AND flashcard_sets.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "Users can delete flashcards from their sets" ON flashcards;
CREATE POLICY "Users can delete flashcards from their sets"
    ON flashcards FOR DELETE
    USING (EXISTS (
        SELECT 1 FROM flashcard_sets
        WHERE flashcard_sets.id = flashcards.set_id
        AND flashcard_sets.user_id = auth.uid()
    ));

-- Flashcard Study Sessions Policies
DROP POLICY IF EXISTS "Users can view their own study sessions" ON flashcard_study_sessions;
CREATE POLICY "Users can view their own study sessions"
    ON flashcard_study_sessions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own study sessions" ON flashcard_study_sessions;
CREATE POLICY "Users can create their own study sessions"
    ON flashcard_study_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own study sessions" ON flashcard_study_sessions;
CREATE POLICY "Users can update their own study sessions"
    ON flashcard_study_sessions FOR UPDATE
    USING (auth.uid() = user_id);

-- Mindmaps Policies
DROP POLICY IF EXISTS "Users can view their own mindmaps" ON mindmaps;
CREATE POLICY "Users can view their own mindmaps"
    ON mindmaps FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own mindmaps" ON mindmaps;
CREATE POLICY "Users can create their own mindmaps"
    ON mindmaps FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update their own mindmaps" ON mindmaps;
CREATE POLICY "Users can update their own mindmaps"
    ON mindmaps FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own mindmaps" ON mindmaps;
CREATE POLICY "Users can delete their own mindmaps"
    ON mindmaps FOR DELETE
    USING (auth.uid() = user_id);

-- Mindmap Interactions Policies
DROP POLICY IF EXISTS "Users can view their own mindmap interactions" ON mindmap_interactions;
CREATE POLICY "Users can view their own mindmap interactions"
    ON mindmap_interactions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can create their own mindmap interactions" ON mindmap_interactions;
CREATE POLICY "Users can create their own mindmap interactions"
    ON mindmap_interactions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- =====================================================
-- FUNCTIONS AND TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_flashcard_sets_updated_at
    BEFORE UPDATE ON flashcard_sets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_flashcards_updated_at
    BEFORE UPDATE ON flashcards
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_mindmaps_updated_at
    BEFORE UPDATE ON mindmaps
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to update node_count and edge_count in mindmaps
CREATE OR REPLACE FUNCTION update_mindmap_counts()
RETURNS TRIGGER AS $$
BEGIN
    NEW.node_count = jsonb_array_length(NEW.data->'nodes');
    NEW.edge_count = jsonb_array_length(NEW.data->'edges');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically update counts
CREATE TRIGGER update_mindmap_counts_trigger
    BEFORE INSERT OR UPDATE ON mindmaps
    FOR EACH ROW
    EXECUTE FUNCTION update_mindmap_counts();

-- =====================================================
-- EXAMPLE QUERIES
-- =====================================================

-- Get all flashcard sets for a user with card count
-- SELECT 
--     fs.*,
--     COUNT(f.id) as card_count
-- FROM flashcard_sets fs
-- LEFT JOIN flashcards f ON f.set_id = fs.id
-- WHERE fs.user_id = 'user-uuid'
-- GROUP BY fs.id
-- ORDER BY fs.created_at DESC;

-- Get all flashcards for a set
-- SELECT * FROM flashcards
-- WHERE set_id = 'set-uuid'
-- ORDER BY position ASC;

-- Get all mindmaps for a project
-- SELECT * FROM mindmaps
-- WHERE project_id = 'project-uuid'
-- AND user_id = 'user-uuid'
-- ORDER BY created_at DESC;

-- Get mindmap with full data
-- SELECT * FROM mindmaps
-- WHERE id = 'mindmap-uuid'
-- AND user_id = 'user-uuid';

-- =====================================================
-- NOTES
-- =====================================================
-- 1. The flashcards.position field allows for custom ordering of cards
-- 2. The mindmaps.data JSONB field stores the complete mindmap structure
-- 3. All tables have RLS enabled for security
-- 4. Indexes are created for common query patterns
-- 5. Triggers automatically update timestamps and counts
-- 6. Study sessions and interactions tables are optional for analytics
