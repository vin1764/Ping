-- Ping database. Paste this whole file into Supabase > SQL Editor > New query > Run.
-- Safe to run more than once.
--
-- Row Level Security is ON for every table with NO policies, so nothing is
-- readable with the public (anon/publishable) key. Only Ping's secret key
-- (which bypasses RLS) can read or write. When the dashboard is built it will
-- add policies that let only YOU (logged in) read.

create table if not exists profile (
  id int primary key default 1 check (id = 1),
  roll text,
  name text,                       -- only used as a fallback when searching PDFs
  department text,                 -- e.g. COMPUTER SCIENCE AND ENGINEERING
  degree text,                     -- e.g. B.TECH, DUAL DEGREE, M.SC(5YR)
  cgpa numeric,
  active_backlogs boolean default false,
  cv_names text[] default '{}',
  interested_companies text[] default '{}',
  not_interested_companies text[] default '{}',
  notice_types text[] default '{PLACEMENT}',
  reminder_hours numeric default 2,   -- one reminder this many hours before each deadline batch
  is_sample boolean default false,
  updated_at timestamptz default now()
);
alter table profile add column if not exists reminder_hours numeric default 2;
-- what you're looking for, in your own words, and whether to still list the other roles (Profile page)
alter table profile add column if not exists targets text;
alter table profile add column if not exists list_other_roles boolean default true;
-- your CVs: [{label, path (in the private "cvs" bucket), uploaded_at, summary, summarised_for}] (ping/cvs.py)
alter table profile add column if not exists cvs jsonb default '[]';
-- first-run onboarding in the chat, and the student's own feed and schedule (all changeable later in the chat)
alter table profile add column if not exists onboarding_step text;            -- null: not started; 'done' when finished
alter table profile add column if not exists feed_mode text default 'personal'; -- 'personal' (For you first) or 'all'
alter table profile add column if not exists check_every_minutes int default 60; -- 30, 60 or 120 (kick-run follows it)
alter table profile add column if not exists check_from text default '06:00';   -- IST, the hours Ping may check the ERP
alter table profile add column if not exists check_to text default '01:00';

create table if not exists roles (
  id text primary key,             -- yop:com_id:jnf_id
  yop text, com_id text, jnf_id text,
  company text, designation text,
  ctc numeric, ctc_text text, currency text,
  has_company_doc boolean, has_ppt_doc boolean, has_form_doc boolean,
  applied boolean,
  apply_start timestamptz, apply_end timestamptz, apply_end_text text,
  interview_date text, contract text,
  details_fetched boolean default false,
  form_type text, bond text, additional_criteria text,
  cgpa_cutoff numeric, cgpa_cutoff_text text, job_description text,
  erp_messages jsonb, allowed jsonb, has_more_details_link boolean, applied_resume_link boolean,
  more_details jsonb, backlog_rule text, cgpa_criteria text,
  selection_details jsonb, has_written_test boolean,
  eligible boolean, eligibility jsonb,
  effective_deadline timestamptz, deadline_source text,
  first_seen timestamptz default now(), last_seen timestamptz,
  is_sample boolean default false
);
-- "For you" or not, per role: {relevant, reason, jd_missing, key, targets, model} (ping/relevance.py)
alter table roles add column if not exists relevance jsonb;

create table if not exists notices (
  id text primary key,             -- year:notice_id
  year text, notice_id int,
  type text, subject text, company text,
  preview text, text text,
  notice_time timestamptz, notice_time_text text,
  has_attachment boolean,
  analysis jsonb,
  first_seen timestamptz default now(),
  is_sample boolean default false
);
create index if not exists notices_time on notices (notice_time desc);

create table if not exists pdf_checks (
  notice_id text primary key,      -- notices.id
  status text,                     -- yes / no / unknown
  matched_by text,                 -- roll / name
  format text, pages int, text_chars int,
  scanned boolean, ocr boolean, roll_like_count int,
  header jsonb, my_row jsonb,      -- ONLY your own row + the table heading
  context text, details jsonb, error text,
  checked_at timestamptz default now(),
  is_sample boolean default false
);

create table if not exists items (
  id text primary key,
  level text,                      -- always / show / hidden
  category text,
  title text,                      -- one line, under 160 characters
  company text,
  role_ids jsonb, notice_id int,
  due_at timestamptz, event_at timestamptz,
  pdf_status text, needs_review boolean default false,
  details jsonb,
  sort_at timestamptz,
  first_seen timestamptz default now(),
  updated_at timestamptz default now(),
  dismissed boolean default false, -- for the dashboard
  done boolean default false,      -- for the dashboard
  is_sample boolean default false
);
create index if not exists items_level on items (level, sort_at desc);

create table if not exists emails (
  id text primary key,
  received_at timestamptz, sender text, subject text, snippet text,
  company text, links jsonb,
  is_sample boolean default false
);
-- placement mail as a source (ping/mail_source.py): what the mail is, its dates and link, the attachment check
-- (your row and the table heading only). Mails that aren't about placements are never stored.
alter table emails add column if not exists kind text;
alter table emails add column if not exists main_link text;
alter table emails add column if not exists due_at timestamptz;
alter table emails add column if not exists event_at timestamptz;
alter table emails add column if not exists when_text text;
alter table emails add column if not exists pdf jsonb;
alter table emails add column if not exists kept_because text;
alter table emails add column if not exists rules_version int;

create table if not exists contacts (
  id text primary key,
  notice_id int, company text, name text, phone text,
  created_at timestamptz default now(),
  is_sample boolean default false
);

create table if not exists runs (
  id text primary key,
  started_at timestamptz, finished_at timestamptz,
  trigger text, mode text, status text,
  login_seconds numeric, otp_seconds numeric, otp_requests int,
  gate_requests int,
  counts jsonb, problems jsonb,
  is_sample boolean default false
);

create table if not exists state (
  key text primary key,
  value jsonb,
  updated_at timestamptz default now()
);

create table if not exists corrections (   -- your fixes from the dashboard
  notice_id text primary key,              -- notices.id
  company text,                            -- "this notice is about X"
  profiles jsonb,
  ignore boolean default false,            -- "not relevant, hide it"
  created_at timestamptz default now()
);

alter table profile enable row level security;
alter table roles enable row level security;
alter table notices enable row level security;
alter table pdf_checks enable row level security;
alter table items enable row level security;
alter table emails enable row level security;
alter table contacts enable row level security;
alter table runs enable row level security;
alter table state enable row level security;
alter table corrections enable row level security;

insert into profile (id) values (1) on conflict (id) do nothing;

-- ---------------------------------------------------------------- dashboard
-- Who may log in to the dashboard and see the data. Ping adds your
-- MAIL_ADDRESS here on every run; add another email by inserting a row.
create table if not exists allowed_users (
  email text primary key,
  created_at timestamptz default now()
);
alter table allowed_users enable row level security;

create or replace function is_ping_owner() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from allowed_users where lower(email) = lower(auth.jwt() ->> 'email'));
$$;
grant execute on function is_ping_owner() to authenticated;

do $$
declare t text;
begin
  foreach t in array array['profile','roles','notices','pdf_checks','items','emails','contacts','runs','corrections'] loop
    execute format('drop policy if exists owner_read on %I', t);
    execute format('create policy owner_read on %I for select to authenticated using (is_ping_owner())', t);
  end loop;
end $$;

drop policy if exists owner_edit_profile on profile;
create policy owner_edit_profile on profile for update to authenticated
  using (is_ping_owner()) with check (is_ping_owner());
drop policy if exists owner_mark_items on items;
create policy owner_mark_items on items for update to authenticated
  using (is_ping_owner()) with check (is_ping_owner());
drop policy if exists owner_fix_notices on corrections;
create policy owner_fix_notices on corrections for all to authenticated
  using (is_ping_owner()) with check (is_ping_owner());

-- feedback said in the chat ("Piramal not relevant", "hide the SDE role at X", "undo"): role-level lists next to the
-- company lists, and the lists as they were before the last change (what "undo" restores)
alter table profile add column if not exists hidden_roles text[] default '{}';
alter table profile add column if not exists shown_roles text[] default '{}';
alter table profile add column if not exists prefs_undo jsonb;

-- The dashboard may only change these columns:
revoke update on profile, items from authenticated;
grant update (roll, name, department, degree, cgpa, active_backlogs, cv_names, interested_companies,
              not_interested_companies, notice_types, reminder_hours, targets, list_other_roles, cvs, onboarding_step, feed_mode, check_every_minutes,
              check_from, check_to, updated_at, hidden_roles, shown_roles, prefs_undo) on profile to authenticated;
grant update (dismissed, done) on items to authenticated;
grant select on profile, roles, notices, pdf_checks, items, emails, contacts, runs, corrections to authenticated;
grant insert, update, delete on corrections to authenticated;

-- Ping's secret key needs explicit access too: newer Supabase projects don't
-- grant API roles access to tables created with SQL.
grant usage on schema public to service_role, authenticated;
grant select, insert, update, delete on all tables in schema public to service_role;
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;


create table if not exists chat_messages (
  id bigint generated always as identity primary key,
  role text not null check (role in ('me', 'ping')),
  text text not null,
  created_at timestamptz default now(),
  is_sample boolean default false
);
alter table chat_messages enable row level security;

alter table profile add column if not exists chat_read_at timestamptz;

drop policy if exists owner_chat_read on chat_messages;
create policy owner_chat_read on chat_messages for select to authenticated using (is_ping_owner());
drop policy if exists owner_chat_write on chat_messages;
create policy owner_chat_write on chat_messages for insert to authenticated with check (is_ping_owner());

grant select, insert on chat_messages to authenticated;
grant select, insert, update, delete on chat_messages to service_role;
grant update (chat_read_at) on profile to authenticated;

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

-- ------------------------------------------------------------------ "For you" marks, shared by every profile
-- One row per (what someone is looking for, a role's text): identical targets reuse the answer, whoever asked.
-- Keys are hashes (ping/relevance.py: targets_hash, role_hash); no text, no user id. Only the server reads or
-- writes it (the hourly run and the ask-ping function, with the service key): no policy for signed-in users.
create table if not exists role_marks (
  targets_hash text not null,
  role_hash text not null,
  relevant boolean not null,
  reason text,
  jd_missing boolean default false,
  model text,
  created_at timestamptz default now(),
  primary key (targets_hash, role_hash)
);
alter table role_marks add column if not exists best_cv text;   -- the label of the CV to apply with
alter table role_marks enable row level security;
revoke all on role_marks from anon, authenticated;
grant select, insert, update, delete on role_marks to service_role;

-- ------------------------------------------------------------------ a demo session's own preferences
-- A one-click demo visitor may say what they're looking for too. It applies to their session only (never the
-- owner's profile, never another session) and goes when the session is cleaned up.
create table if not exists session_prefs (
  owner_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  targets text,
  reminder_hours numeric,
  list_other_roles boolean,
  updated_at timestamptz default now()
);
-- the demo's onboarding answers stay in the session too
alter table session_prefs add column if not exists onboarding_step text;
alter table session_prefs add column if not exists feed_mode text;
alter table session_prefs add column if not exists department text;
alter table session_prefs add column if not exists degree text;
alter table session_prefs add column if not exists check_every_minutes int;
alter table session_prefs add column if not exists check_from text;
alter table session_prefs add column if not exists check_to text;
-- a demo session's own feedback lists (never the owner's)
alter table session_prefs add column if not exists not_interested_companies text[];
alter table session_prefs add column if not exists interested_companies text[];
alter table session_prefs add column if not exists hidden_roles text[];
alter table session_prefs add column if not exists shown_roles text[];
alter table session_prefs add column if not exists prefs_undo jsonb;
alter table session_prefs enable row level security;
revoke all on session_prefs from anon, authenticated;
grant select, insert, update, delete on session_prefs to authenticated;
grant select, insert, update, delete on session_prefs to service_role;
drop policy if exists demo_own_prefs on session_prefs;
create policy demo_own_prefs on session_prefs for all to authenticated
  using (is_ping_demo() and owner_id = auth.uid()) with check (is_ping_demo() and owner_id = auth.uid());

-- ------------------------------------------------------------------ CVs: a private Storage bucket
-- Only the owner's login can upload, list, download, replace or delete; demo sessions and everyone else see
-- nothing (no policy for them). The hourly run reads new CVs with the service key to summarise them.
do $cvs$
begin
  -- a real Supabase project always has Storage; a bare Postgres (the local test replica) doesn't
  if to_regclass('storage.buckets') is null then
    raise notice 'no Storage here: the cvs bucket is skipped';
    return;
  end if;
  insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  values ('cvs', 'cvs', false, 5242880, array['application/pdf'])
  on conflict (id) do update set public = false, file_size_limit = 5242880, allowed_mime_types = array['application/pdf'];
  drop policy if exists ping_cvs_owner_read on storage.objects;
  drop policy if exists ping_cvs_owner_write on storage.objects;
  drop policy if exists ping_cvs_owner_update on storage.objects;
  drop policy if exists ping_cvs_owner_delete on storage.objects;
  create policy ping_cvs_owner_read on storage.objects for select to authenticated
    using (bucket_id = 'cvs' and public.is_ping_owner());
  create policy ping_cvs_owner_write on storage.objects for insert to authenticated
    with check (bucket_id = 'cvs' and public.is_ping_owner());
  create policy ping_cvs_owner_update on storage.objects for update to authenticated
    using (bucket_id = 'cvs' and public.is_ping_owner()) with check (bucket_id = 'cvs' and public.is_ping_owner());
  create policy ping_cvs_owner_delete on storage.objects for delete to authenticated
    using (bucket_id = 'cvs' and public.is_ping_owner());
end $cvs$;

-- Live updates on the dashboard (no reloads): each run reports its progress in its own row, and the page listens
-- to chat_messages and runs with Supabase Realtime. Realtime applies the same row rules as reading: a demo session
-- only ever receives its own chat rows and the demo's runs, never the owner's.
alter table runs add column if not exists stage text;            -- queued, logging in, reading companies,
                                                                  -- reading notices, reading PDFs, saving, done, failed
alter table runs add column if not exists requested_at timestamptz;  -- Check now: when it was pressed
alter table runs add column if not exists new_items int;          -- new messages in the chat from this run
alter table runs add column if not exists note text;              -- why a run failed, in the words the chat uses
do $rt$
declare t text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    raise notice 'no supabase_realtime publication here: live updates skipped';
    return;
  end if;
  foreach t in array array['chat_messages', 'runs'] loop
    if not exists (select 1 from pg_publication_tables
                   where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $rt$;

-- Job descriptions (ping/jd.py): the text Ping found for each role and where it found it, and a short summary.
alter table roles add column if not exists jd_text text;          -- the JD itself (ERP field, ERP file, public link, more details)
alter table roles add column if not exists jd_source text;        -- inline / detail / attachment / link / link-unreadable / none
alter table roles add column if not exists jd_url text;           -- the file on the ERP or the link it came from
alter table roles add column if not exists jd_note text;          -- why there's none (e.g. "link: HTTP 401", "only by email")
alter table roles add column if not exists jd_key text;           -- the role's JD inputs: fetched again only when they change
alter table roles add column if not exists jd_summary jsonb;      -- {role_team, do[], must_have[], location, eligibility, unusual[], key}

-- ---------------------------------------------------------------- push notifications (docs/PUSH.md)
-- One row per device that said yes. Only the owner may add, see or remove them (a demo session can't subscribe);
-- the send-push function reads them with the service key. No key material that could send pushes is here: the
-- VAPID private key is a Supabase function secret.
create table if not exists push_subscriptions (
  endpoint text primary key,
  p256dh text not null,
  auth text not null,
  user_agent text,
  created_at timestamptz default now(),
  last_ok_at timestamptz,
  failures int default 0
);
alter table push_subscriptions enable row level security;
drop policy if exists owner_push on push_subscriptions;
create policy owner_push on push_subscriptions for all to authenticated using (is_ping_owner()) with check (is_ping_owner());
revoke all on push_subscriptions from anon;
grant select, insert, update, delete on push_subscriptions to authenticated;

-- What was sent and what's waiting: one row per message pushed by a run ('run:<item id>', so never twice) and per
-- test-day reminder ('reminder:<item id>', sent by pg_cron through send-push at send_at). Server only: no policies.
create table if not exists push_queue (
  id text primary key,
  kind text not null,
  title text not null,
  body text,
  url text,
  tag text,
  event_at timestamptz,
  send_at timestamptz not null,
  sent_at timestamptz,
  result text,
  created_at timestamptz default now()
);
alter table push_queue enable row level security;
revoke all on push_queue from anon, authenticated;
create index if not exists push_queue_due on push_queue (send_at) where sent_at is null;

-- also email the for-you messages (off by default; the 3-failed-runs alert is mailed either way)
alter table profile add column if not exists email_digests boolean default false;

-- ------------------------------------------------------------------ profile snapshots (Admin > profile-snapshot /
-- profile-restore): the owner's profile row, push subscriptions and the list of CV files copied in the cvs bucket,
-- so it can be put back exactly after someone else has used the account (judging). Only the service key reaches it.
create table if not exists public.profile_snapshots (
  id bigserial primary key, taken_at timestamptz default now(), profile jsonb not null,
  push_subscriptions jsonb not null default '[]', files jsonb not null default '[]');
alter table public.profile_snapshots enable row level security;
revoke all on public.profile_snapshots from anon, authenticated;
grant all on public.profile_snapshots to service_role;
grant usage, select on sequence public.profile_snapshots_id_seq to service_role;

-- ------------------------------------------------------------------ forms (ping/forms.py)
-- Every form that has come in (notices, their PDFs, placement mail), one row per form (its canonical key), built by
-- the hourly run; your ticks in form_status (each login's own rows: the owner's are the owner's alone, a demo
-- session's are its own and never count for anything); your Merge / Keep both answers in form_merges.
-- Ping never submits, prefills or signs in to a form: a tick is your own record, written nowhere else.
create table if not exists forms (
  key text primary key,
  company text, companies text[] default '{}', purpose text,
  title text, description text, question_count int, closed boolean default false, signin_required boolean default false,
  due_at timestamptz, deadline_history jsonb default '[]', link text, final_url text,
  sources jsonb default '[]', first_seen timestamptz default now(), last_seen timestamptz,
  item_ids text[] default '{}', role_ids text[] default '{}', looks_like jsonb default '[]', merged_keys text[] default '{}',
  is_sample boolean default false
);
alter table forms enable row level security;
drop policy if exists owner_forms_read on forms;
create policy owner_forms_read on forms for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false));
drop policy if exists demo_forms_read on forms;
create policy demo_forms_read on forms for select to authenticated using (is_ping_demo() and is_sample is true);
grant select on forms to authenticated;
grant select, insert, update, delete on forms to service_role;

create table if not exists form_status (
  owner_id uuid not null default auth.uid(),
  form_key text not null,
  filled boolean not null default false,
  filled_at timestamptz,
  updated_at timestamptz default now(),
  is_demo boolean not null default coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false),
  primary key (owner_id, form_key)
);
-- "Not for me" (dashboard/forms.js, ping/forms.py not_for_me_items): your own record, per login like the tick; a
-- form's key, "item:<id>", "kind:company:<name>" / "kind:role:<type>" (said yes to in the chat), "asked:..." (asked once)
alter table form_status add column if not exists not_for_me boolean not null default false;
alter table form_status add column if not exists not_for_me_at timestamptz;
alter table form_status add column if not exists not_for_me_reason text;
alter table form_status enable row level security;
drop policy if exists own_form_status on form_status;
create policy own_form_status on form_status for all to authenticated
  using (owner_id = auth.uid() and (is_ping_owner() or is_ping_demo()))
  with check (owner_id = auth.uid() and (is_ping_owner() or is_ping_demo())
              and is_demo = coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false));
grant select, insert, update, delete on form_status to authenticated;
grant select, insert, update, delete on form_status to service_role;

create table if not exists form_merges (
  owner_id uuid not null default auth.uid(),
  a text not null, b text not null,
  choice text not null check (choice in ('merge', 'keep')),
  decided_at timestamptz default now(),
  is_demo boolean not null default coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false),
  primary key (owner_id, a, b)
);
alter table form_merges enable row level security;
drop policy if exists own_form_merges on form_merges;
create policy own_form_merges on form_merges for all to authenticated
  using (owner_id = auth.uid() and (is_ping_owner() or is_ping_demo()))
  with check (owner_id = auth.uid() and (is_ping_owner() or is_ping_demo())
              and is_demo = coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false));
grant select, insert, update, delete on form_merges to authenticated;
grant select, insert, update, delete on form_merges to service_role;

-- what Ping read from each form's public page (cached; service key only)
create table if not exists form_pages (
  key text primary key, final_url text, fetched_at timestamptz default now(), title text, description text,
  question_count int, closed boolean default false, signin_required boolean default false, error text
);
alter table form_pages enable row level security;
revoke all on form_pages from anon, authenticated;
grant select, insert, update, delete on form_pages to service_role;

-- reminders queued for a form are skipped at send time if you've ticked it (send-push)
alter table push_queue add column if not exists form_key text;

-- ticks reach your other open devices at once
do $fs$
declare t text;
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then return; end if;
  foreach t in array array['form_status', 'forms'] loop
    if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t) then
      execute format('alter publication supabase_realtime add table public.%I', t);
    end if;
  end loop;
end $fs$;

-- the nightly demo cleanup also removes old demo sessions' form ticks and merge answers (never the owner's: those
-- aren't is_demo)
create or replace function cleanup_demo_sessions(days int default 7) returns jsonb
language plpgsql volatile security definer set search_path = public, auth as $$
declare c int; q int; u int; f int;
begin
  delete from public.chat_messages
    where owner_id in (select id from auth.users where is_anonymous and created_at < now() - make_interval(days => days))
       or (is_sample and created_at < now() - make_interval(days => days));
  get diagnostics c = row_count;
  delete from public.demo_questions where asked_at < now() - make_interval(days => days);
  get diagnostics q = row_count;
  delete from public.form_status where is_demo
    and owner_id in (select id from auth.users where is_anonymous and created_at < now() - make_interval(days => days));
  get diagnostics f = row_count;
  delete from public.form_merges where is_demo
    and owner_id in (select id from auth.users where is_anonymous and created_at < now() - make_interval(days => days));
  delete from auth.users where is_anonymous and created_at < now() - make_interval(days => days);
  get diagnostics u = row_count;
  return jsonb_build_object('anonymous_users', u, 'chat_messages', c, 'demo_question_counts', q, 'form_ticks', f);
end $$;
revoke all on function cleanup_demo_sessions(int) from public, anon, authenticated;
grant execute on function cleanup_demo_sessions(int) to service_role;

-- "check FirstClub again": one company read again from the ERP now (read-only, the same gate as the hourly run).
-- check-now creates the row (at most one per company per 5 minutes), the Ping workflow (mode recheck) fills it in,
-- the page waits for it on Realtime and answers from result. Never counts as the hourly run.
create table if not exists rechecks (
  id text primary key,
  company text not null,
  question text,
  requested_at timestamptz default now(),
  started_at timestamptz, finished_at timestamptz,
  status text default 'queued',      -- queued, running, done, unreachable, failed
  note text,
  result jsonb,
  is_sample boolean default false
);
create index if not exists rechecks_company on rechecks (lower(company), requested_at desc);
alter table rechecks enable row level security;
revoke all on rechecks from anon;
grant select on rechecks to authenticated;
grant select, insert, update, delete on rechecks to service_role;
drop policy if exists owner_rechecks_read on rechecks;
create policy owner_rechecks_read on rechecks for select to authenticated using (is_ping_owner() and not coalesce(is_sample, false));
do $rc$
begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then return; end if;
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'rechecks') then
    alter publication supabase_realtime add table public.rechecks;
  end if;
end $rc$;

-- reply to a message: what a chat message answers (a feed message "item:<id>" or a chat bubble "msg:<role>:<ms>")
-- and the quote shown inside it
alter table chat_messages add column if not exists reply_to text;
alter table chat_messages add column if not exists reply_quote jsonb;
