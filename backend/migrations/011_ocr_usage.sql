-- Monthly page counter for paid OCR (Google Vision) so the app stays inside the
-- free tier. reserve_ocr_pages atomically grants up to p_pages without passing p_cap.
create table if not exists ocr_usage (
  provider text not null,
  month text not null,            -- 'YYYY-MM' (UTC)
  pages integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (provider, month)
);
alter table ocr_usage enable row level security;  -- service role only

create or replace function reserve_ocr_pages(p_provider text, p_month text, p_pages integer, p_cap integer)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  used integer;
  granted integer;
begin
  insert into ocr_usage (provider, month, pages) values (p_provider, p_month, 0)
  on conflict (provider, month) do nothing;
  select pages into used from ocr_usage where provider = p_provider and month = p_month for update;
  granted := greatest(0, least(p_pages, p_cap - used));
  if granted > 0 then
    update ocr_usage set pages = pages + granted, updated_at = now()
    where provider = p_provider and month = p_month;
  end if;
  return granted;
end;
$$;
revoke all on function reserve_ocr_pages(text, text, integer, integer) from public, anon, authenticated;
