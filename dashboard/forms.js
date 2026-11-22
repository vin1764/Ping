// The Forms tab's logic, pure (no page): sections, filters, the tab's badge, what Today counts, and Ask Ping's form
// questions. The forms come from the hourly run (ping/forms.py); a tick is the student's own record in form_status.
// Node tests: tests/js/forms.test.js.
(function (root) {
  const T = typeof module !== "undefined" && module.exports ? require("./today.js") : root.PingToday;
  const ms = (v) => (v ? new Date(v).getTime() : NaN);
  const DAY = 86400000;
  const isFilled = (status, key) => !!(status && status.get(key)?.filled);
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

  // Due today · Upcoming · Past due (not filled) · Closed (the form page says so) · Filled. query: words in company / purpose / title; only: "foryou" |
  // null; at: one deadline (Today's "7 forms due 20:00" opens the list at that time)
  function sections(forms, status, { now, query = "", only = null, mineOf = () => true, at = null } = {}) {
    const q = String(query || "").trim().toLowerCase();
    const day = T.dayOf(now);
    const out = { today: [], upcoming: [], past: [], closed: [], filled: [] };
    for (const f of forms || []) {
      if (q && ![...names(f), f.purpose, f.title].join(" ").toLowerCase().includes(q)) continue;
      if (only === "foryou" && !mineOf(f)) continue;
      if (at != null && ms(f.due_at) !== at) continue;
      const t = ms(f.due_at);
      if (isFilled(status, f.key)) out.filled.push(f);
      else if (f.closed) out.closed.push(f);
      else if (t > 0 && t <= now) out.past.push(f);
      else if (t > 0 && T.dayOf(t) === day) out.today.push(f);
      else out.upcoming.push(f);
    }
    const byDue = (a, b) => (ms(a.due_at) || 9e15) - (ms(b.due_at) || 9e15) || String(a.company).localeCompare(String(b.company));
    out.today.sort(byDue); out.upcoming.sort(byDue);
    out.past.sort((a, b) => byDue(b, a));
    out.filled.sort((a, b) => (ms(status.get(b.key)?.filled_at) || 0) - (ms(status.get(a.key)?.filled_at) || 0));
    return out;
  }

  // the tab's badge: forms not filled, still open, due in the next 24 h
  const badge = (forms, status, now) => (forms || []).filter((f) => !isFilled(status, f.key) && !f.closed
    && ms(f.due_at) > now && ms(f.due_at) - now <= DAY).length;

  // "posted 3 times: notice 1791, mail, notice 1796"
  function postedLine(f) {
    const s = f.sources || [];
    if (s.length < 2) return "";
    return `posted ${s.length} times: ${s.map((x) => (x.type === "notice" ? `notice ${x.id}` : x.type)).join(", ")}`;
  }
  // "deadline moved Sat 21 Nov 20:00 → Sun 22 Nov 20:00"
  function movedLine(f, when) {
    const h = f.deadline_history || [];
    if (!h.length) return "";
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
      const todo = (forms || []).filter((f) => !isFilled(status, f.key) && open(f)).sort((a, b) => (ms(a.due_at) || 9e15) - (ms(b.due_at) || 9e15));
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

  const api = { sections, badge, postedLine, movedLine, ask, label, isFilled, filledCount, names, cleanName, shortList };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingForms = api;
})(typeof window !== "undefined" ? window : globalThis);
