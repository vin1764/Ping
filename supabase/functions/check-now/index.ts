// "Check now": starts the Ping workflow on GitHub. The GitHub token lives only here
// (a Supabase function secret), never in the browser.
import { caller, cors, json } from "../_shared/owner.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const who = await caller(req);
  if (who?.role === "demo") {
    return json({ error: "The demo can't start a check: Ping only logs in to the ERP for its owner." }, 403);
  }
  if (!who) return json({ error: "not allowed" }, 403);
  const repo = Deno.env.get("PING_GITHUB_REPO");
  const token = Deno.env.get("PING_GITHUB_TOKEN");
  const ref = Deno.env.get("PING_GITHUB_REF") || "main";
  if (!repo || !token) return json({ error: "check-now is not configured (PING_GITHUB_REPO / PING_GITHUB_TOKEN)" }, 500);
  // The run's row, created now ("queued"), so the dashboard shows the check from the first second; the run fills it
  // in (logging in, reading ..., done). Best effort: without it the run still starts and makes its own row.
  const svc = Deno.env.get("PING_SERVICE_KEY"), base = Deno.env.get("SUPABASE_URL");
  const now = new Date();
  const id = now.toISOString().replace(/[-:]/g, "").slice(0, 15) + "-check" + crypto.randomUUID().slice(0, 4);
  let row = "";
  if (svc && base) {
    const ins = await fetch(`${base}/rest/v1/runs`, {
      method: "POST",
      headers: { apikey: svc, Authorization: `Bearer ${svc}`, "Content-Type": "application/json", Prefer: "return=minimal" },
      body: JSON.stringify({ id, trigger: "manual", mode: "run", status: "queued", stage: "queued", requested_at: now.toISOString() }),
    }).catch(() => null);
    if (ins?.ok) row = id;
    else console.error(JSON.stringify({ event: "queued_row_failed", status: ins?.status ?? 0 }));
  }
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/ping.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ping-dashboard" },
    body: JSON.stringify({ ref, inputs: { mode: "run", ...(row ? { run_row: row } : {}) } }),
  });
  if (r.status !== 204) {
    // the check didn't start: the queued row says so, so the chat doesn't wait for it
    if (row) await fetch(`${base}/rest/v1/runs?id=eq.${row}`, {
      method: "PATCH", headers: { apikey: svc!, Authorization: `Bearer ${svc}`, "Content-Type": "application/json" },
      body: JSON.stringify({ status: "failed: not started", stage: "failed", note: `GitHub didn't start the check (${r.status}).` }),
    }).catch(() => null);
    return json({ error: `GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}`, run_row: row || null }, 502);
  }
  return json({ ok: true, run_row: row || null });
});
