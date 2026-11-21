// Should the hourly run start now? Shared by kick-run (Supabase's hourly call) and mirrored in
// ping/schedule_guard.py (GitHub's own cron, kept as a backup), so the two never start two runs.
export const MIN_GAP_MINUTES = 50;
const BUSY = new Set(["queued", "in_progress", "waiting", "requested", "pending"]);

export interface Run { id: number; status: string; created_at: string; run_started_at?: string }

export function decide(runs: Run[], now: Date, ignoreId?: number): { start: boolean; why: string } {
  const others = runs.filter((r) => r.id !== ignoreId);
  const busy = others.find((r) => BUSY.has(r.status));
  if (busy) return { start: false, why: `a Ping run is ${busy.status.replace("_", " ")} (run ${busy.id})` };
  const latest = others.map((r) => new Date(r.run_started_at || r.created_at).getTime()).sort((a, b) => b - a)[0];
  if (latest && now.getTime() - latest < MIN_GAP_MINUTES * 60_000) {
    return { start: false, why: `a Ping run started ${Math.round((now.getTime() - latest) / 60_000)} min ago` };
  }
  return { start: true, why: latest ? `last run started ${Math.round((now.getTime() - latest) / 60_000)} min ago` : "no earlier runs" };
}
