begin;

create table if not exists public.topic_graph_publications (
    project_id uuid primary key references public.projects(id) on delete cascade,
    build_started_at timestamptz not null,
    published_at timestamptz not null default now()
);

alter table public.topic_graph_publications enable row level security;
revoke all on table public.topic_graph_publications from public, anon, authenticated;
grant select, insert, update, delete on table public.topic_graph_publications to service_role;

drop function if exists public.replace_topic_graph_relationships(uuid, jsonb);

create function public.replace_topic_graph_relationships(
    p_project_id uuid,
    p_edges jsonb,
    p_build_started_at timestamptz
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

    perform pg_advisory_xact_lock(hashtextextended(p_project_id::text, 0));

    if exists (
        select 1
        from public.topic_graph_publications
        where project_id = p_project_id
          and build_started_at > p_build_started_at
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

    insert into public.topic_graph_publications (
        project_id, build_started_at, published_at
    ) values (
        p_project_id, p_build_started_at, clock_timestamp()
    )
    on conflict (project_id) do update
    set build_started_at = excluded.build_started_at,
        published_at = excluded.published_at;

    return true;
end;
$$;

revoke all on function public.replace_topic_graph_relationships(
    uuid, jsonb, timestamptz
) from public, anon, authenticated;
grant execute on function public.replace_topic_graph_relationships(
    uuid, jsonb, timestamptz
) to service_role;

commit;
