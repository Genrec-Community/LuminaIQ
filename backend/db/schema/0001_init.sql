-- =============================================================================
-- Lumina IQ: application database (plain Postgres; Docker in dev, AWS RDS in prod)
-- =============================================================================
-- Supabase is used only for sign-in and file storage. Every table lives here.
-- Built on 2026-10-31 from the Supabase-era SQL files (fresh start, no data copy):
-- row-level security, policies, auth.users references and storage buckets were
-- dropped because the backend is the only client of this database and checks
-- ownership itself (api/access.py). Later changes go in new numbered files.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Users we have seen sign in (id from the Supabase token). Kept up to date by
-- api/deps.py so that SQL can join on email (e.g. unlimited_access).
CREATE TABLE IF NOT EXISTS app_users (
    id           UUID PRIMARY KEY,
    email        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_app_users_email ON app_users (lower(email));

-- ---- from fm.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS flashcard_sets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT flashcard_sets_user_project_idx UNIQUE (user_id, project_id, title)
);

CREATE INDEX IF NOT EXISTS idx_flashcard_sets_user_id ON flashcard_sets(user_id);

CREATE INDEX IF NOT EXISTS idx_flashcard_sets_project_id ON flashcard_sets(project_id);

CREATE INDEX IF NOT EXISTS idx_flashcard_sets_created_at ON flashcard_sets(created_at DESC);

CREATE TABLE IF NOT EXISTS flashcards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    set_id UUID NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flashcards_set_id ON flashcards(set_id);

CREATE INDEX IF NOT EXISTS idx_flashcards_position ON flashcards(set_id, position);

CREATE TABLE IF NOT EXISTS flashcard_study_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    set_id UUID NOT NULL REFERENCES flashcard_sets(id) ON DELETE CASCADE,
    cards_studied INTEGER DEFAULT 0,
    cards_correct INTEGER DEFAULT 0,
    cards_incorrect INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_user_id ON flashcard_study_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_set_id ON flashcard_study_sessions(set_id);

CREATE INDEX IF NOT EXISTS idx_flashcard_sessions_started_at ON flashcard_study_sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS mindmaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    topic VARCHAR(255) NOT NULL,
    description TEXT,
    
    data JSONB NOT NULL,
    
    document_ids UUID[] DEFAULT '{}',  -- Array of document IDs used to generate
    node_count INTEGER DEFAULT 0,
    edge_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT mindmaps_user_project_title_idx UNIQUE (user_id, project_id, title)
);

CREATE INDEX IF NOT EXISTS idx_mindmaps_user_id ON mindmaps(user_id);

CREATE INDEX IF NOT EXISTS idx_mindmaps_project_id ON mindmaps(project_id);

CREATE INDEX IF NOT EXISTS idx_mindmaps_topic ON mindmaps(topic);

CREATE INDEX IF NOT EXISTS idx_mindmaps_created_at ON mindmaps(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_mindmaps_data_gin ON mindmaps USING GIN (data);

CREATE TABLE IF NOT EXISTS mindmap_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    mindmap_id UUID NOT NULL REFERENCES mindmaps(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,  -- 'view', 'export', 'edit', etc.
    duration_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_user_id ON mindmap_interactions(user_id);

CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_mindmap_id ON mindmap_interactions(mindmap_id);

CREATE INDEX IF NOT EXISTS idx_mindmap_interactions_created_at ON mindmap_interactions(created_at DESC);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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

CREATE OR REPLACE FUNCTION update_mindmap_counts()
RETURNS TRIGGER AS $$
BEGIN
    NEW.node_count = jsonb_array_length(NEW.data->'nodes');
    NEW.edge_count = jsonb_array_length(NEW.data->'edges');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_mindmap_counts_trigger
    BEFORE INSERT OR UPDATE ON mindmaps
    FOR EACH ROW
    EXECUTE FUNCTION update_mindmap_counts();

-- ---- from supabase_schema_all_tables.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);

CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(512) NOT NULL,
    file_type VARCHAR(50),
    file_size INTEGER,
    upload_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    topics JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);

CREATE INDEX IF NOT EXISTS idx_documents_upload_status ON documents(upload_status);

CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_project_id ON chat_messages(project_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT notes_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);

CREATE INDEX IF NOT EXISTS idx_notes_project_id ON notes(project_id);

CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT user_settings_user_unique UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

CREATE TABLE IF NOT EXISTS bookmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    title VARCHAR(500),
    note TEXT,
    type VARCHAR(100),
    highlight_text TEXT,
    color VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id);

CREATE INDEX IF NOT EXISTS idx_bookmarks_project_id ON bookmarks(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_bookmarks_created_at ON bookmarks(created_at DESC);

CREATE TABLE IF NOT EXISTS study_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    activity_date DATE NOT NULL DEFAULT CURRENT_DATE,
    quiz INTEGER NOT NULL DEFAULT 0,
    review INTEGER NOT NULL DEFAULT 0,
    notes INTEGER NOT NULL DEFAULT 0,
    qa INTEGER NOT NULL DEFAULT 0,
    pomodoro INTEGER NOT NULL DEFAULT 0,
    chat INTEGER NOT NULL DEFAULT 0,
    exam INTEGER NOT NULL DEFAULT 0,
    path INTEGER NOT NULL DEFAULT 0,
    knowledge_graph INTEGER NOT NULL DEFAULT 0,
    quiz_scores JSONB DEFAULT '[]'::jsonb,
    total INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT study_activity_user_project_date_unique UNIQUE (user_id, project_id, activity_date)
);

CREATE INDEX IF NOT EXISTS idx_study_activity_user_id ON study_activity(user_id);

CREATE INDEX IF NOT EXISTS idx_study_activity_project_id ON study_activity(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_study_activity_date ON study_activity(activity_date DESC);

CREATE INDEX IF NOT EXISTS idx_study_activity_lookup ON study_activity(user_id, project_id, activity_date);

CREATE TABLE IF NOT EXISTS exam_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    exam_date DATE NOT NULL,
    topics JSONB DEFAULT '[]'::jsonb,
    difficulty VARCHAR(50) DEFAULT 'medium',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exam_schedules_user_id ON exam_schedules(user_id);

CREATE INDEX IF NOT EXISTS idx_exam_schedules_project_id ON exam_schedules(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_exam_schedules_date ON exam_schedules(exam_date ASC);

CREATE TABLE IF NOT EXISTS learning_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    completed_topics JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT learning_progress_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_learning_progress_user_id ON learning_progress(user_id);

CREATE INDEX IF NOT EXISTS idx_learning_progress_project_id ON learning_progress(user_id, project_id);

CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    sessions INTEGER NOT NULL DEFAULT 0,
    focus_time_minutes INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pomodoro_user_id ON pomodoro_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_pomodoro_session_date ON pomodoro_sessions(user_id, session_date);

CREATE INDEX IF NOT EXISTS idx_pomodoro_document ON pomodoro_sessions(user_id, document_id, session_date);

CREATE TABLE IF NOT EXISTS recent_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recent_searches_user_id ON recent_searches(user_id);

CREATE INDEX IF NOT EXISTS idx_recent_searches_lookup ON recent_searches(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_recent_searches_dedup ON recent_searches(user_id, project_id, query);

CREATE INDEX IF NOT EXISTS idx_recent_searches_created_at ON recent_searches(created_at DESC);

CREATE TABLE IF NOT EXISTS study_streaks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_study_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT study_streaks_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_study_streaks_user_id ON study_streaks(user_id);

CREATE INDEX IF NOT EXISTS idx_study_streaks_project_id ON study_streaks(user_id, project_id);

CREATE TABLE IF NOT EXISTS user_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500) NOT NULL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    last_attempt TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    history JSONB DEFAULT '[]'::jsonb,

    CONSTRAINT user_performance_user_project_topic_unique UNIQUE (user_id, project_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_user_performance_user_id ON user_performance(user_id);

CREATE INDEX IF NOT EXISTS idx_user_performance_lookup ON user_performance(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_user_performance_topic ON user_performance(user_id, project_id, topic);

CREATE INDEX IF NOT EXISTS idx_user_performance_last_attempt ON user_performance(last_attempt DESC);

CREATE TABLE IF NOT EXISTS review_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    easiness_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 1,
    repetition INTEGER NOT NULL DEFAULT 0,
    next_review TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_reviewed TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_cards_user_id ON review_cards(user_id);

CREATE INDEX IF NOT EXISTS idx_review_cards_project_id ON review_cards(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_review_cards_next_review ON review_cards(user_id, project_id, next_review ASC);

CREATE TABLE IF NOT EXISTS mcq_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_name VARCHAR(500),
    questions TEXT NOT NULL,  -- JSON stored as TEXT (parsed with json.loads in code)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcq_tests_project_id ON mcq_tests(project_id);

CREATE TABLE IF NOT EXISTS subjective_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500),
    questions TEXT NOT NULL,  -- JSON stored as TEXT
    results TEXT,             -- JSON stored as TEXT (set after evaluation)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subjective_tests_project_id ON subjective_tests(project_id);

CREATE TABLE IF NOT EXISTS answer_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    question TEXT NOT NULL,
    user_answer TEXT NOT NULL,
    ai_feedback TEXT NOT NULL,  -- JSON stored as TEXT
    score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_answer_evaluations_user_id ON answer_evaluations(user_id);

CREATE INDEX IF NOT EXISTS idx_answer_evaluations_project_id ON answer_evaluations(project_id);

CREATE TABLE IF NOT EXISTS topic_relations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_topic VARCHAR(500) NOT NULL,
    to_topic VARCHAR(500) NOT NULL,
    relation_type VARCHAR(100) DEFAULT 'related',
    weight DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topic_relations_project_id ON topic_relations(project_id);

CREATE INDEX IF NOT EXISTS idx_topic_relations_from ON topic_relations(project_id, from_topic);

CREATE INDEX IF NOT EXISTS idx_topic_relations_to ON topic_relations(project_id, to_topic);

CREATE INDEX IF NOT EXISTS idx_topic_relations_type ON topic_relations(project_id, relation_type);

CREATE TABLE IF NOT EXISTS topic_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500) NOT NULL,
    summary TEXT,
    sources JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT topic_summaries_project_topic_unique UNIQUE (project_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_topic_summaries_project_id ON topic_summaries(project_id);

CREATE INDEX IF NOT EXISTS idx_topic_summaries_lookup ON topic_summaries(project_id, topic);

CREATE TABLE IF NOT EXISTS graph_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    topic VARCHAR(500),
    event_type VARCHAR(100) NOT NULL,
    duration_ms INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_graph_analytics_project_id ON graph_analytics(project_id);

CREATE INDEX IF NOT EXISTS idx_graph_analytics_user_id ON graph_analytics(user_id);

CREATE INDEX IF NOT EXISTS idx_graph_analytics_lookup ON graph_analytics(project_id, user_id);

CREATE INDEX IF NOT EXISTS idx_graph_analytics_created_at ON graph_analytics(created_at DESC);

CREATE TABLE IF NOT EXISTS learning_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    topics_visited JSONB DEFAULT '[]'::jsonb,
    total_time_ms INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_id ON learning_sessions(user_id);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_project_id ON learning_sessions(project_id);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_lookup ON learning_sessions(project_id, user_id);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_started_at ON learning_sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS user_gamification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL UNIQUE,
    total_xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    badges JSONB NOT NULL DEFAULT '[]'::jsonb,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_gamification_user_id ON user_gamification(user_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_flashcard_sets_project'
        AND table_name = 'flashcard_sets'
    ) THEN
        ALTER TABLE flashcard_sets
            ADD CONSTRAINT fk_flashcard_sets_project
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_mindmaps_project'
        AND table_name = 'mindmaps'
    ) THEN
        ALTER TABLE mindmaps
            ADD CONSTRAINT fk_mindmaps_project
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
    END IF;
END $$;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT unnest(ARRAY[
            'projects', 'documents', 'notes', 'user_settings',
            'bookmarks', 'pomodoro_sessions', 'study_streaks',
            'learning_progress', 'user_gamification'
        ])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS update_%s_updated_at ON %I', tbl, tbl);
        EXECUTE format(
            'CREATE TRIGGER update_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
            tbl, tbl
        );
    END LOOP;
END $$;

-- ---- from supabase_schema_roles_auth.sql
CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID PRIMARY KEY,
    role VARCHAR(50) NOT NULL DEFAULT 'handler',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

DO $$
BEGIN
    DROP TRIGGER IF EXISTS update_user_roles_updated_at ON user_roles;
    CREATE TRIGGER update_user_roles_updated_at 
        BEFORE UPDATE ON user_roles 
        FOR EACH ROW 
        EXECUTE FUNCTION update_updated_at_column();
EXCEPTION
    WHEN undefined_function THEN
        RAISE NOTICE 'update_updated_at_column() function missing, skipping trigger';
END $$;

-- ---- from 003_adaptive_learning.sql
CREATE TABLE IF NOT EXISTS user_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    last_attempt TIMESTAMPTZ DEFAULT NOW(),
    history JSONB DEFAULT '[]'::jsonb,  -- Sliding window of recent attempts
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_user_project_topic UNIQUE(user_id, project_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_performance_user_project 
    ON user_performance(user_id, project_id);

CREATE INDEX IF NOT EXISTS idx_performance_weakness 
    ON user_performance(user_id, project_id, wrong_count DESC);

CREATE TABLE IF NOT EXISTS review_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    
    easiness_factor FLOAT DEFAULT 2.5,  -- EF: 1.3 to 2.5
    interval_days INTEGER DEFAULT 0,     -- Days until next review
    repetition INTEGER DEFAULT 0,        -- Number of successful reviews
    next_review TIMESTAMPTZ DEFAULT NOW(),
    last_reviewed TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_cards_due 
    ON review_cards(user_id, next_review ASC);

CREATE INDEX IF NOT EXISTS idx_review_cards_project 
    ON review_cards(user_id, project_id, next_review ASC);

CREATE INDEX IF NOT EXISTS idx_review_cards_topic 
    ON review_cards(user_id, project_id, topic);

CREATE TABLE IF NOT EXISTS topic_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_topic TEXT NOT NULL,
    to_topic TEXT NOT NULL,
    relation_type TEXT DEFAULT 'related' CHECK (relation_type IN ('prerequisite', 'related', 'subtopic')),
    weight FLOAT DEFAULT 0.5 CHECK (weight >= 0.1 AND weight <= 1.0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_project_edge UNIQUE(project_id, from_topic, to_topic)
);

CREATE INDEX IF NOT EXISTS idx_topic_relations_from 
    ON topic_relations(project_id, from_topic);

CREATE INDEX IF NOT EXISTS idx_topic_relations_to 
    ON topic_relations(project_id, to_topic);

CREATE INDEX IF NOT EXISTS idx_topic_relations_type 
    ON topic_relations(project_id, relation_type);

/*
INSERT INTO user_performance (user_id, project_id, topic, correct_count, wrong_count)
VALUES 
    ('your-user-id', 'your-project-id', 'Introduction', 8, 2),
    ('your-user-id', 'your-project-id', 'Chapter 1', 5, 5),
    ('your-user-id', 'your-project-id', 'Chapter 2', 3, 7);

INSERT INTO topic_relations (project_id, from_topic, to_topic, relation_type, weight)
VALUES
    ('your-project-id', 'Introduction', 'Chapter 1', 'prerequisite', 0.9),
    ('your-project-id', 'Chapter 1', 'Chapter 2', 'prerequisite', 0.8),
    ('your-project-id', 'Chapter 1', 'Chapter 3', 'prerequisite', 0.7);

*/;

-- ---- from 004_topic_outline.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS topic_outline JSONB DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_documents_project_status_created
    ON documents (project_id, upload_status, created_at);

CREATE INDEX IF NOT EXISTS idx_topic_relations_project_type
    ON topic_relations (project_id, relation_type);

-- ---- from 005_topic_cards.sql
CREATE TABLE IF NOT EXISTS topic_cards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    kind        TEXT NOT NULL,              -- 'cram' | 'visual' | 'coverage'
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, topic, kind)
);

-- ---- from 006_shared_book_library.sql
CREATE TABLE IF NOT EXISTS shared_books (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sketch       JSONB NOT NULL,          -- smallest 128 shingle hashes
    sketch_keys  BIGINT[] NOT NULL,       -- smallest 16, for candidate lookup
    title        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shared_books_sketch_keys ON shared_books USING GIN (sketch_keys);

CREATE TABLE IF NOT EXISTS document_books (
    document_id  UUID PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    book_id      UUID NOT NULL REFERENCES shared_books(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_document_books_book ON document_books (book_id);

CREATE TABLE IF NOT EXISTS shared_topic_assets (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id       UUID NOT NULL REFERENCES shared_books(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    topic_key     TEXT NOT NULL,          -- normalised topic name
    kind          TEXT NOT NULL,          -- 'visual' | 'cram'
    content       JSONB NOT NULL DEFAULT '{}'::jsonb,
    storage_path  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (book_id, topic_key, kind)
);

-- ---- from 007_plans_and_usage.sql
CREATE TABLE IF NOT EXISTS user_plans (
    user_id                  UUID PRIMARY KEY,
    plan                     TEXT NOT NULL DEFAULT 'free',     -- free | scholar | topper | institution
    status                   TEXT NOT NULL DEFAULT 'active',   -- active | authenticated | pending | halted | cancelled | expired
    source                   TEXT NOT NULL DEFAULT 'manual',   -- razorpay | pass | institution | manual
    billing_cycle            TEXT,                              -- monthly | yearly
    current_period_end       TIMESTAMPTZ,                       -- NULL = no expiry
    cancel_at_period_end     BOOLEAN NOT NULL DEFAULT false,
    razorpay_subscription_id TEXT UNIQUE,
    razorpay_customer_id     TEXT,
    institution_id           UUID,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_counters (
    user_id     UUID NOT NULL,
    feature     TEXT NOT NULL,
    period      TEXT NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, feature, period)
);

CREATE TABLE IF NOT EXISTS llm_usage_daily (
    user_id        UUID,
    day            DATE NOT NULL,
    model          TEXT NOT NULL,
    feature        TEXT NOT NULL,
    calls          INTEGER NOT NULL DEFAULT 0,
    input_tokens   BIGINT NOT NULL DEFAULT 0,
    output_tokens  BIGINT NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_llm_usage_daily_key
    ON llm_usage_daily (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), day, model, feature);

CREATE TABLE IF NOT EXISTS payments (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID,
    kind                     TEXT NOT NULL,            -- subscription | pass | seats
    plan                     TEXT,
    amount_paise             INTEGER,
    currency                 TEXT DEFAULT 'INR',
    status                   TEXT NOT NULL,            -- created | paid | failed | refunded
    razorpay_order_id        TEXT,
    razorpay_payment_id      TEXT UNIQUE,
    razorpay_subscription_id TEXT,
    raw                      JSONB,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payments_user ON payments (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS billing_events (
    event_id    TEXT PRIMARY KEY,
    event       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION consume_usage(p_user UUID, p_feature TEXT, p_period TEXT, p_amount INTEGER, p_limit INTEGER)
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v INTEGER;
BEGIN
    INSERT INTO usage_counters (user_id, feature, period, count)
    VALUES (p_user, p_feature, p_period, 0)
    ON CONFLICT (user_id, feature, period) DO NOTHING;

    UPDATE usage_counters
       SET count = count + p_amount, updated_at = now()
     WHERE user_id = p_user AND feature = p_feature AND period = p_period
       AND (p_limit < 0 OR count + p_amount <= p_limit)
    RETURNING count INTO v;

    RETURN COALESCE(v, -1);
END $$;

CREATE OR REPLACE FUNCTION add_llm_usage(p_user UUID, p_day DATE, p_model TEXT, p_feature TEXT, p_input BIGINT, p_output BIGINT)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO llm_usage_daily (user_id, day, model, feature, calls, input_tokens, output_tokens)
    VALUES (p_user, p_day, p_model, p_feature, 1, p_input, p_output)
    ON CONFLICT (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), day, model, feature)
    DO UPDATE SET calls = llm_usage_daily.calls + 1,
                  input_tokens = llm_usage_daily.input_tokens + EXCLUDED.input_tokens,
                  output_tokens = llm_usage_daily.output_tokens + EXCLUDED.output_tokens;
END $$;

-- ---- from 008_exam_night_pass.sql
ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS pass_until TIMESTAMPTZ;

-- ---- from 009_institutions.sql
CREATE TABLE IF NOT EXISTS institutions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT NOT NULL,
    owner_user_id  UUID NOT NULL,
    contact_email  TEXT,
    billing_name   TEXT,
    gstin          TEXT,
    seats          INTEGER NOT NULL DEFAULT 25,          -- student seats
    status         TEXT NOT NULL DEFAULT 'trial',        -- trial | active | expired
    paid_until     TIMESTAMPTZ,                          -- trial end or paid-up date
    teacher_code   TEXT NOT NULL UNIQUE,                 -- teachers join with this
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS institution_members (
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    user_id        UUID NOT NULL,
    role           TEXT NOT NULL,                        -- admin | teacher | student
    display_name   TEXT,
    email          TEXT,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (institution_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_institution_members_user ON institution_members (user_id);

CREATE TABLE IF NOT EXISTS institution_classes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    invite_code    TEXT NOT NULL UNIQUE,                 -- students join with this
    created_by     UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS class_members (
    class_id   UUID NOT NULL REFERENCES institution_classes(id) ON DELETE CASCADE,
    user_id    UUID NOT NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (class_id, user_id)
);

CREATE TABLE IF NOT EXISTS class_books (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    class_id           UUID NOT NULL REFERENCES institution_classes(id) ON DELETE CASCADE,
    source_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title              TEXT,
    published_by       UUID,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (class_id, source_document_id)
);

CREATE TABLE IF NOT EXISTS class_book_copies (
    class_book_id UUID NOT NULL REFERENCES class_books(id) ON DELETE CASCADE,
    user_id       UUID NOT NULL,
    document_id   UUID REFERENCES documents(id) ON DELETE CASCADE,
    PRIMARY KEY (class_book_id, user_id)
);

-- ---- from 011_ocr_usage.sql
create table if not exists ocr_usage (
  provider text not null,
  month text not null,            -- 'YYYY-MM' (UTC)
  pages integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (provider, month)
);

create or replace function reserve_ocr_pages(p_provider text, p_month text, p_pages integer, p_cap integer)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  used integer;
  granted integer;
begin
  insert into ocr_usage (provider, month, pages) values (p_provider, p_month, 0)
  on conflict (provider, month) do nothing;
  select pages into used from ocr_usage where provider = p_provider and month = p_month for update;
  granted := greatest(0, least(p_pages, p_cap - used));
  if granted > 0 then
    update ocr_usage set pages = pages + granted, updated_at = now()
    where provider = p_provider and month = p_month;
  end if;
  return granted;
end;
$$;

-- ---- from 012_document_progress.sql
alter table documents add column if not exists progress jsonb;

-- ---- from 013_learning_engine.sql
ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS kind TEXT;

ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION;

ALTER TABLE topic_relations ADD COLUMN IF NOT EXISTS evidence TEXT;

CREATE TABLE IF NOT EXISTS learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
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
    user_id UUID NOT NULL,
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

-- ---- from 014_school_accounts_and_approval.sql
ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approval_note   TEXT;

ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approved_at     TIMESTAMPTZ;

ALTER TABLE institutions ADD COLUMN IF NOT EXISTS approved_by     UUID;

ALTER TABLE institutions ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMPTZ;

ALTER TABLE institutions ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE institutions ALTER COLUMN paid_until DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'institutions'
                      AND column_name = 'approval_status') THEN
        ALTER TABLE institutions ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending';
        UPDATE institutions SET approval_status = 'approved', approved_at = now();
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_institutions_approval ON institutions (approval_status, paid_until);

CREATE INDEX IF NOT EXISTS idx_institutions_paid_until ON institutions (paid_until);

CREATE INDEX IF NOT EXISTS idx_institutions_owner ON institutions (owner_user_id);

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS login_id             TEXT;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS reg_no               TEXT;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS managed              BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS disabled             BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS created_by           UUID;

ALTER TABLE institution_members ADD COLUMN IF NOT EXISTS password_changed_at  TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_members_login_id
    ON institution_members (lower(login_id)) WHERE login_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_institution_members_reg_no
    ON institution_members (institution_id, lower(reg_no)) WHERE reg_no IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_institution_members_inst_role
    ON institution_members (institution_id, role, disabled);

CREATE INDEX IF NOT EXISTS idx_institution_classes_inst ON institution_classes (institution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_class_members_user ON class_members (user_id);

CREATE INDEX IF NOT EXISTS idx_class_books_class ON class_books (class_id);

CREATE INDEX IF NOT EXISTS idx_class_book_copies_user ON class_book_copies (user_id);

CREATE INDEX IF NOT EXISTS idx_payments_order ON payments (razorpay_order_id);

CREATE INDEX IF NOT EXISTS idx_user_plans_institution ON user_plans (institution_id) WHERE institution_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS institution_audit (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    actor_user_id  UUID,
    action         TEXT NOT NULL,
    detail         JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_institution_audit_inst ON institution_audit (institution_id, created_at DESC);

-- ---- from 015_plan_periods.sql
ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMPTZ;

ALTER TABLE user_plans ADD COLUMN IF NOT EXISTS last_payment_at TIMESTAMPTZ;

ALTER TABLE payments ADD COLUMN IF NOT EXISTS period_start TIMESTAMPTZ;

ALTER TABLE payments ADD COLUMN IF NOT EXISTS period_end TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_payments_order ON payments (razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payments_subscription ON payments (razorpay_subscription_id) WHERE razorpay_subscription_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_plans_period_end ON user_plans (current_period_end) WHERE source = 'razorpay';

-- ---- from 016_unlimited_access.sql
CREATE TABLE IF NOT EXISTS unlimited_access (
    email    TEXT PRIMARY KEY CHECK (email = lower(email)),
    note     TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION is_unlimited(p_user UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM app_users u
        JOIN unlimited_access a ON a.email = lower(u.email)
        WHERE u.id = p_user
    );
$$;

-- ---- from add_notes_metadata_columns.sql
ALTER TABLE notes ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE notes ADD COLUMN IF NOT EXISTS note_type TEXT;

ALTER TABLE notes ADD COLUMN IF NOT EXISTS topic TEXT;

ALTER TABLE notes DROP CONSTRAINT IF EXISTS notes_project_id_user_id_key;

-- ---- from fix_updated_at_trigger.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
EXCEPTION
    WHEN undefined_column THEN
        RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ---- tables that only ever existed in the Supabase dashboard (rebuilt from code)

-- Columns the code uses that were added by hand in Supabase
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_url TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS text_storage_path TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS user_id UUID;
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents (user_id);

CREATE TABLE IF NOT EXISTS project_summaries (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    summary    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Book store: books users chose to share publicly (services/book_service.py)
CREATE TABLE IF NOT EXISTS books (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL,
    document_id  UUID REFERENCES documents(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    author       TEXT,
    description  TEXT,
    cover_url    TEXT,
    tags         TEXT[] NOT NULL DEFAULT '{}',
    file_size    BIGINT,
    file_type    TEXT,
    text_path    TEXT,
    is_public    BOOLEAN NOT NULL DEFAULT true,
    import_count INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_books_public_rank ON books (is_public, import_count DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_books_user ON books (user_id);
CREATE INDEX IF NOT EXISTS idx_books_tags ON books USING GIN (tags);

CREATE TABLE IF NOT EXISTS book_imports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id     UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL,
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_book_imports_lookup ON book_imports (book_id, project_id, user_id);

CREATE OR REPLACE FUNCTION increment_book_import_count(book_id_input UUID)
RETURNS VOID LANGUAGE sql AS $$
    UPDATE books SET import_count = import_count + 1 WHERE id = book_id_input;
$$;
