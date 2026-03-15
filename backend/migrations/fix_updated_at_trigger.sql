-- Migration: Fix the updated_at trigger error on the documents table
-- Error: record "new" has no field "updated_at"
-- 
-- Root cause: The trigger function update_updated_at_column() fires BEFORE UPDATE
-- on the documents table and tries to set NEW.updated_at = NOW(), but the 
-- updated_at column doesn't exist in the live documents table.
--
-- Run this SQL in your Supabase SQL Editor to fix the issue.

-- Option 1 (RECOMMENDED): Add the missing updated_at column to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Recreate the trigger function to be defensive (won't crash if column missing)
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

-- Ensure the trigger exists on documents table
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
