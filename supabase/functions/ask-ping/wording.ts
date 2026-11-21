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
