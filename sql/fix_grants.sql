-- Run this once in Supabase > SQL Editor if Ping reports
-- "permission denied for table ..." (42501). Newer Supabase projects don't
-- give the API roles access to tables created with SQL automatically.
-- Safe to run more than once. Row Level Security still decides who sees rows.

grant usage on schema public to service_role, authenticated;

-- Ping's secret key: full access to its own tables
grant select, insert, update, delete on all tables in schema public to service_role;
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;

-- The dashboard login: read Ping's tables, and only the few edits it needs
grant select on profile, roles, notices, pdf_checks, items, emails, contacts, runs, corrections to authenticated;
grant update (roll, name, department, degree, cgpa, active_backlogs, cv_names, interested_companies,
              not_interested_companies, notice_types, reminder_hours, targets, list_other_roles, cvs, onboarding_step, feed_mode, check_every_minutes,
              check_from, check_to, updated_at) on profile to authenticated;
grant update (dismissed, done) on items to authenticated;
grant insert, update, delete on corrections to authenticated;
grant execute on function is_ping_owner() to authenticated;
