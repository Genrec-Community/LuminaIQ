-- Migration 006: Add new activity type columns to study_activity
-- Adds tracking for exam prep, learning path, and knowledge graph exploration

ALTER TABLE study_activity ADD COLUMN IF NOT EXISTS exam INT DEFAULT 0;
ALTER TABLE study_activity ADD COLUMN IF NOT EXISTS path INT DEFAULT 0;
ALTER TABLE study_activity ADD COLUMN IF NOT EXISTS knowledge_graph INT DEFAULT 0;
