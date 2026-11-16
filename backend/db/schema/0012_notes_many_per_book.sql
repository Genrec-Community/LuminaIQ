-- Students keep many generated notes per book (the "Saved notes" list), but 0001 still had a
-- one-note-per-book constraint left from the old single notepad, so every note after the first
-- failed to save. 0001 dropped the constraint under another name; this drops the real one.
ALTER TABLE notes DROP CONSTRAINT IF EXISTS notes_user_project_unique;
CREATE INDEX IF NOT EXISTS idx_notes_project_user_created ON notes(project_id, user_id, created_at DESC);
