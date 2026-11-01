-- Several chats per book, like ChatGPT's "New chat": each message belongs to a thread,
-- and the rolling summary (Phase 5) is kept per thread.

CREATE TABLE IF NOT EXISTS chat_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL,
    title       TEXT NOT NULL DEFAULT 'New chat',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_threads_project ON chat_threads (project_id, updated_at DESC);

ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS thread_id UUID REFERENCES chat_threads(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages (thread_id, created_at);

-- Messages written before threads existed become one chat per book
INSERT INTO chat_threads (project_id, user_id, title, created_at, updated_at)
SELECT p.id, p.user_id, 'Earlier chat', min(m.created_at), max(m.created_at)
FROM chat_messages m JOIN projects p ON p.id = m.project_id
WHERE m.thread_id IS NULL
GROUP BY p.id, p.user_id;

UPDATE chat_messages m SET thread_id = t.id
FROM chat_threads t
WHERE m.thread_id IS NULL AND t.project_id = m.project_id AND t.title = 'Earlier chat';

-- Summaries move from one-per-book to one-per-thread
ALTER TABLE chat_summaries ADD COLUMN IF NOT EXISTS thread_id UUID REFERENCES chat_threads(id) ON DELETE CASCADE;
UPDATE chat_summaries s SET thread_id = t.id
FROM chat_threads t WHERE s.thread_id IS NULL AND t.project_id = s.project_id AND t.title = 'Earlier chat';
DELETE FROM chat_summaries WHERE thread_id IS NULL;
ALTER TABLE chat_summaries DROP CONSTRAINT IF EXISTS chat_summaries_pkey;
ALTER TABLE chat_summaries ALTER COLUMN thread_id SET NOT NULL;
ALTER TABLE chat_summaries ADD PRIMARY KEY (thread_id);
CREATE INDEX IF NOT EXISTS idx_chat_summaries_project ON chat_summaries (project_id);
