-- Resumable browser uploads: the app uploads books straight to this private
-- bucket in 6 MB chunks (TUS), then the backend fetches the file by path.
-- Each user may only touch objects under their own "<user id>/" folder.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('uploads', 'uploads', false, 52428800,
        array['application/pdf',
              'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              'text/plain'])
on conflict (id) do update
  set public = excluded.public,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists uploads_own_insert on storage.objects;
drop policy if exists uploads_own_select on storage.objects;
drop policy if exists uploads_own_update on storage.objects;
drop policy if exists uploads_own_delete on storage.objects;

create policy uploads_own_insert on storage.objects for insert to authenticated
  with check (bucket_id = 'uploads' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy uploads_own_select on storage.objects for select to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy uploads_own_update on storage.objects for update to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = (select auth.uid())::text);
create policy uploads_own_delete on storage.objects for delete to authenticated
  using (bucket_id = 'uploads' and (storage.foldername(name))[1] = (select auth.uid())::text);
