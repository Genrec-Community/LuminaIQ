-- Word uploads store their MIME type, which is 71 characters
-- (application/vnd.openxmlformats-officedocument.wordprocessingml.document), so the
-- VARCHAR(50) from 0001 rejected every .docx upload (and the live ones being copied in).
ALTER TABLE documents ALTER COLUMN file_type TYPE TEXT;
