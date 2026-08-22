begin;

alter table public.topic_graph_publications
    add column if not exists requested_fingerprint text,
    add column if not exists published_fingerprint text,
    add column if not exists request_id uuid,
    add column if not exists requested_at timestamptz;

alter table public.topic_graph_publications
    drop constraint if exists topic_graph_publications_requested_fingerprint_sha256,
    drop constraint if exists topic_graph_publications_published_fingerprint_sha256;

alter table public.topic_graph_publications
    add constraint topic_graph_publications_requested_fingerprint_sha256
        check (
            requested_fingerprint is null
            or requested_fingerprint ~ '^[0-9a-f]{64}$'
        ),
    add constraint topic_graph_publications_published_fingerprint_sha256
        check (
            published_fingerprint is null
            or published_fingerprint ~ '^[0-9a-f]{64}$'
        );

create or replace function public.request_topic_graph_build(
    p_project_id uuid,
    p_source_fingerprint text,
    p_request_id uuid,
    p_requested_at timestamptz,
    p_force_rebuild boolean default false
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
    v_already_published boolean;
begin
    if p_source_fingerprint !~ '^[0-9a-f]{64}$' then
        raise exception 'p_source_fingerprint must be a lowercase SHA-256 digest';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_project_id::text, 0));

    select published_fingerprint = p_source_fingerprint
    into v_already_published
    from public.topic_graph_publications
    where project_id = p_project_id;

    insert into public.topic_graph_publications (
        project_id,
        build_started_at,
        requested_fingerprint,
        request_id,
        requested_at
    ) values (
        p_project_id,
        p_requested_at,
        p_source_fingerprint,
        p_request_id,
        clock_timestamp()
    )
    on conflict (project_id) do update
    set build_started_at = excluded.build_started_at,
        requested_fingerprint = excluded.requested_fingerprint,
        request_id = excluded.request_id,
        requested_at = excluded.requested_at;

    return p_force_rebuild or not coalesce(v_already_published, false);
end;
$$;

create or replace function public.replace_topic_graph_relationships(
    p_project_id uuid,
    p_edges jsonb,
    p_source_fingerprint text,
    p_request_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
begin
    if jsonb_typeof(coalesce(p_edges, '[]'::jsonb)) <> 'array' then
        raise exception 'p_edges must be a JSON array';
    end if;
    if p_source_fingerprint !~ '^[0-9a-f]{64}$' then
        raise exception 'p_source_fingerprint must be a lowercase SHA-256 digest';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_project_id::text, 0));

    if not exists (
        select 1
        from public.topic_graph_publications
        where project_id = p_project_id
          and request_id = p_request_id
          and requested_fingerprint = p_source_fingerprint
    ) then
        return false;
    end if;

    delete from public.topic_relations where project_id = p_project_id;

    insert into public.topic_relations (
        id, project_id, from_topic, to_topic, relation_type, weight
    )
    select
        coalesce(nullif(edge->>'id', '')::uuid, gen_random_uuid()),
        p_project_id,
        edge->>'from_topic',
        edge->>'to_topic',
        edge->>'relation_type',
        (edge->>'weight')::double precision
    from jsonb_array_elements(coalesce(p_edges, '[]'::jsonb)) as edge;

    update public.topic_graph_publications
    set published_fingerprint = p_source_fingerprint,
        published_at = clock_timestamp()
    where project_id = p_project_id
      and request_id = p_request_id;

    return true;
end;
$$;

revoke all on function public.request_topic_graph_build(
    uuid, text, uuid, timestamptz, boolean
) from public, anon, authenticated;
grant execute on function public.request_topic_graph_build(
    uuid, text, uuid, timestamptz, boolean
) to service_role;

revoke all on function public.replace_topic_graph_relationships(
    uuid, jsonb, text, uuid
) from public, anon, authenticated;
grant execute on function public.replace_topic_graph_relationships(
    uuid, jsonb, text, uuid
) to service_role;

commit;
