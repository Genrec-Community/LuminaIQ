-- Chapter-grouped topic outline per document (see services/topic_outline_service.py).
-- documents.topics stays the flat list every feature uses; topic_outline adds
-- the chapter structure: [{"title": "...", "topics": [{"name": "...", "summary": "..."}]}]
-- The backend works without this column (it just skips chapters) until it is added.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS topic_outline JSONB DEFAULT '[]'::jsonb;

-- Speeds up per-project document lookups ordered by upload time
CREATE INDEX IF NOT EXISTS idx_documents_project_status_created
    ON documents (project_id, upload_status, created_at);

-- Speeds up prerequisite-edge lookups used for every learning-path / topics call
CREATE INDEX IF NOT EXISTS idx_topic_relations_project_type
    ON topic_relations (project_id, relation_type);
