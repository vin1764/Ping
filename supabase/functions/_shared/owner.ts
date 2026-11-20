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

// Uses the caller's own login token, so Row Level Security applies exactly as in the dashboard.
export async function ownerClient(req: Request) {
  const auth = req.headers.get("Authorization") ?? "";
  const key = Deno.env.get("PING_PUBLISHABLE_KEY") || Deno.env.get("SUPABASE_ANON_KEY") || "";
  const sb = createClient(Deno.env.get("SUPABASE_URL")!, key, { global: { headers: { Authorization: auth } } });
  const { data, error } = await sb.rpc("is_ping_owner");
  if (error || data !== true) return null;
  return sb;
}
