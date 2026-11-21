// Two things the model got wrong on its own, decided here instead (deterministic, tested in wording_test.ts):
// 1. Does the message ask Ping to DO something? Only then may the answer carry the read-only refusal.
// 2. For times today: already over, or how long until it (the model can't be trusted with the arithmetic).

const ACTIONS = "apply|withdraw|submit|upload|change|update|edit|accept|decline|reject|fill|register|cancel|sign\\s?up|opt\\s(?:in|out)|delete|remove|book|send|email|mail";
const ACT_WORD = new RegExp(`\\b(${ACTIONS})\\b`, "i");
const STARTS_WITH_ACT = new RegExp(`^(?:please\\s+|pls\\s+|kindly\\s+|ping,?\\s+)?(?:${ACTIONS})\\b`, "i");
const ASKS_YOU = /^(?:please\s+|pls\s+|kindly\s+)?(?:can|could|would|will)\s+(?:you|ping)\b/i;
const FOR_ME = /\b(?:for me|on my behalf)\b/i;

export function asksToAct(message: string): boolean {
  const t = message.trim();
  if (!ACT_WORD.test(t)) return false;
  return FOR_ME.test(t) || ASKS_YOU.test(t) || STARTS_WITH_ACT.test(t);
}

// "Ping is read-only, so I can't ..." (or any sentence that says Ping is read-only), removed from an answer to a
// question; what's left is the actual answer.
export function stripRefusal(answer: string): string {
  const out = answer
    .split(/\n/)
    .map((line) => line.replace(/(^|(?<=[.!?]\s))[^.!?\n]*\bread[- ]only\b[^.!?\n]*[.!?]?\s*/gi, "").trimEnd())
    .filter((line, i, all) => line.trim() !== "" || (i > 0 && all[i - 1].trim() !== ""))
    .join("\n")
    .trim();
  return out || answer;
}

const DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" });

// "(earlier today, already over)" / "(later today, in 1h 25m)" for times on the same IST day as now; "" otherwise.
export function todayNote(iso: string | null | undefined, now: Date): string {
  if (!iso) return "";
  const at = new Date(iso);
  if (DAY.format(at) !== DAY.format(now)) return "";
  const mins = Math.round((at.getTime() - now.getTime()) / 60_000);
  if (mins < 0) return " (earlier today, already over)";
  if (mins === 0) return " (now)";
  const h = Math.floor(mins / 60), m = mins % 60;
  return ` (later today, in ${h ? `${h}h ` : ""}${m}m)`;
}

// 3. "Today and this week" in numbers, counted here: the evals saw the model miss the Groww test that was earlier
// today, call deadlines tonight "not this week", and answer "anything else?" without the 48 roles closing at 20:00.
const HM = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" });
const WD = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", weekday: "short", day: "numeric", month: "short" });
const ISO_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", weekday: "short" });

type Ev = { title: string; at: string | null | undefined };
type Role = { company: string; applied: boolean | null; effective_deadline: string | null | undefined; for_you?: boolean };

function endOfWeek(now: Date): number {
  // Sunday 23:59:59 IST of the week (Mon-Sun) that holds `now`
  const wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(ISO_DAY.format(now).split(",")[0].trim());
  const ymd = DAY.format(now);
  const midnight = new Date(`${ymd}T00:00:00+05:30`).getTime();
  return midnight + (7 - Math.max(wd, 0)) * 86_400_000 - 1000;
}

export function glance(events: Ev[], roles: Role[], now: Date): string {
  const today = DAY.format(now);
  const lines: string[] = [];
  const seen = new Set<string>();
  const evToday = events.filter((e) => e.at && DAY.format(new Date(e.at)) === today)
    .sort((a, b) => String(a.at).localeCompare(String(b.at)))
    .filter((e) => !seen.has(e.title) && seen.add(e.title));
  lines.push(evToday.length
    ? `Tests and events today (${evToday.length}): ` + evToday.map((e) => `${e.title} at ${HM.format(new Date(e.at!))}${todayNote(e.at, now)}`).join("; ")
    : "Tests and events today: none");
  const open = roles.filter((r) => r.effective_deadline && new Date(r.effective_deadline) > now);
  const group = (rs: Role[], key: (r: Role) => string) => {
    const m = new Map<string, Role[]>();
    for (const r of rs) m.set(key(r), [...(m.get(key(r)) || []), r]);
    return [...m.entries()].sort((a, b) => String(a[1][0].effective_deadline).localeCompare(String(b[1][0].effective_deadline)));
  };
  const n = (k: number, one: string, many: string) => `${k} ${k === 1 ? one : many}`;
  const count = (rs: Role[]) => {
    const no = rs.filter((r) => !r.applied).length;
    const mine = rs.filter((r) => r.for_you).length;
    return `${n(rs.length, "role", "roles")} at ${n(new Set(rs.map((r) => r.company)).size, "company", "companies")} (${no} not applied, ${rs.length - no} applied` +
      `${rs.some((r) => r.for_you !== undefined) ? `; ${mine} for you` : ""})`;
  };
  const todayRoles = open.filter((r) => DAY.format(new Date(r.effective_deadline!)) === today);
  lines.push(todayRoles.length
    ? "Application deadlines still open today: " + group(todayRoles, (r) => HM.format(new Date(r.effective_deadline!)))
        .map(([hm, rs]) => `${count(rs)} close at ${hm}${todayNote(rs[0].effective_deadline, now)}`).join("; ")
    : "Application deadlines still open today: none");
  const week = open.filter((r) => new Date(r.effective_deadline!).getTime() <= endOfWeek(now));
  lines.push(`Application deadlines from now to the end of this week (Sunday; today counts as this week): ` + (week.length
    ? group(week, (r) => DAY.format(new Date(r.effective_deadline!)))
        .map(([, rs]) => `${WD.format(new Date(rs[0].effective_deadline!))}: ${count(rs)}`).join("; ")
    : "none"));
  return lines.join("\n");
}

// 4. Ready-made role lists, one per closing time, so every answer lists roles the same way: the deadline once in the
// heading, "For you" first (not applied, then "✓ applied"), then "Others" one "Company — Role" line each.
// No reasons (those are in the feed).
type ListRole = { id: string; company: string; designation: string; applied: boolean | null;
                  effective_deadline: string | null | undefined; eligible: boolean | null };

export function dayWord(at: Date, now: Date): string {
  const d = DAY.format(at), n = DAY.format(now), tm = DAY.format(new Date(now.getTime() + 86_400_000));
  const hour = Number(HM.format(at).slice(0, 2));
  if (d === n) return hour >= 17 ? "tonight" : "today";
  if (d === tm) return "tomorrow";
  return WD.format(at);
}

export function roleLists(roles: ListRole[], marks: Map<string, { relevant: boolean }>, now: Date,
                          hasTargets: boolean, listOthers: boolean, days = 7): string {
  const until = now.getTime() + days * 86_400_000;
  const open = roles.filter((r) => r.eligible !== false && r.effective_deadline &&
    new Date(r.effective_deadline).getTime() > now.getTime() && new Date(r.effective_deadline).getTime() <= until);
  const byTime = new Map<string, ListRole[]>();
  for (const r of open) byTime.set(r.effective_deadline!, [...(byTime.get(r.effective_deadline!) || []), r]);
  const line = (r: ListRole) => `- ${r.company} — ${r.designation}${r.applied ? " ✓ applied" : ""}`;
  const order = (rs: ListRole[]) => [...rs].sort((a, b) => Number(!!a.applied) - Number(!!b.applied) ||
    a.company.localeCompare(b.company) || a.designation.localeCompare(b.designation));
  const blocks: string[] = [];
  for (const [iso, rs] of [...byTime.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    const at = new Date(iso);
    const when = `Close ${dayWord(at, now)} ${HM.format(at)}${todayNote(iso, now).replace(" (later today, in ", " (in ")}`;
    const mine = hasTargets ? rs.filter((r) => marks.get(r.id)?.relevant === true) : rs;
    const others = hasTargets ? rs.filter((r) => marks.get(r.id)?.relevant !== true) : [];
    const applied = mine.filter((r) => r.applied).length;
    const head = hasTargets ? `${when} — ${mine.length} for you, ${applied} applied:` : `${when} — ${rs.length} roles, ${applied} applied:`;
    const body = hasTargets
      ? ["For you:", ...(mine.length ? order(mine).map(line) : ["- none"]),
         ...(others.length ? (listOthers ? ["Others:", ...order(others).map(line)] : [`Others: ${others.length} more (not listed)`]) : [])]
      : order(rs).map(line);
    blocks.push([head, ...body].join("\n"));
  }
  return blocks.join("\n\n");
}
