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
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/ping.yml/dispatches`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ping-dashboard" },
    body: JSON.stringify({ ref, inputs: { mode: "run" } }),
  });
  if (r.status !== 204) return json({ error: `GitHub said ${r.status}: ${(await r.text()).slice(0, 200)}` }, 502);
  return json({ ok: true });
});
