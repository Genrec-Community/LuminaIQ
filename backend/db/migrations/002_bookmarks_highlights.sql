-- =============================================
-- Migration 002: Highlight & Quote Collection
-- Adds highlight_text and color columns to the existing bookmarks table
-- =============================================

ALTER TABLE bookmarks
ADD COLUMN IF NOT EXISTS highlight_text TEXT DEFAULT NULL;

ALTER TABLE bookmarks
ADD COLUMN IF NOT EXISTS color TEXT DEFAULT NULL;

-- Add comments for clarity
COMMENT ON COLUMN bookmarks.highlight_text IS 'Stored quote/passage text for highlight-type bookmarks';
COMMENT ON COLUMN bookmarks.color IS 'Highlight color: yellow, green, blue, pink, purple';
