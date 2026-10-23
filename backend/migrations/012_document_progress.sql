-- Latest processing progress per document, so any backend instance can report
-- it (the live stream is in one process's memory; with several instances the
-- app may be connected to a different one). Additive: safe for production.
alter table public.documents add column if not exists progress jsonb;
