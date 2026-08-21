begin;

create table if not exists public.document_jobs (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references public.projects(id) on delete cascade,
    document_id uuid not null references public.documents(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    status text not null default 'queued'
        check (status in ('queued', 'processing', 'completed', 'failed')),
    stage text not null default 'queued',
    progress integer not null default 0 check (progress between 0 and 100),
    attempts integer not null default 0 check (attempts >= 0),
    max_attempts integer not null default 3 check (max_attempts > 0),
    available_at timestamptz not null default now(),
    worker_id text,
    lease_token uuid,
    lease_expires_at timestamptz,
    error_code text,
    error_message text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz not null default now(),
    constraint document_jobs_lease_consistency check (
        (status = 'processing' and worker_id is not null and lease_token is not null
            and lease_expires_at is not null)
        or
        (status <> 'processing' and worker_id is null and lease_token is null
            and lease_expires_at is null)
    )
);

create unique index if not exists idx_document_jobs_one_active_document
    on public.document_jobs (document_id)
    where status in ('queued', 'processing');

create index if not exists idx_document_jobs_claim
    on public.document_jobs (available_at, created_at)
    where status = 'queued';

create index if not exists idx_document_jobs_expired_leases
    on public.document_jobs (lease_expires_at)
    where status = 'processing';

create index if not exists idx_document_jobs_user_created
    on public.document_jobs (user_id, created_at desc);

create index if not exists idx_document_jobs_project
    on public.document_jobs (project_id, created_at desc);

create or replace function public.validate_document_job_ownership()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if not exists (
        select 1
        from public.projects p
        join public.documents d on d.project_id = p.id
        where p.id = new.project_id
          and d.id = new.document_id
          and p.user_id = new.user_id
    ) then
        raise exception 'document job project, document, and user do not match'
            using errcode = '23503';
    end if;
    return new;
end;
$$;

drop trigger if exists validate_document_job_ownership on public.document_jobs;
create trigger validate_document_job_ownership
before insert or update of project_id, document_id, user_id
on public.document_jobs
for each row execute function public.validate_document_job_ownership();

alter table public.document_jobs enable row level security;

drop policy if exists document_jobs_select_own on public.document_jobs;
create policy document_jobs_select_own
on public.document_jobs
for select
to authenticated
using (auth.uid() = user_id);

revoke all on table public.document_jobs from public, anon, authenticated;
grant select on table public.document_jobs to authenticated;
grant select, insert, update, delete on table public.document_jobs to service_role;

create or replace function public.claim_document_job(
    p_worker_id text,
    p_lease_seconds integer default 300
)
returns setof public.document_jobs
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_job_id uuid;
begin
    if nullif(btrim(p_worker_id), '') is null then
        raise exception 'p_worker_id must not be empty';
    end if;
    if p_lease_seconds < 1 or p_lease_seconds > 86400 then
        raise exception 'p_lease_seconds must be between 1 and 86400';
    end if;

    -- A crashed final attempt cannot be reclaimed, so close it before looking
    -- for the next available job rather than leaving it processing forever.
    update public.document_jobs
    set status = 'failed',
        stage = 'failed',
        worker_id = null,
        lease_token = null,
        lease_expires_at = null,
        error_code = 'lease_expired',
        error_message = 'The final processing lease expired before completion.',
        completed_at = clock_timestamp(),
        updated_at = clock_timestamp()
    where status = 'processing'
      and lease_expires_at < clock_timestamp()
      and attempts >= max_attempts;

    select j.id into v_job_id
    from public.document_jobs j
    where j.attempts < j.max_attempts
      and (
          (j.status = 'queued' and j.available_at <= clock_timestamp())
          or
          (j.status = 'processing' and j.lease_expires_at < clock_timestamp())
      )
    order by j.available_at, j.created_at
    for update skip locked
    limit 1;

    if v_job_id is null then
        return;
    end if;

    return query
    update public.document_jobs
    set status = 'processing',
        stage = 'claimed',
        attempts = attempts + 1,
        worker_id = btrim(p_worker_id),
        lease_token = gen_random_uuid(),
        lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
        started_at = coalesce(started_at, clock_timestamp()),
        completed_at = null,
        error_code = null,
        error_message = null,
        updated_at = clock_timestamp()
    where id = v_job_id
    returning *;
end;
$$;

create or replace function public.heartbeat_document_job(
    p_job_id uuid,
    p_lease_token uuid,
    p_lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if p_lease_seconds < 1 or p_lease_seconds > 86400 then
        raise exception 'p_lease_seconds must be between 1 and 86400';
    end if;

    update public.document_jobs
    set lease_expires_at = clock_timestamp() + make_interval(secs => p_lease_seconds),
        updated_at = clock_timestamp()
    where id = p_job_id
      and status = 'processing'
      and lease_token = p_lease_token
      and lease_expires_at >= clock_timestamp();
    return found;
end;
$$;

create or replace function public.update_document_job_progress(
    p_job_id uuid,
    p_lease_token uuid,
    p_stage text,
    p_progress integer
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if nullif(btrim(p_stage), '') is null then
        raise exception 'p_stage must not be empty';
    end if;
    if p_progress < 0 or p_progress > 99 then
        raise exception 'p_progress must be between 0 and 99';
    end if;

    update public.document_jobs
    set stage = btrim(p_stage),
        progress = p_progress,
        updated_at = clock_timestamp()
    where id = p_job_id
      and status = 'processing'
      and lease_token = p_lease_token
      and lease_expires_at >= clock_timestamp()
      and p_progress >= progress;
    return found;
end;
$$;

create or replace function public.complete_document_job(
    p_job_id uuid,
    p_lease_token uuid
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    update public.document_jobs
    set status = 'completed',
        stage = 'completed',
        progress = 100,
        worker_id = null,
        lease_token = null,
        lease_expires_at = null,
        error_code = null,
        error_message = null,
        completed_at = clock_timestamp(),
        updated_at = clock_timestamp()
    where id = p_job_id
      and status = 'processing'
      and lease_token = p_lease_token
      and lease_expires_at >= clock_timestamp();
    return found;
end;
$$;

create or replace function public.fail_document_job(
    p_job_id uuid,
    p_lease_token uuid,
    p_error_code text,
    p_error_message text,
    p_retryable boolean default true,
    p_retry_delay_seconds integer default 30
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if nullif(btrim(p_error_code), '') is null then
        raise exception 'p_error_code must not be empty';
    end if;
    if p_retry_delay_seconds < 0 or p_retry_delay_seconds > 86400 then
        raise exception 'p_retry_delay_seconds must be between 0 and 86400';
    end if;

    update public.document_jobs
    set status = case when p_retryable and attempts < max_attempts
                      then 'queued' else 'failed' end,
        stage = case when p_retryable and attempts < max_attempts
                     then 'retry_scheduled' else 'failed' end,
        available_at = case when p_retryable and attempts < max_attempts
                            then clock_timestamp() + make_interval(secs => p_retry_delay_seconds)
                            else available_at end,
        worker_id = null,
        lease_token = null,
        lease_expires_at = null,
        error_code = btrim(p_error_code),
        error_message = left(coalesce(p_error_message, ''), 8000),
        completed_at = case when p_retryable and attempts < max_attempts
                            then null else clock_timestamp() end,
        updated_at = clock_timestamp()
    where id = p_job_id
      and status = 'processing'
      and lease_token = p_lease_token
      and lease_expires_at >= clock_timestamp();
    return found;
end;
$$;

revoke all on function public.validate_document_job_ownership() from public, anon, authenticated;
revoke all on function public.claim_document_job(text, integer) from public, anon, authenticated;
revoke all on function public.heartbeat_document_job(uuid, uuid, integer) from public, anon, authenticated;
revoke all on function public.update_document_job_progress(uuid, uuid, text, integer) from public, anon, authenticated;
revoke all on function public.complete_document_job(uuid, uuid) from public, anon, authenticated;
revoke all on function public.fail_document_job(uuid, uuid, text, text, boolean, integer) from public, anon, authenticated;

grant execute on function public.claim_document_job(text, integer) to service_role;
grant execute on function public.heartbeat_document_job(uuid, uuid, integer) to service_role;
grant execute on function public.update_document_job_progress(uuid, uuid, text, integer) to service_role;
grant execute on function public.complete_document_job(uuid, uuid) to service_role;
grant execute on function public.fail_document_job(uuid, uuid, text, text, boolean, integer) to service_role;

commit;
