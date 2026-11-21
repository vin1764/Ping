// Shared by both functions: CORS + "is the caller the logged-in owner?"
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

export const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
}

// Uses the caller's own login token, so Row Level Security applies exactly as in the dashboard:
// the owner reads only real rows, a reviewer only the anonymised demo rows.
function client(req: Request) {
  const auth = req.headers.get("Authorization") ?? "";
  const key = Deno.env.get("PING_PUBLISHABLE_KEY") || Deno.env.get("SUPABASE_ANON_KEY") || "";
  return createClient(Deno.env.get("SUPABASE_URL")!, key, { global: { headers: { Authorization: auth } } });
}

export async function ownerClient(req: Request) {
  const sb = client(req);
  const { data, error } = await sb.rpc("is_ping_owner");
  return error || data !== true ? null : sb;
}

export async function ownerOrReviewerClient(req: Request) {
  return (await caller(req))?.sb ?? null;
}

// Who is calling: the owner (real rows) or the reviewer (anonymised demo rows), or nobody.
export async function caller(req: Request) {
  const sb = client(req);
  const owner = await sb.rpc("is_ping_owner");
  if (!owner.error && owner.data === true) return { sb, role: "owner" as const };
  const reviewer = await sb.rpc("is_ping_reviewer");
  return !reviewer.error && reviewer.data === true ? { sb, role: "reviewer" as const } : null;
}
