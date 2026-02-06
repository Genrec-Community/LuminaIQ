-- Document Chunks Table
-- Run this SQL in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_document_chunk UNIQUE (document_id, chunk_index)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_project_id ON document_chunks(project_id);

-- Enable RLS (optional, based on your security requirements)
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- Policy to allow service role full access
CREATE POLICY "Service role has full access to document_chunks"
    ON document_chunks
    FOR ALL
    USING (true)
    WITH CHECK (true);
