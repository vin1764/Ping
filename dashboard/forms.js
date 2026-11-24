// The Forms tab's logic, pure (no page): sections, filters, the tab's badge, what Today counts, and Ask Ping's form
// questions. The forms come from the hourly run (ping/forms.py); a tick is the student's own record in form_status.
// Node tests: tests/js/forms.test.js.
(function (root) {
  const T = typeof module !== "undefined" && module.exports ? require("./today.js") : root.PingToday;
  const ms = (v) => (v ? new Date(v).getTime() : NaN);
  const DAY = 86400000;
  const isFilled = (status, key) => !!(status && status.get(key)?.filled);

  // ---- "Not for me": your own record (form_status.not_for_me), never anything on the ERP and never the company's
  // roles. A form (its key), a Today item that has no form ("item:<id>"), or a kind you said yes to in the chat
  // ("kind:company:<name>", "kind:role:<type>"). "asked:<kind>:<value>" remembers that Ping asked once.
  const REASONS = ["Wrong role", "Not interested in company", "Not eligible"];
  // role types, by the words a designation uses (the same list as ping/forms.py ROLE_TYPES)
  const ROLE_TYPES = [["product manager", /\bproduct\s+(manager|management)\b|\bapm\b/], ["product analyst", /\bproduct\s+analyst\b/],
    ["data scientist", /\bdata\s+scien/], ["data analyst", /\bdata\s+analyst\b/], ["business analyst", /\bbusiness\s+analyst\b/],
    ["management trainee", /\bmanagement\s+trainee\b|\bmt\b/], ["consultant", /\bconsult/], ["software engineer", /\b(software|sde|developer|full\s*stack|backend|frontend)\b/],
    ["quant", /\bquant/], ["research", /\bresearch/], ["sales", /\bsales\b/], ["marketing", /\bmarketing\b/], ["finance", /\bfinanc|\binvestment\b|\bbanking\b/],
    ["operations", /\boperations?\b/], ["design", /\bdesign(er)?\b/], ["analyst", /\banalyst\b/], ["engineer", /\bengineer/]];
  const roleType = (designation) => { const d = String(designation || "").toLowerCase(); return (ROLE_TYPES.find(([, re]) => re.test(d)) || [null])[0]; };
  // the same as ping/posting.py _norm: "Diageo India Pvt. Ltd." -> "diageo"
  const coKey = (n) => String(n || "").toLowerCase().replace(/\(.*?\)/g, " ").replace(/\b(private|pvt|limited|ltd|llp|inc|india)\b\.?/g, " ").replace(/[^a-z0-9]+/g, "");
  const kindKey = (kind, value) => `kind:${kind}:${kind === "company" ? coKey(value) : String(value).toLowerCase()}`;
  const flagged = (status, key) => !!(status && key && status.get(key)?.not_for_me);
  // why a form is out of your lists: "you" (this form), "company" / "role" (a kind you said yes to), or null
  function notForMe(status, f, roleNames = []) {
    if (!f) return null;
    if (flagged(status, f.key)) return "you";
    if (names(f).some((n) => flagged(status, kindKey("company", n)))) return "company";
    const types = [...roleNames, f.title].map(roleType).filter(Boolean);
    if (types.some((t) => flagged(status, kindKey("role", t)))) return "role";
    return null;
  }
  // after a dismissal: two or more forms you dismissed yourself from one company, or of one role type, and Ping hasn't
  // asked about it -> { kind, value, label, n } (asked once; saved only when you say yes)
  function askAbout(status, forms, rolesOf = () => []) {
    const mine = (forms || []).filter((f) => flagged(status, f.key));
    const count = new Map();
    const add = (kind, value, label) => { const k = kindKey(kind, value); const c = count.get(k) || { kind, value, label, n: 0 }; c.n++; count.set(k, c); };
    for (const f of mine) {
      for (const n of new Set(names(f).map(cleanName))) add("company", n, `${n} forms`);
      for (const t of new Set([...rolesOf(f), f.title].map(roleType).filter(Boolean))) add("role", t, `${t} forms`);
    }
    for (const [k, c] of count) {
      const asked = status && status.has(`asked:${k.slice(5)}`);
      if (c.n >= 2 && !asked && !flagged(status, k)) return c;
    }
    return null;
  }
  const label = (purpose) => (!purpose || purpose === "form" ? "Form" : purpose[0].toUpperCase() + purpose.slice(1));
  const names = (f) => (f.companies && f.companies.length > 1 ? f.companies : [f.company]).filter(Boolean);
  // a company as people say it: no bracketed website, no "Private Limited", and a shouted multi-word name in title
  // case with its short acronyms kept ("GOLDMAN SACHS" -> "Goldman Sachs", "TATA AIG" -> "Tata AIG"); one-word names
  // stay as written (AIRAMATRIX)
  function cleanName(n) {
    let s = String(n || "").replace(/\s*\(([^()]*)\)/g, (m, inner) => (/https?:|www\.|\.(com|in|io|ai|co)\b/i.test(inner) ? "" : m));
    for (let i = 0; i < 2; i++) s = s.replace(/[\s,]+(private\s+limited|pvt\.?\s*ltd\.?|limited|ltd\.?|inc\.?|llp|corporation|corp\.?)\s*$/i, "");
    s = s.replace(/\s{2,}/g, " ").trim();
    const words = s.split(" ");
    if (words.length > 1 && s === s.toUpperCase() && /[A-Z]{4,}/.test(s))
      s = words.map((w) => (w.length <= 3 || /\d/.test(w) ? w : w[0] + w.slice(1).toLowerCase())).join(" ");
    return s || String(n || "");
  }
  // "Piramal, Auro Group, SLB +8 more"
  function shortList(f, n = 3) {
    const all = names(f).map(cleanName);
    return all.length <= n + 1 ? all.join(", ") : `${all.slice(0, n).join(", ")} +${all.length - n} more`;
  }

  // open (Due today + Upcoming, one list by deadline) · Past due (not filled) · Closed (the form page says so) · Filled ·
  // Not for me. query: words in company / purpose / title; only: "foryou" |
  // null; at: one deadline (Today's "7 forms due 20:00" opens the list at that time)
  function sections(forms, status, { now, query = "", only = null, mineOf = () => true, at = null, rolesOf = () => [] } = {}) {
    const q = String(query || "").trim().toLowerCase();
    const day = T.dayOf(now);
    const out = { open: [], today: [], upcoming: [], past: [], closed: [], filled: [], notForMe: [] };
    for (const f of forms || []) {
      if (q && ![...names(f), f.purpose, f.title].join(" ").toLowerCase().includes(q)) continue;
      if (at != null && ms(f.due_at) !== at) continue;
      const t = ms(f.due_at);
      // not for you: only in the "Not for me" section, whatever the filter (you look for them there to restore)
      if (notForMe(status, f, rolesOf(f))) { out.notForMe.push(f); continue; }
      if (only === "foryou" && !mineOf(f)) continue;
      if (isFilled(status, f.key)) out.filled.push(f);
      else if (f.closed) out.closed.push(f);
      else if (t > 0 && t <= now) out.past.push(f);
      else if (t > 0 && T.dayOf(t) === day) out.today.push(f);
      else out.upcoming.push(f);
    }
    const byDue = (a, b) => (ms(a.due_at) || 9e15) - (ms(b.due_at) || 9e15) || String(a.company).localeCompare(String(b.company));
    out.today.sort(byDue); out.upcoming.sort(byDue);
    // the Forms tab: one list of open forms by deadline (the card's date line says "Today 20:00" / "Fri 27 Nov"),
    // the ones with no deadline given last
    out.open = [...out.today, ...out.upcoming].sort(byDue);
    out.past.sort((a, b) => byDue(b, a));
    out.filled.sort((a, b) => (ms(status.get(b.key)?.filled_at) || 0) - (ms(status.get(a.key)?.filled_at) || 0));
    out.notForMe.sort((a, b) => (ms(status.get(b.key)?.not_for_me_at) || 0) - (ms(status.get(a.key)?.not_for_me_at) || 0) || byDue(a, b));
    return out;
  }

  // the tab's badge: forms not filled, still open, due in the next 24 h
  const badge = (forms, status, now, rolesOf = () => []) => (forms || []).filter((f) => !isFilled(status, f.key) && !f.closed
    && !notForMe(status, f, rolesOf(f)) && ms(f.due_at) > now && ms(f.due_at) - now <= DAY).length;

  // "posted 3 times: notice 1791, mail, notice 1796"
  function postedLine(f) {
    const s = f.sources || [];
    if (s.length < 2) return "";
    const one = (x) => (x.type === "notice" ? `notice ${x.id}` : x.type);
    const shown = s.length > 3 ? [...s.slice(0, 2).map(one), `+${s.length - 2} more`] : s.map(one);
    return `posted ${s.length} times: ${shown.join(", ")}`;
  }
  // "deadline moved Sat 21 Nov 20:00 → Sun 22 Nov 20:00"
  function movedLine(f, when) {
    const h = f.deadline_history || [];
    if (!h.length) return "";
    if (h.length > 2) return `deadline moved ${h.length} times, last ${when(h[h.length - 1].from)} → ${when(h[h.length - 1].to)}`;
    return `deadline moved ${[h[0].from, ...h.map((x) => x.to)].map((v) => when(v)).join(" → ")}`;
  }

  // ---------------------------------------------------------------- Ask Ping
  const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  function formsOf(question, forms) {
    const q = ` ${norm(question)} `;
    const hits = (forms || []).filter((f) => names(f).some((n) => {
      const words = norm(n).split(" ").filter((w) => w.length > 2 && !["private", "limited", "pvt", "ltd", "india", "the"].includes(w));
      return words.length && q.includes(` ${words[0]} `);
    }));
    return hits;
  }
  // { text, tick?: form key } or null when it isn't a question about forms
  function ask(question, forms, status, { now, when }) {
    const q = norm(question);
    if (!/\bforms?\b/.test(q)) return null;
    const open = (f) => !f.closed && !(ms(f.due_at) <= now);
    const line = (f) => `${shortList(f)}: ${label(f.purpose).toLowerCase()}${f.due_at ? `, due ${when(f.due_at)}` : ""}`;
    // "mark the Piramal form as filled" / "tick the Groww form"
    if (/\b(mark|tick|check)\b/.test(q) && /\b(filled|done|submitted|complete[d]?)\b|\btick\b/.test(q)) {
      const hits = formsOf(question, forms);
      if (!hits.length) return { text: "Which form? Say the company, for example: “mark the Groww form as filled”." };
      const f = hits.find((x) => !isFilled(status, x.key)) || hits[0];
      if (isFilled(status, f.key)) return { text: `The ${shortList(f)} form is already ticked as filled.` };
      return { text: `Done: the ${shortList(f)} ${label(f.purpose).toLowerCase()} is ticked as filled. (Your own record; Ping doesn't fill forms.)`, tick: f.key };
    }
    // "did I fill the Groww form?"
    if (/\bdid i\b|\bhave i\b|\bis the\b.*\bfilled\b/.test(q) && formsOf(question, forms).length) {
      const f = formsOf(question, forms)[0];
      if (isFilled(status, f.key)) return { text: `Yes: you ticked the ${shortList(f)} ${label(f.purpose).toLowerCase()} as filled${status.get(f.key)?.filled_at ? ` (${when(status.get(f.key).filled_at)})` : ""}.` };
      return { text: `Not ticked yet: the ${shortList(f)} ${label(f.purpose).toLowerCase()}${f.due_at ? ` is due ${when(f.due_at)}` : ""}${f.closed ? " (the form says it's closed)" : ""}. Tick it in Forms once you've filled it.` };
    }
    // "which forms haven't I filled?"
    if (/\b(not|haven t|havent|yet|left|pending|unfilled|still|remaining|to fill|due)\b/.test(q)) {
      const todo = (forms || []).filter((f) => !isFilled(status, f.key) && !notForMe(status, f) && open(f)).sort((a, b) => (ms(a.due_at) || 9e15) - (ms(b.due_at) || 9e15));
      if (!todo.length) return { text: "Nothing left: every open form is ticked as filled." };
      const shown = todo.slice(0, 8).map((f) => `- ${line(f)}`);
      return { text: `${todo.length} form${todo.length === 1 ? "" : "s"} not ticked yet:\n${shown.join("\n")}${todo.length > 8 ? `\n+${todo.length - 8} more in Forms` : ""}` };
    }
    return null;
  }

  // what Today's form rows say: "7 forms due 20:00 · 3 filled"
  function filledCount(items, status) {
    return (items || []).filter((it) => isFilled(status, it?.details?.form?.key)).length;
  }

  const api = { sections, badge, postedLine, movedLine, ask, label, isFilled, filledCount, names, cleanName, shortList,
                notForMe, askAbout, roleType, kindKey, REASONS, ROLE_TYPES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingForms = api;
})(typeof window !== "undefined" ? window : globalThis);
