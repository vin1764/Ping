-- The hourly Ping run and the daily demo cleanup, scheduled inside Supabase (GitHub's cron never fired for this
-- repo). Applied by Actions > Admin > schedule-setup, which fills in {{FUNCTION_URL}} and stores the shared secret
-- in Vault as 'ping_cron_secret' (and as the kick-run function's PING_CRON_SECRET). Safe to re-run.
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
grant usage on schema cron to postgres;

select cron.unschedule(jobid) from cron.job where jobname in ('ping-hourly', 'ping-demo-cleanup', 'ping-push-due', 'ping-ask-warm');

-- every 30 minutes, all day (:11 and :41 UTC = :41 and :11 IST); kick-run starts a run only when the student's own
-- schedule says so (profile: check_every_minutes, check_from, check_to; default hourly, 06:00-01:00 IST)
select cron.schedule('ping-hourly', '11,41 * * * *', $job$
  select net.http_post(
    url := '{{FUNCTION_URL}}',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-ping-cron',
                                  (select decrypted_secret from vault.decrypted_secrets where name = 'ping_cron_secret')),
    body := '{"task": "run"}'::jsonb,
    timeout_milliseconds := 30000)
$job$);

-- once a day at 21:23 UTC (02:53 IST): demo sessions older than 7 days and their chat
select cron.schedule('ping-demo-cleanup', '23 21 * * *', $job$ select public.cleanup_demo_sessions(7) $job$);

-- every 5 minutes: test-day reminders whose time has come (push_queue), even when no run happens (docs/PUSH.md)
select cron.schedule('ping-push-due', '*/5 * * * *', $job$
  select net.http_post(
    url := '{{PUSH_URL}}',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-ping-cron',
                                  (select decrypted_secret from vault.decrypted_secrets where name = 'ping_cron_secret')),
    body := '{"mode": "due"}'::jsonb,
    timeout_milliseconds := 30000)
$job$);

-- every minute from 00:00 to 19:59 UTC (05:30-01:29 IST, around the 06:00-01:00 check hours): a warm-up for Ask Ping,
-- so an instance stays booted (an idle one shuts down after about a minute) and a question never waits for a cold
-- start. It reads nothing and answers nothing (ask-ping returns at once); about 1,200 calls a day.
select cron.schedule('ping-ask-warm', '* 0-19 * * *', $job$
  select net.http_post(
    url := '{{ASK_URL}}',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-ping-warm', '1', 'x-ping-cron',
                                  (select decrypted_secret from vault.decrypted_secrets where name = 'ping_cron_secret')),
    body := '{}'::jsonb,
    timeout_milliseconds := 10000)
$job$);
