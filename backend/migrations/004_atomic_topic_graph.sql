begin;

create or replace function public.replace_topic_graph_relationships(
    p_project_id uuid,
    p_edges jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer;
begin
    if jsonb_typeof(coalesce(p_edges, '[]'::jsonb)) <> 'array' then
        raise exception 'p_edges must be a JSON array';
    end if;

    delete from public.topic_relations
    where project_id = p_project_id;

    insert into public.topic_relations (
        id,
        project_id,
        from_topic,
        to_topic,
        relation_type,
        weight
    )
    select
        coalesce(nullif(edge->>'id', '')::uuid, gen_random_uuid()),
        p_project_id,
        edge->>'from_topic',
        edge->>'to_topic',
        edge->>'relation_type',
        (edge->>'weight')::double precision
    from jsonb_array_elements(coalesce(p_edges, '[]'::jsonb)) as edge;

    get diagnostics v_count = row_count;
    return v_count;
end;
$$;

revoke all on function public.replace_topic_graph_relationships(uuid, jsonb)
from public, anon, authenticated;

grant execute on function public.replace_topic_graph_relationships(uuid, jsonb)
to service_role;

commit;
