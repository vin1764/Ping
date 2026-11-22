// "Check now": starts the Ping workflow on GitHub. The GitHub token lives only here
// (a Supabase function secret), never in the browser.
import { caller, cors, json } from "../_shared/owner.ts";

const RECHECK_EVERY_MS = 5 * 60_000;   // one ERP re-check per company per 5 minutes

// "check FirstClub again": one company's notices and files read again from the ERP now (the Ping workflow, mode
// recheck, read-only). A second ask within 5 minutes gets the same re-check (its row), not another ERP login.
async function recheck(company: string, question: string): Promise<Response> {
  if (!company) return json({ error: "which company?" }, 400);
  const repo = Deno.env.get("PING_GITHUB_REPO"), token = Deno.env.get("PING_GITHUB_TOKEN");
  const ref = Deno.env.get("PING_GITHUB_REF") || "main";
  const svc = Deno.env.get("PING_SERVICE_KEY"), base = Deno.env.get("SUPABASE_URL");
  if (!repo || !token || !svc || !base) return json({ error: "re-check is not configured" }, 500);
  const H = { apikey: svc, Authorization: `Bearer ${svc}`, "Content-Type": "application/json" };
  const since = new Date(Date.now() - RECHECK_EVERY_MS).toISOString();
  const recent = await fetch(`${base}/rest/v1/rechecks?select=id,status,requested_at,finished_at&company=ilike.${encodeURIComponent(company)}` +
    `&requested_at=gte.${encodeURIComponent(since)}&status=in.(queued,running,done)&order=requested_at.desc&limit=1`, { headers: H })
    .then((r) => (r.ok ? r.json() : [])).catch(() => []);
  if (recent?.[0]) return json({ ok: true, recheck: recent[0].id, reused: true, status: recent[0].status });
  const id = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "-re" + crypto.randomUUID().slice(0, 6);
  const ins = await fetch(`${base}/rest/v1/rechecks`, { method: "POST", headers: { ...H, Prefer: "return=minimal" },
    body: JSON.stringify({ id, company, question, status: "queued" }) });
  if (!ins.ok) return json({ error: `the re-check couldn't be queued (${ins.status})` }, 502);
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/ping.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ping-dashboard" },
    body: JSON.stringify({ ref, inputs: { mode: "recheck", company, run_row: id } }),
  });
  if (r.status !== 204) {
    await fetch(`${base}/rest/v1/rechecks?id=eq.${id}`, { method: "PATCH", headers: H,
      body: JSON.stringify({ status: "failed", note: `GitHub didn't start the re-check (${r.status})`, finished_at: new Date().toISOString() }) }).catch(() => null);
    return json({ error: `GitHub said ${r.status}`, recheck: id }, 502);
  }
  console.log(JSON.stringify({ event: "recheck_started", id }));
  return json({ ok: true, recheck: id, reused: false, status: "queued" });
}

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
  const body = await req.json().catch(() => ({}));
  if (body?.task === "recheck") return recheck(String(body.company || "").trim().slice(0, 80), String(body.question || "").slice(0, 300));
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
