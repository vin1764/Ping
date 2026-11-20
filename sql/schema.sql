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
  is_sample boolean default false,
  updated_at timestamptz default now()
);

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

-- The dashboard may only change these columns:
revoke update on profile, items from authenticated;
grant update (roll, name, department, degree, cgpa, active_backlogs, cv_names, interested_companies,
              not_interested_companies, notice_types, updated_at) on profile to authenticated;
grant update (dismissed, done) on items to authenticated;
grant select on profile, roles, notices, pdf_checks, items, emails, contacts, runs, corrections to authenticated;
grant insert, update, delete on corrections to authenticated;
