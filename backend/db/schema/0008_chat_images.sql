-- Photo questions (AGENTS.md Phase 6): the stored photo behind a chat message, for its thumbnail.
ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS image_path TEXT;
