-- Supabase Storage hardening (run once in the Supabase SQL editor; not applied by db/migrate.py).
--
-- 1. The "documents" bucket (original PDFs) was public: anyone with a file's address could
--    download it. The app only ever reads it with the service key and hands the reader
--    short-lived signed links (api/v1/endpoints/documents.py), so it can be private.
-- 2. Any signed-in user could read, upload or delete ANY file in the "texts" bucket (extracted
--    book text): the policies only checked the bucket name. Only the backend (service key,
--    which bypasses these policies) uses that bucket, so the policies are removed.
--
-- Undo: UPDATE storage.buckets SET public = true WHERE id = 'documents'; and re-create the policies.

BEGIN;
UPDATE storage.buckets SET public = false WHERE id = 'documents';
DROP POLICY IF EXISTS texts_user_read ON storage.objects;
DROP POLICY IF EXISTS texts_user_delete ON storage.objects;
DROP POLICY IF EXISTS texts_user_upload ON storage.objects;
COMMIT;
