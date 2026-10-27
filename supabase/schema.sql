-- Einmal im Supabase-Dashboard ausführen: SQL Editor → New query → einfügen → Run.
-- Speicher der App: ein Dokument (JSON) je Sammlung und ID, wie im Artifact (activities, settings, strength, daylogs, …).

create table if not exists public.docs (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  col        text        not null check (col ~ '^[A-Za-z0-9_.:@+-]{1,200}$'),
  id         text        not null check (id  ~ '^[A-Za-z0-9_.:@+-]{1,200}$'),
  doc        jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, col, id)
);

-- Zeilenschutz: jede angemeldete Person sieht und ändert nur ihre eigenen Dokumente
alter table public.docs enable row level security;

drop policy if exists "docs_select_own" on public.docs;
drop policy if exists "docs_insert_own" on public.docs;
drop policy if exists "docs_update_own" on public.docs;
drop policy if exists "docs_delete_own" on public.docs;
create policy "docs_select_own" on public.docs for select to authenticated using (user_id = (select auth.uid()));
create policy "docs_insert_own" on public.docs for insert to authenticated with check (user_id = (select auth.uid()));
create policy "docs_update_own" on public.docs for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy "docs_delete_own" on public.docs for delete to authenticated using (user_id = (select auth.uid()));

revoke all on public.docs from anon;
grant select, insert, update, delete on public.docs to authenticated;

-- updated_at bei jeder Änderung setzen (Uhr des Servers, nicht des Handys)
create or replace function public.docs_touch() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists docs_touch on public.docs;
create trigger docs_touch before insert or update on public.docs
  for each row execute function public.docs_touch();

-- Kurzer Stand-Check für den Abgleich: ändert sich bei jedem Schreiben und Löschen
create or replace function public.docs_version() returns text
language sql stable security invoker set search_path = '' as $$
  select count(*)::text || '-' || coalesce(extract(epoch from max(updated_at))::text, '0')
  from public.docs where user_id = (select auth.uid());
$$;

revoke all on function public.docs_version() from public, anon;
grant execute on function public.docs_version() to authenticated;
