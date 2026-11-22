// "kick-run": Supabase's own scheduler (pg_cron, see sql/schedule.sql) calls this every 30 minutes. It starts the
// Ping workflow on GitHub, the same way the dashboard's Check now does and with the same GitHub token, when the
// student's own schedule says so (profile: how often, between which hours; set during onboarding, in the chat or on
// the Profile page; default every hour, 06:00-01:00 IST) and no Ping run is going (guard.ts; GitHub's own cron
// line in ping.yml is kept as a backup and uses the same rule). The runs it starts count as scheduled
// runs: a refused-credentials pause still holds and failures stay quiet.
// Only callers with the shared secret (PING_CRON_SECRET, also kept in the database's Vault) get in.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { json } from "../_shared/owner.ts";
import { decide, type Schedule } from "./guard.ts";

// the owner's schedule (the real profile row); the default when it can't be read
async function schedule(): Promise<Schedule> {
  const key = Deno.env.get("PING_SERVICE_KEY") || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!key) return {};
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, key);
  const { data } = await sb.from("profile").select("check_every_minutes,check_from,check_to").eq("id", 1).limit(1);
  const p: any = data?.[0] || {};
  return { every_minutes: p.check_every_minutes, from: p.check_from, to: p.check_to };
}

// when the last real Ping run started (runs table); undefined when it can't be read (then GitHub's list decides)
async function lastStarted(): Promise<string | null | undefined> {
  const key = Deno.env.get("PING_SERVICE_KEY") || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!key) return undefined;
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, key);
  const { data, error } = await sb.from("runs").select("started_at").order("started_at", { ascending: false }).limit(1);
  if (error) return undefined;
  return data?.[0]?.started_at ?? null;
}

Deno.serve(async (req) => {
  const secret = Deno.env.get("PING_CRON_SECRET");
  if (!secret || req.headers.get("x-ping-cron") !== secret) return json({ error: "not allowed" }, 403);
  const { task = "run" } = await req.json().catch(() => ({}));
  if (task !== "run" && task !== "check") return json({ error: "task must be run or check" }, 400);
  const repo = Deno.env.get("PING_GITHUB_REPO");
  const token = Deno.env.get("PING_GITHUB_TOKEN");
  const ref = Deno.env.get("PING_GITHUB_REF") || "main";
  if (!repo || !token) return json({ error: "PING_GITHUB_REPO / PING_GITHUB_TOKEN not set" }, 500);
  const gh = { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ping-kick-run" };
  const base = `https://api.github.com/repos/${repo}/actions/workflows/ping.yml`;
  const list = await fetch(`${base}/runs?per_page=10`, { headers: gh });
  if (!list.ok) {
    console.error(JSON.stringify({ event: "kick_failed", step: "list runs", status: list.status }));
    return json({ error: `GitHub said ${list.status} when listing runs` }, 502);
  }
  const runs = (await list.json()).workflow_runs || [];
  const plan = await schedule();
  const d = decide(runs, new Date(), undefined, plan, await lastStarted());
  if (!d.start || task === "check") {
    console.log(JSON.stringify({ event: task === "check" ? "kick_check" : "kick_skipped", why: d.why, start: d.start, plan }));
    return json({ started: false, would_start: d.start, why: d.why, schedule: plan });
  }
  const r = await fetch(`${base}/dispatches`, {
    method: "POST", headers: gh, body: JSON.stringify({ ref, inputs: { mode: "run", source: "schedule" } }),
  });
  if (r.status !== 204) {
    console.error(JSON.stringify({ event: "kick_failed", step: "dispatch", status: r.status }));
    return json({ error: `GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
  }
  console.log(JSON.stringify({ event: "kick_started", why: d.why }));
  return json({ started: true, why: d.why });
});
