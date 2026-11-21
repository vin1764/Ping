// Should a scheduled Ping run start now? Shared by kick-run (Supabase's pg_cron calls it every 30 minutes) and
// mirrored in ping/schedule_guard.py (GitHub's own cron, kept as a backup), so the two never start two runs.
// The student's own schedule decides (profile: check_every_minutes, check_from, check_to, in IST; set in the
// chat or on the Profile page): a run starts only inside that window and once the last run is at least
// (every - 10) minutes old, and never while one is going.
export const DEFAULT_SCHEDULE = { every_minutes: 60, from: "06:00", to: "01:00" };
export const MIN_GAP_MINUTES = DEFAULT_SCHEDULE.every_minutes - 10;   // 50 for the default hourly schedule
const BUSY = new Set(["queued", "in_progress", "waiting", "requested", "pending"]);

export interface Run { id: number; status: string; created_at: string; run_started_at?: string }
export interface Schedule { every_minutes?: number | null; from?: string | null; to?: string | null }

const mins = (hhmm: string) => { const [h, m] = hhmm.split(":").map(Number); return (h % 24) * 60 + (m || 0); };

// IST minutes since midnight
function istMinutes(now: Date): number {
  const t = new Date(now.getTime() + 330 * 60_000);
  return t.getUTCHours() * 60 + t.getUTCMinutes();
}

export function inWindow(now: Date, from: string, to: string): boolean {
  const m = istMinutes(now), f = mins(from), t = mins(to);
  if (f === t) return true;                         // the same start and end: all day
  return f < t ? m >= f && m < t : m >= f || m < t;  // a window past midnight wraps
}

export function decide(runs: Run[], now: Date, ignoreId?: number, schedule: Schedule = {}):
  { start: boolean; why: string } {
  const s = { ...DEFAULT_SCHEDULE, ...Object.fromEntries(Object.entries(schedule).filter(([, v]) => v != null)) } as
    typeof DEFAULT_SCHEDULE;
  if (!inWindow(now, s.from, s.to)) return { start: false, why: `outside your hours (${s.from}-${s.to} IST)` };
  const gap = Math.max(20, s.every_minutes - 10);
  const others = runs.filter((r) => r.id !== ignoreId);
  const busy = others.find((r) => BUSY.has(r.status));
  if (busy) return { start: false, why: `a Ping run is ${busy.status.replace("_", " ")} (run ${busy.id})` };
  const latest = others.map((r) => new Date(r.run_started_at || r.created_at).getTime()).sort((a, b) => b - a)[0];
  if (latest && now.getTime() - latest < gap * 60_000) {
    return { start: false, why: `a Ping run started ${Math.round((now.getTime() - latest) / 60_000)} min ago (every ${s.every_minutes} min)` };
  }
  return { start: true, why: latest ? `last run started ${Math.round((now.getTime() - latest) / 60_000)} min ago` : "no earlier runs" };
}
