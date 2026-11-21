-- ---------------------------------------------------------------- one-click demo
-- "View demo" on the sign-in screen signs in anonymously (Supabase Auth, is_anonymous = true in the token).
-- Such a session may READ the anonymised demo rows (is_sample = true) in profile, roles, notices, pdf_checks
-- and items, and INSERT / READ only its own chat messages. Nothing else: no update or delete anywhere, no real
-- rows, no runs, state, contacts, emails, corrections or allowed_users. Your own (owner) rules are unchanged.
-- Also in sql/demo.sql. Safe to re-run.

-- the reviewer login this replaces
do $$
declare t text;
begin
  foreach t in array array['profile','roles','notices','pdf_checks','items','emails','contacts','runs'] loop
    execute format('drop policy if exists reviewer_read on %I', t);
  end loop;
end $$;
drop function if exists is_ping_reviewer();
drop table if exists reviewer_users;

-- the demo profile lives in row 2, yours in row 1
alter table profile drop constraint if exists profile_id_check;
alter table profile add constraint profile_id_check check (id in (1, 2));

create or replace function is_ping_demo() returns boolean
language sql stable as $$
  select coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
$$;
grant execute on function is_ping_demo() to authenticated;

-- owner: real rows only (unchanged); demo: the anonymised demo rows, and only reading them
do $$
declare t text;
begin
  foreach t in array array['profile','roles','notices','pdf_checks','items','emails','contacts','runs'] loop
    execute format('drop policy if exists owner_read on %I', t);
    execute format('create policy owner_read on %I for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false))', t);
    execute format('drop policy if exists demo_read on %I', t);
  end loop;
  foreach t in array array['profile','roles','notices','pdf_checks','items'] loop
    execute format('create policy demo_read on %I for select to authenticated using (is_ping_demo() and coalesce(is_sample, false))', t);
  end loop;
end $$;

drop policy if exists owner_edit_profile on profile;
create policy owner_edit_profile on profile for update to authenticated
  using (is_ping_owner() and id = 1) with check (is_ping_owner() and id = 1);
drop policy if exists owner_mark_items on items;
create policy owner_mark_items on items for update to authenticated
  using (is_ping_owner() and not coalesce(is_sample, false)) with check (is_ping_owner() and not coalesce(is_sample, false));

-- chat: each message belongs to the login that wrote it; demo messages are demo rows (is_sample), so the
-- owner's rules never show them and the demo rules show each session only its own
alter table chat_messages add column if not exists owner_id uuid default auth.uid();
create index if not exists chat_messages_owner_time on chat_messages (owner_id, created_at);
drop policy if exists owner_chat_read on chat_messages;
create policy owner_chat_read on chat_messages for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false));
drop policy if exists demo_chat_read on chat_messages;
create policy demo_chat_read on chat_messages for select to authenticated
  using (is_ping_demo() and owner_id = auth.uid());
drop policy if exists demo_chat_write on chat_messages;
create policy demo_chat_write on chat_messages for insert to authenticated
  with check (is_ping_demo() and owner_id = auth.uid() and is_sample is true);

-- Ask Ping's limits for demo sessions (15 questions per session per hour, 100 per hour for all demo
-- sessions together). Counts only: no question text is stored.
create table if not exists demo_questions (
  id bigint generated always as identity primary key,
  session_id uuid not null,
  asked_at timestamptz not null default now()
);
create index if not exists demo_questions_time on demo_questions (asked_at);
alter table demo_questions enable row level security;   -- no policies: only the functions below touch it
grant select, insert, delete on demo_questions to service_role;

create or replace function demo_take_question() returns jsonb
language plpgsql volatile security definer set search_path = public as $$
declare s int; g int;
begin
  if not is_ping_demo() then
    return jsonb_build_object('ok', true);
  end if;
  select count(*) into s from demo_questions where session_id = auth.uid() and asked_at > now() - interval '1 hour';
  select count(*) into g from demo_questions where asked_at > now() - interval '1 hour';
  if s >= 15 then
    return jsonb_build_object('ok', false, 'why', 'session', 'session', s, 'all', g);
  end if;
  if g >= 100 then
    return jsonb_build_object('ok', false, 'why', 'all', 'session', s, 'all', g);
  end if;
  insert into demo_questions (session_id) values (auth.uid());
  return jsonb_build_object('ok', true, 'session', s + 1, 'all', g + 1);
end $$;
revoke all on function demo_take_question() from public, anon;
grant execute on function demo_take_question() to authenticated;

-- Daily cleanup (Ping workflow): anonymous users older than N days, their chat, old demo counts.
create or replace function cleanup_demo_sessions(days int default 7) returns jsonb
language plpgsql volatile security definer set search_path = public, auth as $$
declare c int; q int; u int;
begin
  delete from public.chat_messages
    where owner_id in (select id from auth.users where is_anonymous and created_at < now() - make_interval(days => days))
       or (is_sample and created_at < now() - make_interval(days => days));
  get diagnostics c = row_count;
  delete from public.demo_questions where asked_at < now() - make_interval(days => days);
  get diagnostics q = row_count;
  delete from auth.users where is_anonymous and created_at < now() - make_interval(days => days);
  get diagnostics u = row_count;
  return jsonb_build_object('anonymous_users', u, 'chat_messages', c, 'demo_question_counts', q);
end $$;
revoke all on function cleanup_demo_sessions(int) from public, anon, authenticated;
grant execute on function cleanup_demo_sessions(int) to service_role;
