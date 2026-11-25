// Shared by both functions: CORS + "is the caller the logged-in owner?"
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

export const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info, x-ping-evals",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });
}

// Uses the caller's own login token, so Row Level Security applies exactly as in the dashboard:
// the owner reads only real rows, a demo session only the anonymised demo rows.
export function client(req: Request) {
  const auth = req.headers.get("Authorization") ?? "";
  const key = Deno.env.get("PING_PUBLISHABLE_KEY") || Deno.env.get("SUPABASE_ANON_KEY") || "";
  return createClient(Deno.env.get("SUPABASE_URL")!, key, { global: { headers: { Authorization: auth } } });
}

// Who is calling: the owner (real rows), a one-click demo session (anonymous sign-in: the anonymised demo
// rows only, read-only, by the database's own rules), or nobody.
// Both checks are asked at once (one round trip, not two); the owner check still wins, as before.
export async function caller(req: Request, sb = client(req)) {
  const [owner, demo] = await Promise.all([sb.rpc("is_ping_owner"), sb.rpc("is_ping_demo")]);
  if (!owner.error && owner.data === true) return { sb, role: "owner" as const };
  return !demo.error && demo.data === true ? { sb, role: "demo" as const } : null;
}
