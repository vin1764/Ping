-- Reviewer login: a second dashboard login that only ever sees the anonymised
-- demo rows (is_sample = true) and can't change anything. Your own login only
-- ever sees your real rows. Safe to re-run. (Also part of schema.sql.)

create table if not exists reviewer_users (
  email text primary key,
  created_at timestamptz default now()
);
alter table reviewer_users enable row level security;

create or replace function is_ping_reviewer() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from reviewer_users where lower(email) = lower(auth.jwt() ->> 'email'));
$$;
grant execute on function is_ping_reviewer() to authenticated;
grant select, insert, update, delete on reviewer_users to service_role;

-- the demo profile lives in row 2, yours in row 1
alter table profile drop constraint if exists profile_id_check;
alter table profile add constraint profile_id_check check (id in (1, 2));

-- owner: real rows only; reviewer: demo rows only (and only reading)
do $$
declare t text;
begin
  foreach t in array array['profile','roles','notices','pdf_checks','items','emails','contacts','runs'] loop
    execute format('drop policy if exists owner_read on %I', t);
    execute format('create policy owner_read on %I for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false))', t);
    execute format('drop policy if exists reviewer_read on %I', t);
    execute format('create policy reviewer_read on %I for select to authenticated using (is_ping_reviewer() and coalesce(is_sample, false))', t);
  end loop;
end $$;

drop policy if exists owner_edit_profile on profile;
create policy owner_edit_profile on profile for update to authenticated
  using (is_ping_owner() and id = 1) with check (is_ping_owner() and id = 1);
drop policy if exists owner_mark_items on items;
create policy owner_mark_items on items for update to authenticated
  using (is_ping_owner() and not coalesce(is_sample, false)) with check (is_ping_owner() and not coalesce(is_sample, false));
drop policy if exists owner_chat_read on chat_messages;
create policy owner_chat_read on chat_messages for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false));
