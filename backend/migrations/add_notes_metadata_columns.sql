-- Migration: Add title, note_type, topic columns to notes table
-- These columns are needed to support listing saved notes with metadata

ALTER TABLE notes ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE notes ADD COLUMN IF NOT EXISTS note_type TEXT;
ALTER TABLE notes ADD COLUMN IF NOT EXISTS topic TEXT;

-- Drop unique constraint on (project_id, user_id) if it exists
-- because we now store multiple notes per project per user
ALTER TABLE notes DROP CONSTRAINT IF EXISTS notes_project_id_user_id_key;
