-- The hourly Ping run and the daily demo cleanup, scheduled inside Supabase (GitHub's cron never fired for this
-- repo). Applied by Actions > Admin > schedule-setup, which fills in {{FUNCTION_URL}} and stores the shared secret
-- in Vault as 'ping_cron_secret' (and as the kick-run function's PING_CRON_SECRET). Safe to re-run.
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;
grant usage on schema cron to postgres;

select cron.unschedule(jobid) from cron.job where jobname in ('ping-hourly', 'ping-demo-cleanup');

-- every hour at :41 UTC from 00:41 to 19:41 = 06:11 to 01:11 IST; kick-run skips if a run is going or recent
select cron.schedule('ping-hourly', '41 0-19 * * *', $job$
  select net.http_post(
    url := '{{FUNCTION_URL}}',
    headers := jsonb_build_object('Content-Type', 'application/json', 'x-ping-cron',
                                  (select decrypted_secret from vault.decrypted_secrets where name = 'ping_cron_secret')),
    body := '{"task": "run"}'::jsonb,
    timeout_milliseconds := 30000)
$job$);

-- once a day at 21:23 UTC (02:53 IST): demo sessions older than 7 days and their chat
select cron.schedule('ping-demo-cleanup', '23 21 * * *', $job$ select public.cleanup_demo_sessions(7) $job$);
