-- =====================================================
-- LuminaIQ: Complete Supabase Schema
-- All tables NOT covered by supabase_schema_flashcards_mindmaps.sql
-- Safe to run on existing DB (uses IF NOT EXISTS everywhere)
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- 1. PROJECTS
-- =====================================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);

-- =====================================================
-- 2. DOCUMENTS
-- =====================================================
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

-- =====================================================
-- 3. CHAT MESSAGES
-- =====================================================
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

-- =====================================================
-- 4. NOTES
-- =====================================================
CREATE TABLE IF NOT EXISTS notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One note document per user per project
    CONSTRAINT notes_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes(user_id);
CREATE INDEX IF NOT EXISTS idx_notes_project_id ON notes(project_id);

-- =====================================================
-- 5. USER SETTINGS
-- =====================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT user_settings_user_unique UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);

-- =====================================================
-- 6. BOOKMARKS
-- =====================================================
CREATE TABLE IF NOT EXISTS bookmarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

-- =====================================================
-- 7. STUDY ACTIVITY
-- =====================================================
CREATE TABLE IF NOT EXISTS study_activity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

    -- One row per user per project per day
    CONSTRAINT study_activity_user_project_date_unique UNIQUE (user_id, project_id, activity_date)
);

CREATE INDEX IF NOT EXISTS idx_study_activity_user_id ON study_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_study_activity_project_id ON study_activity(user_id, project_id);
CREATE INDEX IF NOT EXISTS idx_study_activity_date ON study_activity(activity_date DESC);
CREATE INDEX IF NOT EXISTS idx_study_activity_lookup ON study_activity(user_id, project_id, activity_date);

-- =====================================================
-- 8. EXAM SCHEDULES
-- =====================================================
CREATE TABLE IF NOT EXISTS exam_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

-- =====================================================
-- 9. LEARNING PROGRESS
-- =====================================================
CREATE TABLE IF NOT EXISTS learning_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    completed_topics JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One row per user per project (upsert target)
    CONSTRAINT learning_progress_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_learning_progress_user_id ON learning_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_progress_project_id ON learning_progress(user_id, project_id);

-- =====================================================
-- 10. POMODORO SESSIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

-- =====================================================
-- 11. RECENT SEARCHES
-- =====================================================
CREATE TABLE IF NOT EXISTS recent_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recent_searches_user_id ON recent_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_recent_searches_lookup ON recent_searches(user_id, project_id);
CREATE INDEX IF NOT EXISTS idx_recent_searches_dedup ON recent_searches(user_id, project_id, query);
CREATE INDEX IF NOT EXISTS idx_recent_searches_created_at ON recent_searches(created_at DESC);

-- =====================================================
-- 12. STUDY STREAKS
-- =====================================================
CREATE TABLE IF NOT EXISTS study_streaks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    current_streak INTEGER NOT NULL DEFAULT 0,
    longest_streak INTEGER NOT NULL DEFAULT 0,
    last_study_date DATE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One streak record per user per project
    CONSTRAINT study_streaks_user_project_unique UNIQUE (user_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_study_streaks_user_id ON study_streaks(user_id);
CREATE INDEX IF NOT EXISTS idx_study_streaks_project_id ON study_streaks(user_id, project_id);

-- =====================================================
-- 13. USER PERFORMANCE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500) NOT NULL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    last_attempt TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    history JSONB DEFAULT '[]'::jsonb,

    -- One record per user per project per topic
    CONSTRAINT user_performance_user_project_topic_unique UNIQUE (user_id, project_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_user_performance_user_id ON user_performance(user_id);
CREATE INDEX IF NOT EXISTS idx_user_performance_lookup ON user_performance(user_id, project_id);
CREATE INDEX IF NOT EXISTS idx_user_performance_topic ON user_performance(user_id, project_id, topic);
CREATE INDEX IF NOT EXISTS idx_user_performance_last_attempt ON user_performance(last_attempt DESC);

-- =====================================================
-- 14. REVIEW CARDS (Spaced Repetition)
-- =====================================================
CREATE TABLE IF NOT EXISTS review_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

-- =====================================================
-- 15. MCQ TESTS
-- =====================================================
CREATE TABLE IF NOT EXISTS mcq_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_name VARCHAR(500),
    questions TEXT NOT NULL,  -- JSON stored as TEXT (parsed with json.loads in code)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcq_tests_project_id ON mcq_tests(project_id);

-- =====================================================
-- 16. SUBJECTIVE TESTS
-- =====================================================
CREATE TABLE IF NOT EXISTS subjective_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500),
    questions TEXT NOT NULL,  -- JSON stored as TEXT
    results TEXT,             -- JSON stored as TEXT (set after evaluation)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subjective_tests_project_id ON subjective_tests(project_id);

-- =====================================================
-- 17. ANSWER EVALUATIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS answer_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    user_answer TEXT NOT NULL,
    ai_feedback TEXT NOT NULL,  -- JSON stored as TEXT
    score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_answer_evaluations_user_id ON answer_evaluations(user_id);
CREATE INDEX IF NOT EXISTS idx_answer_evaluations_project_id ON answer_evaluations(project_id);

-- =====================================================
-- 18. TOPIC RELATIONS (Knowledge Graph)
-- =====================================================
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

-- =====================================================
-- 19. TOPIC SUMMARIES
-- =====================================================
CREATE TABLE IF NOT EXISTS topic_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    topic VARCHAR(500) NOT NULL,
    summary TEXT,
    sources JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One summary per project per topic (upsert target)
    CONSTRAINT topic_summaries_project_topic_unique UNIQUE (project_id, topic)
);

CREATE INDEX IF NOT EXISTS idx_topic_summaries_project_id ON topic_summaries(project_id);
CREATE INDEX IF NOT EXISTS idx_topic_summaries_lookup ON topic_summaries(project_id, topic);

-- =====================================================
-- 20. GRAPH ANALYTICS
-- =====================================================
CREATE TABLE IF NOT EXISTS graph_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
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

-- =====================================================
-- 21. LEARNING SESSIONS
-- =====================================================
CREATE TABLE IF NOT EXISTS learning_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    topics_visited JSONB DEFAULT '[]'::jsonb,
    total_time_ms INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_learning_sessions_user_id ON learning_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_project_id ON learning_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_lookup ON learning_sessions(project_id, user_id);
CREATE INDEX IF NOT EXISTS idx_learning_sessions_started_at ON learning_sessions(started_at DESC);

-- =====================================================
-- 22. USER GAMIFICATION
-- =====================================================
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

-- =====================================================
-- ADD MISSING FOREIGN KEYS TO EXISTING TABLES
-- (safe: only adds if constraint doesn't exist)
-- =====================================================

-- flashcard_sets.project_id → projects.id
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

-- mindmaps.project_id → projects.id
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


-- =====================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================
-- Enable RLS on all new tables

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE pomodoro_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE recent_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_streaks ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcq_tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjective_tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_gamification ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────
-- Helper: create a standard set of RLS policies for
-- tables with a user_id column referencing auth.uid()
-- ─────────────────────────────────────────────────────

-- PROJECTS
DROP POLICY IF EXISTS "projects_select_own" ON projects;
CREATE POLICY "projects_select_own" ON projects FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "projects_insert_own" ON projects;
CREATE POLICY "projects_insert_own" ON projects FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "projects_update_own" ON projects;
CREATE POLICY "projects_update_own" ON projects FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "projects_delete_own" ON projects;
CREATE POLICY "projects_delete_own" ON projects FOR DELETE USING (auth.uid() = user_id);

-- DOCUMENTS (access via project ownership)
DROP POLICY IF EXISTS "documents_select_own" ON documents;
CREATE POLICY "documents_select_own" ON documents FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = documents.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "documents_insert_own" ON documents;
CREATE POLICY "documents_insert_own" ON documents FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = documents.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "documents_update_own" ON documents;
CREATE POLICY "documents_update_own" ON documents FOR UPDATE
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = documents.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "documents_delete_own" ON documents;
CREATE POLICY "documents_delete_own" ON documents FOR DELETE
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = documents.project_id AND projects.user_id = auth.uid()));

-- CHAT MESSAGES (access via project ownership)
DROP POLICY IF EXISTS "chat_messages_select_own" ON chat_messages;
CREATE POLICY "chat_messages_select_own" ON chat_messages FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = chat_messages.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "chat_messages_insert_own" ON chat_messages;
CREATE POLICY "chat_messages_insert_own" ON chat_messages FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = chat_messages.project_id AND projects.user_id = auth.uid()));

-- NOTES
DROP POLICY IF EXISTS "notes_select_own" ON notes;
CREATE POLICY "notes_select_own" ON notes FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "notes_insert_own" ON notes;
CREATE POLICY "notes_insert_own" ON notes FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "notes_update_own" ON notes;
CREATE POLICY "notes_update_own" ON notes FOR UPDATE USING (auth.uid() = user_id);

-- USER SETTINGS
DROP POLICY IF EXISTS "user_settings_select_own" ON user_settings;
CREATE POLICY "user_settings_select_own" ON user_settings FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "user_settings_insert_own" ON user_settings;
CREATE POLICY "user_settings_insert_own" ON user_settings FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "user_settings_update_own" ON user_settings;
CREATE POLICY "user_settings_update_own" ON user_settings FOR UPDATE USING (auth.uid() = user_id);

-- BOOKMARKS
DROP POLICY IF EXISTS "bookmarks_select_own" ON bookmarks;
CREATE POLICY "bookmarks_select_own" ON bookmarks FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "bookmarks_insert_own" ON bookmarks;
CREATE POLICY "bookmarks_insert_own" ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "bookmarks_update_own" ON bookmarks;
CREATE POLICY "bookmarks_update_own" ON bookmarks FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "bookmarks_delete_own" ON bookmarks;
CREATE POLICY "bookmarks_delete_own" ON bookmarks FOR DELETE USING (auth.uid() = user_id);

-- STUDY ACTIVITY
DROP POLICY IF EXISTS "study_activity_select_own" ON study_activity;
CREATE POLICY "study_activity_select_own" ON study_activity FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "study_activity_insert_own" ON study_activity;
CREATE POLICY "study_activity_insert_own" ON study_activity FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "study_activity_update_own" ON study_activity;
CREATE POLICY "study_activity_update_own" ON study_activity FOR UPDATE USING (auth.uid() = user_id);

-- EXAM SCHEDULES
DROP POLICY IF EXISTS "exam_schedules_select_own" ON exam_schedules;
CREATE POLICY "exam_schedules_select_own" ON exam_schedules FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "exam_schedules_insert_own" ON exam_schedules;
CREATE POLICY "exam_schedules_insert_own" ON exam_schedules FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "exam_schedules_delete_own" ON exam_schedules;
CREATE POLICY "exam_schedules_delete_own" ON exam_schedules FOR DELETE USING (auth.uid() = user_id);

-- LEARNING PROGRESS
DROP POLICY IF EXISTS "learning_progress_select_own" ON learning_progress;
CREATE POLICY "learning_progress_select_own" ON learning_progress FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "learning_progress_insert_own" ON learning_progress;
CREATE POLICY "learning_progress_insert_own" ON learning_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "learning_progress_update_own" ON learning_progress;
CREATE POLICY "learning_progress_update_own" ON learning_progress FOR UPDATE USING (auth.uid() = user_id);

-- POMODORO SESSIONS
DROP POLICY IF EXISTS "pomodoro_sessions_select_own" ON pomodoro_sessions;
CREATE POLICY "pomodoro_sessions_select_own" ON pomodoro_sessions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "pomodoro_sessions_insert_own" ON pomodoro_sessions;
CREATE POLICY "pomodoro_sessions_insert_own" ON pomodoro_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "pomodoro_sessions_update_own" ON pomodoro_sessions;
CREATE POLICY "pomodoro_sessions_update_own" ON pomodoro_sessions FOR UPDATE USING (auth.uid() = user_id);

-- RECENT SEARCHES
DROP POLICY IF EXISTS "recent_searches_select_own" ON recent_searches;
CREATE POLICY "recent_searches_select_own" ON recent_searches FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "recent_searches_insert_own" ON recent_searches;
CREATE POLICY "recent_searches_insert_own" ON recent_searches FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "recent_searches_delete_own" ON recent_searches;
CREATE POLICY "recent_searches_delete_own" ON recent_searches FOR DELETE USING (auth.uid() = user_id);

-- STUDY STREAKS
DROP POLICY IF EXISTS "study_streaks_select_own" ON study_streaks;
CREATE POLICY "study_streaks_select_own" ON study_streaks FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "study_streaks_insert_own" ON study_streaks;
CREATE POLICY "study_streaks_insert_own" ON study_streaks FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "study_streaks_update_own" ON study_streaks;
CREATE POLICY "study_streaks_update_own" ON study_streaks FOR UPDATE USING (auth.uid() = user_id);

-- USER PERFORMANCE
DROP POLICY IF EXISTS "user_performance_select_own" ON user_performance;
CREATE POLICY "user_performance_select_own" ON user_performance FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "user_performance_insert_own" ON user_performance;
CREATE POLICY "user_performance_insert_own" ON user_performance FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "user_performance_update_own" ON user_performance;
CREATE POLICY "user_performance_update_own" ON user_performance FOR UPDATE USING (auth.uid() = user_id);

-- REVIEW CARDS
DROP POLICY IF EXISTS "review_cards_select_own" ON review_cards;
CREATE POLICY "review_cards_select_own" ON review_cards FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "review_cards_insert_own" ON review_cards;
CREATE POLICY "review_cards_insert_own" ON review_cards FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "review_cards_update_own" ON review_cards;
CREATE POLICY "review_cards_update_own" ON review_cards FOR UPDATE USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "review_cards_delete_own" ON review_cards;
CREATE POLICY "review_cards_delete_own" ON review_cards FOR DELETE USING (auth.uid() = user_id);

-- MCQ TESTS (access via project ownership)
DROP POLICY IF EXISTS "mcq_tests_select_own" ON mcq_tests;
CREATE POLICY "mcq_tests_select_own" ON mcq_tests FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = mcq_tests.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "mcq_tests_insert_own" ON mcq_tests;
CREATE POLICY "mcq_tests_insert_own" ON mcq_tests FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = mcq_tests.project_id AND projects.user_id = auth.uid()));

-- SUBJECTIVE TESTS (access via project ownership)
DROP POLICY IF EXISTS "subjective_tests_select_own" ON subjective_tests;
CREATE POLICY "subjective_tests_select_own" ON subjective_tests FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = subjective_tests.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "subjective_tests_insert_own" ON subjective_tests;
CREATE POLICY "subjective_tests_insert_own" ON subjective_tests FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = subjective_tests.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "subjective_tests_update_own" ON subjective_tests;
CREATE POLICY "subjective_tests_update_own" ON subjective_tests FOR UPDATE
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = subjective_tests.project_id AND projects.user_id = auth.uid()));

-- ANSWER EVALUATIONS
DROP POLICY IF EXISTS "answer_evaluations_select_own" ON answer_evaluations;
CREATE POLICY "answer_evaluations_select_own" ON answer_evaluations FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "answer_evaluations_insert_own" ON answer_evaluations;
CREATE POLICY "answer_evaluations_insert_own" ON answer_evaluations FOR INSERT WITH CHECK (auth.uid() = user_id);

-- TOPIC RELATIONS (access via project ownership)
DROP POLICY IF EXISTS "topic_relations_select_own" ON topic_relations;
CREATE POLICY "topic_relations_select_own" ON topic_relations FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_relations.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "topic_relations_insert_own" ON topic_relations;
CREATE POLICY "topic_relations_insert_own" ON topic_relations FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_relations.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "topic_relations_delete_own" ON topic_relations;
CREATE POLICY "topic_relations_delete_own" ON topic_relations FOR DELETE
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_relations.project_id AND projects.user_id = auth.uid()));

-- TOPIC SUMMARIES (access via project ownership)
DROP POLICY IF EXISTS "topic_summaries_select_own" ON topic_summaries;
CREATE POLICY "topic_summaries_select_own" ON topic_summaries FOR SELECT
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_summaries.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "topic_summaries_insert_own" ON topic_summaries;
CREATE POLICY "topic_summaries_insert_own" ON topic_summaries FOR INSERT
    WITH CHECK (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_summaries.project_id AND projects.user_id = auth.uid()));
DROP POLICY IF EXISTS "topic_summaries_update_own" ON topic_summaries;
CREATE POLICY "topic_summaries_update_own" ON topic_summaries FOR UPDATE
    USING (EXISTS (SELECT 1 FROM projects WHERE projects.id = topic_summaries.project_id AND projects.user_id = auth.uid()));

-- GRAPH ANALYTICS
DROP POLICY IF EXISTS "graph_analytics_select_own" ON graph_analytics;
CREATE POLICY "graph_analytics_select_own" ON graph_analytics FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "graph_analytics_insert_own" ON graph_analytics;
CREATE POLICY "graph_analytics_insert_own" ON graph_analytics FOR INSERT WITH CHECK (auth.uid() = user_id);

-- LEARNING SESSIONS
DROP POLICY IF EXISTS "learning_sessions_select_own" ON learning_sessions;
CREATE POLICY "learning_sessions_select_own" ON learning_sessions FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "learning_sessions_insert_own" ON learning_sessions;
CREATE POLICY "learning_sessions_insert_own" ON learning_sessions FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "learning_sessions_update_own" ON learning_sessions;
CREATE POLICY "learning_sessions_update_own" ON learning_sessions FOR UPDATE USING (auth.uid() = user_id);

-- USER GAMIFICATION (user_id is TEXT, not UUID — matches code)
-- Note: RLS with auth.uid() requires casting since user_id is TEXT
DROP POLICY IF EXISTS "user_gamification_select_own" ON user_gamification;
CREATE POLICY "user_gamification_select_own" ON user_gamification FOR SELECT USING (auth.uid()::text = user_id);
DROP POLICY IF EXISTS "user_gamification_insert_own" ON user_gamification;
CREATE POLICY "user_gamification_insert_own" ON user_gamification FOR INSERT WITH CHECK (auth.uid()::text = user_id);
DROP POLICY IF EXISTS "user_gamification_update_own" ON user_gamification;
CREATE POLICY "user_gamification_update_own" ON user_gamification FOR UPDATE USING (auth.uid()::text = user_id);


-- =====================================================
-- SERVICE ROLE BYPASS POLICY
-- =====================================================
-- The backend uses service_role key which bypasses RLS by default.
-- The RLS policies above protect against direct client-side access
-- via Supabase JS client (anon key).
-- No additional service-role policies are needed.


-- =====================================================
-- UPDATED_AT TRIGGERS
-- Reuse the function from flashcards_mindmaps schema
-- =====================================================
-- The function update_updated_at_column() is already created
-- in supabase_schema_flashcards_mindmaps.sql. If running this
-- script standalone, uncomment the block below:
--
-- CREATE OR REPLACE FUNCTION update_updated_at_column()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     NEW.updated_at = NOW();
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- Apply updated_at triggers to tables that have updated_at columns
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
        -- Drop existing trigger if any, then create
        EXECUTE format('DROP TRIGGER IF EXISTS update_%s_updated_at ON %I', tbl, tbl);
        EXECUTE format(
            'CREATE TRIGGER update_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
            tbl, tbl
        );
    END LOOP;
END $$;


-- =====================================================
-- NOTES
-- =====================================================
-- 1. Run supabase_schema_flashcards_mindmaps.sql FIRST (it creates
--    the update_updated_at_column function and the flashcard/mindmap tables).
-- 2. Then run this file to create all remaining tables.
-- 3. Both scripts are idempotent (safe to re-run).
--
-- IMPORTANT: The backend uses service_role key, which bypasses RLS.
-- RLS policies above protect against direct anon-key access only.
--
-- Tables with no user_id column (mcq_tests, subjective_tests,
-- topic_relations, topic_summaries, chat_messages, documents)
-- use project-ownership checks via a subquery on the projects table.
