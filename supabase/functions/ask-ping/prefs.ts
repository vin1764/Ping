// Preferences said in the chat ("only show me product and consulting roles", "also include data scientist roles",
// "don't count SDE as relevant", "remind me 3 hours before deadlines", "stop listing other roles separately",
// "what are my preferences?", "reset my preferences"). Decided here with fixed patterns, not by the model, so a
// question that merely mentions roles ("any product roles tonight?") never changes anything. Tested in
// prefs_test.ts.

export type Prefs = { targets: string | null; reminder_hours: number | null; list_other_roles: boolean | null };
export type Parsed = { kind: "none" | "set" | "show" | "reset"; changes: Partial<Prefs>; rest: string };

const clean = (s: string) => s.replace(/\s+/g, " ").trim();
const item = (s: string) => clean(s).replace(/^(?:the|any|all)\s+/i, "").replace(/[.!?,;:]+$/, "")
  .replace(/\s+(?:too|as well|also|please|as relevant|for me)$/i, "").replace(/[.!?,;:]+$/, "").trim();

const SHOW = /^(?:what\s+(?:are|is)\s+my\s+(?:preferences|targets|settings)|show\s+(?:me\s+)?my\s+(?:preferences|targets|settings)|what\s+am\s+i\s+looking\s+for)\b/i;
const RESET = /^(?:please\s+)?(?:reset|clear|forget|delete)\s+(?:all\s+)?my\s+(?:preferences|targets|settings)\b/i;
const REMIND = /\bremind\s+me\s+(\d+(?:\.\d+)?)\s*(h|hrs?|hours?|m|mins?|minutes?)\s+before\b/i;
const LIST_OFF = /\b(?:stop|don'?t|do\s+not|no\s+longer)\s+(?:list(?:ing)?|show(?:ing)?)\s+(?:the\s+)?other\s+roles\b/i;
const LIST_ON = /^(?:please\s+)?(?:start\s+|keep\s+)?(?:list|show)(?:ing)?\s+(?:the\s+)?other\s+roles\s+(?:separately|again|too)\b/i;
const SET = /^(?:please\s+)?(?:only\s+show\s+me|show\s+me\s+only|just\s+show\s+me|i(?:'m|\s+am)\s+(?:only\s+)?(?:looking\s+for|interested\s+in)|i\s+only\s+want|my\s+targets?\s+(?:is|are))\s+(.+)$/i;
const ADD = /^(?:please\s+)?(?:also\s+(?:include|show(?:\s+me)?|add|count)|include|add)\s+(.+)$/i;
const EXCLUDE = /^(?:please\s+)?(?:(?:don'?t|do\s+not|stop)\s+(?:count(?:ing)?|show(?:ing)?(?:\s+me)?|include|including|list(?:ing)?)|exclude|remove|drop|not\s+interested\s+in|no\s+more)\s+(.+)$/i;

// one sentence -> a change, or null when it isn't a preference
function one(s: string, cur: Prefs): { kind: Parsed["kind"]; changes: Partial<Prefs> } | null {
  const t = clean(s);
  if (!t) return null;
  if (RESET.test(t)) return { kind: "reset", changes: { targets: null, reminder_hours: 2, list_other_roles: true } };
  if (SHOW.test(t)) return { kind: "show", changes: {} };
  const rm = t.match(REMIND);
  if (rm) {
    const n = Number(rm[1]);
    return { kind: "set", changes: { reminder_hours: /^m/i.test(rm[2]) ? Math.round((n / 60) * 100) / 100 : n } };
  }
  if (LIST_OFF.test(t)) return { kind: "set", changes: { list_other_roles: false } };
  if (LIST_ON.test(t)) return { kind: "set", changes: { list_other_roles: true } };
  if (t.endsWith("?")) return null;                       // other questions are questions, never preferences
  const set = t.match(SET);
  if (set && item(set[1])) return { kind: "set", changes: { targets: item(set[1]) } };
  const add = t.match(ADD);
  if (add && item(add[1])) return { kind: "set", changes: { targets: merge(cur.targets, item(add[1]), "also") } };
  const ex = t.match(EXCLUDE);
  if (ex && item(ex[1]) && !/^other roles\b/i.test(item(ex[1]))) {
    return { kind: "set", changes: { targets: merge(cur.targets, item(ex[1]), "not") } };
  }
  return null;
}

// "also X" appends (and drops an earlier "not X"); "not X" adds an exclusion (and drops an earlier "also X").
export function merge(targets: string | null, what: string, how: "also" | "not"): string {
  const parts = clean(targets || "").split(/\s*;\s*/).filter(Boolean);
  const key = (p: string) => p.replace(/^(?:also|not)\s+/i, "").toLowerCase();
  const kept = parts.filter((p) => key(p) !== what.toLowerCase());
  if (!kept.length && how === "also") return what;
  kept.push(`${how} ${what}`);
  return kept.join("; ");
}

export function parsePrefs(message: string, cur: Prefs): Parsed {
  // sentences; "only show me X. what's due tonight?" is a preference and a question
  const parts = message.split(/(?<=[.!?])\s+|\n+/).map(clean).filter(Boolean);
  let kind: Parsed["kind"] = "none";
  let state: Prefs = { ...cur };
  const changes: Partial<Prefs> = {};
  const rest: string[] = [];
  for (const p of parts) {
    const r = one(p, state);
    if (!r) { rest.push(p); continue; }
    if (r.kind === "reset") { kind = "reset"; Object.assign(changes, r.changes); state = { ...state, ...r.changes }; continue; }
    if (r.kind === "show") { if (kind === "none") kind = "show"; continue; }
    kind = kind === "reset" ? "reset" : "set";
    Object.assign(changes, r.changes);
    state = { ...state, ...r.changes };
  }
  return { kind, changes, rest: rest.join(" ") };
}

export function describe(p: Prefs, changed?: Partial<Prefs>): string {
  const bits: string[] = [];
  const show = (k: keyof Prefs) => !changed || k in changed;
  if (show("targets")) bits.push(`targets = ${p.targets ? `"${p.targets}"` : "(none: every role is listed the same way)"}`);
  if (show("reminder_hours")) bits.push(`reminders ${p.reminder_hours ?? 2} h before`);
  if (show("list_other_roles")) bits.push(`other roles listed separately: ${p.list_other_roles === false ? "off" : "on"}`);
  return bits.join("; ");
}
