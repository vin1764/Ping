/* Answers from the ERP data without the AI: used when Gemini is busy or down (the ask-ping function), when the
 * function can't be reached at all (the dashboard), and in the offline ?demo=1 copy. One file for both, loaded as a
 * plain script (window.PingRules) by the page and imported by the function (globalThis.PingRules).
 *
 * It answers what was asked:
 *   - a company in the question (fuzzy: typos, "msft" -> Microsoft, "HUL" -> Hindustan Unilever): ONLY that company,
 *     its open deadlines (one line per deadline: "form + CV submission by ..."), its latest notice and your status;
 *   - a company Ping has no data on: says so;
 *   - no company but a clear intent (deadlines, tests, shortlists): that list, for the time asked about;
 *   - neither: says it couldn't tell, then what's due soon.
 * Never a count without names. Tested in tests/js/answer_rules.test.js.
 *
 * data = { now: Date, lastChecked: iso | null,
 *          roles:   [{ id, company, designation, applied, deadline, eligible, ctc, currency, cv }],
 *          items:   [{ id, company, category, title, due_at, event_at, level, pdf_status, role_ids, hidden_because, subject }],
 *          notices: [{ company, subject, notice_time }] }
 */
(function (root) {
  "use strict";
  const TZ = "Asia/Kolkata";
  const FMT = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const DAYKEY = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });
  const DAYNAME = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" });
  const when = (iso) => FMT.format(new Date(iso)).replace(/,/g, "");
  const dayKey = (d) => DAYKEY.format(new Date(d));
  const dayName = (d) => DAYNAME.format(new Date(d)).replace(/,/g, "");   // Deno writes "Sun, 22 Nov", Node "Sun 22 Nov"

  // ---------------------------------------------------------------- names
  const URLISH = /https?:\/\/|www\.|\b[a-z0-9-]+\.(?:com|in|io|ai|co|org|net|tech|app|dev)\b/i;
  const SUFFIX = /[\s,]+(?:private\s+limited|pvt\.?\s*ltd\.?|limited|ltd\.?|inc\.?|llp|llc|corporation|corp\.?|plc)\s*$/i;
  // display name: no bracketed website, no "Private Limited" / "Corporation" at the end, ALL CAPS made readable
  function shortName(name) {
    let s = String(name || "").replace(/\s*\(([^()]*)\)/g, (m, inner) => (URLISH.test(inner) ? "" : m));
    for (let i = 0; i < 2; i++) s = s.replace(SUFFIX, "");
    s = s.replace(/\s{2,}/g, " ").trim() || String(name || "").trim();
    if (s === s.toUpperCase() && /[A-Z]{4,}/.test(s)) s = s.toLowerCase().replace(/\b[a-z]/g, (c) => c.toUpperCase());
    return s;
  }
  const LEGAL = new Set(("private pvt limited ltd inc llp llc plc the and of co company corp corporation technologies technology " +
    "services solutions group global labs systems software india").split(" "));
  const norm = (s) => String(s || "").toLowerCase().replace(/\s*\(([^()]*)\)/g, (m, inner) => (URLISH.test(inner) ? " " : m))
    .replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();
  const keyWords = (name) => norm(name).split(" ").filter((w) => w && !LEGAL.has(w));

  // cheap aliases: a word in the question -> words that must appear in the company's name
  const ALIASES = { ms: ["microsoft", "morgan stanley"], msft: ["microsoft"], goog: ["google"], amzn: ["amazon"],
    jpm: ["jp morgan", "jpmorgan", "morganchase", "morgan chase"], jpmc: ["jp morgan", "jpmorgan", "morganchase", "morgan chase"],
    gs: ["goldman"], pw: ["physicswallah", "physics wallah"], db: ["deutsche"], bofa: ["bank of america"], amex: ["american express"],
    hul: ["hindustan unilever"], pg: ["procter"], bcg: ["boston consulting"], tcs: ["tata consultancy"], ge: ["general electric"],
    deshaw: ["shaw"], qrt: ["qube"], ib: ["intelligent business"] };

  // words that are never a company: question words, intents, times, role words
  const STOP = new Set(("a an the and or but for of to in on at by from with about into is are was were be been am do does did " +
    "have has had i me my mine we you your it its this that these those there here what whats which who whom whose when where why how " +
    "hows can could would should will shall may might must please pls kindly tell show give list find get got need want know check see " +
    "any anything something everything nothing all some new open still next upcoming soon latest last first recent status update " +
    "updates info information detail details about regarding re role roles job jobs company companies firm placement placements " +
    "intern internship internships erp ping ok okay thanks thank hi hello hey yes no not just only also more else other others much " +
    "many im ive id isnt dont doesnt didnt cant there theres now right like same again pending remaining left mean meaning " +
    "deadline deadlines due date dates close closes closed closing submit submitted submission submissions form forms apply applied " +
    "applying application applications register registration cv cvs resume resumes test tests exam exams assessment oa room rooms " +
    "venue slot slots interview interviews ppt shortlist shortlisted shortlists result results selected list lists ctc pay salary " +
    "package stipend lpa compensation bond eligible eligibility eligibile time timing schedule today tonight tomorrow week weekend " +
    "month day days hour hours morning evening night monday tuesday wednesday thursday friday saturday sunday mon tue wed thu fri sat sun " +
    "analyst engineer engineering developer manager management product associate data software sde intern trainee consultant " +
    "consulting finance financial quant research researcher scientist design designer marketing sales operations ops strategy " +
    "business hr core full stack frontend backend senior junior lead program programme officer executive role " +
    "use using used help look looking try go going make take put say think best good better fine sure wait start end let lets " +
    "share send link links portal website site mail email notification notifications message messages question answer").split(" "));

  function editClose(a, b) {
    if (Math.abs(a.length - b.length) > 2 || Math.min(a.length, b.length) < 5) return false;
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
    return d[a.length][b.length] <= (Math.max(a.length, b.length) >= 8 ? 2 : 1);
  }

  // every company Ping knows: from the companies list, plus companies that only appear in notices
  const SCHEDULE = /placement schedule|^cdc\b|all students/i;
  function entities(data) {
    const ents = [];
    const byKey = new Map();
    const add = (raw, fromRole) => {
      const kw = keyWords(raw);
      const key = kw.join(" ") || norm(raw);
      if (!key) return;
      let e = byKey.get(key);
      if (!e && !fromRole) {
        // "MICROSOFT" (a notice) belongs to "Microsoft Corporation" (the companies list)
        e = ents.find((x) => x.key.startsWith(key + " ") || key.startsWith(x.key + " "));
      }
      if (!e) {
        e = { key, words: kw.length ? kw : norm(raw).split(" "), name: shortName(raw), raw: new Set(), roles: fromRole };
        ents.push(e);
        byKey.set(key, e);
      }
      e.raw.add(raw);
      if (fromRole && !e.roles) { e.roles = true; e.name = shortName(raw); }
    };
    for (const r of data.roles || []) if (r.company) add(r.company, true);
    for (const n of data.notices || []) if (n.company && !SCHEDULE.test(n.company)) add(n.company, false);
    for (const i of data.items || []) if (i.company && !SCHEDULE.test(i.company)) add(i.company, false);
    return ents;
  }

  function tokensOf(question) { return norm(question).replace(/\b(\w+) s\b/g, "$1").split(" ").filter(Boolean); }

  // the companies a question is about
  function matchCompanies(question, data, ents) {
    ents = ents || entities(data);
    const toks = tokensOf(question);
    const q = ` ${toks.join(" ")} `;
    const joined = toks.join("");
    const hits = [];
    const used = new Set();
    // pass 1: whole names ("ather energy"); their words are taken, so "energy" can't also pick "Energy Aspects"
    for (const e of ents) {
      const whole = (e.key.length >= 3 && q.includes(` ${e.key} `)) ||
        (e.key.includes(" ") && e.key.length >= 6 && joined.includes(e.key.replace(/ /g, "")));
      if (whole) { hits.push(e); e.key.split(" ").forEach((x) => used.add(x)); }
    }
    // pass 2: one distinctive word, a typo of it, a prefix, initials or an alias
    for (const e of ents) {
      if (hits.includes(e)) continue;
      const w0 = e.words.find((w) => w.length >= 3) || e.words[0];
      const initials = e.words.map((w) => w[0]).join("");
      let hit = null;
      for (const t of toks) {
        if (used.has(t) || STOP.has(t) || /^\d+$/.test(t)) continue;
        if ((t === w0 && t.length >= 2) || (t.length >= 5 && w0.length > t.length && w0.startsWith(t)) || editClose(t, w0) ||
            (t.length >= 3 && e.words.length >= 3 && t === initials)) { hit = t; break; }
        const want = ALIASES[t];
        if (want && want.some((w) => e.key.includes(w) || e.key.replace(/ /g, "").includes(w.replace(/ /g, "")))) { hit = t; break; }
      }
      if (hit) { hits.push(e); hit.split(" ").forEach((x) => used.add(x)); }
    }
    return { hits, used };
  }

  // ---------------------------------------------------------------- intent
  function intentsOf(question) {
    const q = norm(question);
    const has = (re) => re.test(q);
    const out = new Set();
    if (has(/\b(which|what|best)\s+(cv|resume)\b|\bapply\s+with\b|\bcv\s+(for|to use)\b/)) out.add("whichcv");
    if (has(/\b(deadlines?|due|last date|closes?|closing|closed|submit\w*|submissions?|forms?|apply by|register\w*|registration)\b/) ||
        (has(/\b(cv|resume)\b/) && !out.has("whichcv"))) out.add("deadline");
    if (has(/\bshort ?list\w*|\bselected\b|\bresults?\b/)) out.add("shortlist");
    if (has(/\b(tests?|exams?|assessments?|oa|rooms?|venue|slots?|interviews?|ppt|dates?)\b/) && !has(/\blast date\b/)) out.add("test");
    if (has(/\b(ctc|pay|salary|package|stipend|lpa|compensation|bond)\b/)) out.add("pay");
    if (has(/\beligib\w*/)) out.add("eligible");
    if (has(/\b(did i apply|have i applied|applied)\b/)) out.add("applied");
    if (has(/\bwhen\b/) && !out.size) out.add("deadline").add("test");
    return out;
  }
  function timeRange(question, now) {
    const q = norm(question);
    const start = new Date(`${dayKey(now)}T00:00:00+05:30`).getTime();
    if (/\btomorrow\b/.test(q)) return { from: start + 86400000, to: start + 2 * 86400000, label: `tomorrow (${dayName(start + 86400000)})` };
    if (/\b(today|tonight)\b/.test(q)) return { from: now.getTime(), dayStart: start, to: start + 86400000, label: `today (${dayName(now)})` };
    if (/\bnext week\b/.test(q)) return { from: start + 7 * 86400000 - ((new Date(start).getUTCDay() + 6) % 7) * 0, to: start + 14 * 86400000, label: "in the next two weeks" };
    if (/\b(this week|week)\b/.test(q)) return { from: now.getTime(), to: now.getTime() + 7 * 86400000, label: "in the next 7 days" };
    return null;
  }

  // ---------------------------------------------------------------- deadlines, merged per company and time
  const PAST = /deadline gone|already happened|updated by a later|older than/;
  function kindOf(i) {
    const t = `${i.subject || ""} ${i.title || ""}`.toLowerCase();
    if (/\b(cv|resume)\b/.test(t)) return "CV submission";
    if (/\bform\b|google form|registration|register/.test(t)) return "form";
    if (/submi/.test(t)) return "submission";
    if (/test|assessment/.test(t)) return "test registration";
    return "application";        // a deadline extension or reminder is about the application itself
  }
  const ORDER = ["form", "CV submission", "submission", "test registration", "application", "deadline"];
  function deadlineEntries(data, ents, from, to) {
    const now = data.now.getTime();
    from = from ?? now; to = to ?? Infinity;
    const roleById = new Map((data.roles || []).map((r) => [r.id, r]));
    const entOf = (company) => ents.find((e) => e.raw.has(company));
    const out = [];
    for (const r of data.roles || []) {
      const at = r.deadline && new Date(r.deadline).getTime();
      if (!at || at <= now || at < from || at >= to || r.eligible === false) continue;
      out.push({ ent: entOf(r.company), at, kind: "application", roles: [r.designation], applied: !!r.applied, fromRole: true });
    }
    for (const i of data.items || []) {
      const at = i.due_at && new Date(i.due_at).getTime();
      if (!at || at <= now || at < from || at >= to || !i.company) continue;
      if (!["todo", "form", "deadline"].includes(i.category) || PAST.test(i.hidden_because || "")) continue;
      // hidden with no reason = not about you (e.g. a submission for a shortlist you're not on); hidden because a
      // digest or list message carries it = still yours
      if (i.level === "hidden" && !/digest|message|collapse|merged/.test(i.hidden_because || "")) continue;
      const roles = (i.role_ids || []).map((id) => roleById.get(id)?.designation).filter(Boolean);
      const paren = /\(([^)]+)\)/.exec(i.title || "");
      out.push({ ent: entOf(i.company), at, kind: kindOf(i), roles: roles.length ? roles : paren ? [paren[1]] : [] });
    }
    // one line per company and deadline: "Meesho (Senior Associate - BM): form + submission by Sun 22 Nov 18:00"
    const merged = new Map();
    for (const e of out.filter((x) => x.ent)) {
      const k = `${e.ent.key}|${Math.floor(e.at / 60000)}`;
      const m = merged.get(k) || { ent: e.ent, at: e.at, kinds: new Set(), roles: new Set(), apps: [] };
      m.kinds.add(e.kind);
      e.roles.forEach((r) => m.roles.add(r));
      if (e.fromRole) m.apps.push(e.applied);
      merged.set(k, m);
    }
    return [...merged.values()].sort((a, b) => a.at - b.at || a.ent.name.localeCompare(b.ent.name));
  }
  function relTime(at, now) {
    const mins = Math.round((at - now.getTime()) / 60000);
    if (dayKey(at) !== dayKey(now) || mins <= 0) return "";
    return ` (in ${mins >= 60 ? `${Math.floor(mins / 60)}h ` : ""}${mins % 60}m)`;
  }
  const names = (list, n = 3) => (list.length > n ? `${list.slice(0, n).join(", ")} +${list.length - n} more` : list.join(", "));
  function deadlineLine(m, now, withCompany = true) {
    const roles = [...m.roles];
    const kinds = [...m.kinds].sort((a, b) => ORDER.indexOf(a) - ORDER.indexOf(b));
    const status = m.apps.length && m.apps.every(Boolean) ? " · ✓ applied" : m.apps.some(Boolean) ? ` · applied to ${m.apps.filter(Boolean).length} of ${m.apps.length}`
      : m.apps.length ? " · not applied" : "";
    const who = withCompany ? `${m.ent.name}${roles.length ? ` (${names(roles)})` : ""}` : (roles.length ? names(roles) : "");
    return `- ${who}: ${kinds.join(" + ")} by ${when(m.at)}${relTime(m.at, now)}${status}`;
  }
  function cap(lines, n = 12) { return lines.length > n ? [...lines.slice(0, n), `- +${lines.length - n} more`] : lines; }

  // ---------------------------------------------------------------- answers
  function latestNotice(data, ent) {
    return (data.notices || []).filter((n) => ent.raw.has(n.company))
      .sort((a, b) => String(b.notice_time).localeCompare(String(a.notice_time)))[0] || null;
  }

  function aboutCompany(ent, intents, data, ents, checked) {
    const now = data.now;
    const roles = (data.roles || []).filter((r) => ent.raw.has(r.company));
    const items = (data.items || []).filter((i) => i.company && ent.raw.has(i.company));
    const lines = [];
    const open = deadlineEntries(data, ents).filter((m) => m.ent === ent);
    const notice = latestNotice(data, ent);
    const noticeLine = notice ? `Last ${ent.name} notice: "${notice.subject}", ${when(notice.notice_time)}.` : `No ${ent.name} notice in the data yet.`;

    if (intents.has("whichcv")) {
      const withCv = roles.filter((r) => r.cv);
      lines.push(withCv.length ? withCv.map((r) => `${ent.name} (${r.designation}): apply with ${r.cv}.`).join("\n")
        : `No CV suggestion for ${ent.name} yet (it comes from your targets and CVs on the Profile page).`);
    }
    if (intents.has("pay")) {
      lines.push(roles.length ? roles.map((r) => `${ent.name} (${r.designation}): CTC ${r.ctc ? Number(r.ctc).toLocaleString("en-IN") + " " + (r.currency || "") : "not given"}`.trim()).join("\n")
        : `No pay details for ${ent.name} in the data.`);
    }
    if (intents.has("eligible")) {
      lines.push(roles.map((r) => `${ent.name} (${r.designation}): ${r.eligible === true ? "eligible" : r.eligible === false ? "not eligible" : "eligibility not sure (add your degree and department on the Profile page)"}`).join("\n")
        || `No ${ent.name} role in your companies list.`);
    }
    if (intents.has("test") || intents.has("shortlist")) {
      const ev = items.filter((i) => ["test", "shortlist", "result", "offer"].includes(i.category))
        .sort((a, b) => String(b.event_at || b.due_at || "").localeCompare(String(a.event_at || a.due_at || ""))).slice(0, 3);
      lines.push(ev.length ? ev.map((i) => `- ${i.title}${i.event_at && new Date(i.event_at) < now ? " (over)" : ""}`).join("\n")
        : `No test, shortlist or result for ${ent.name} in the data.`);
    }
    // deadlines: always for a deadline question, and for any question that isn't one of the above
    const deadlineAsked = intents.has("deadline") || !lines.length;
    if (deadlineAsked) {
      if (open.length) lines.unshift(`${ent.name}: open deadlines (last checked ${checked}):\n` + open.map((m) => deadlineLine(m, now, false)).join("\n"));
      else lines.unshift(`No open deadline for ${ent.name} in the ERP data (last checked ${checked}).`);
    }
    lines.push(noticeLine);
    // status: applied or not, and the latest list that names you
    if (roles.length) {
      const ap = roles.filter((r) => r.applied).map((r) => r.designation);
      lines.push(ap.length ? `You applied to: ${names(ap, 4)}.` : `You haven't applied to ${roles.length === 1 ? `the ${ent.name} role` : `any of the ${roles.length} ${ent.name} roles`}.`);
    }
    const mine = items.filter((i) => i.pdf_status === "yes" || i.pdf_status === "no")
      .sort((a, b) => String(b.event_at || b.due_at || "").localeCompare(String(a.event_at || a.due_at || "")))[0];
    if (mine && !(intents.has("test") || intents.has("shortlist"))) lines.push(mine.title);
    return lines.join("\n");
  }

  function capitalised(words) { return words.map((w) => w[0].toUpperCase() + w.slice(1)).join(" "); }

  function answer(question, data) {
    data = { ...data, now: new Date(data.now || Date.now()) };
    const now = data.now;
    const checked = data.lastChecked ? when(data.lastChecked) : "not yet";
    const ents = entities(data);
    const { hits, used } = matchCompanies(question, data, ents);
    const intents = intentsOf(question);
    const range = timeRange(question, now);

    if (hits.length) {
      return { kind: "company", companies: hits.map((e) => e.name),
               text: hits.slice(0, 3).map((e) => aboutCompany(e, intents, data, ents, checked)).join("\n\n") };
    }
    // a name Ping has no company for: the words left once question words, intents and times are gone
    const left = tokensOf(question).filter((t) => !STOP.has(t) && !used.has(t) && t.length >= 3 && !/^\d+$/.test(t));
    if (left.length && intents.size) {        // "google cv deadline"; a bare "hmm" is not a company
      const name = capitalised(left.slice(0, 3));
      const inSubject = (data.notices || []).filter((n) => left.some((t) => t.length >= 4 && norm(n.subject).split(" ").includes(t)))
        .sort((a, b) => String(b.notice_time).localeCompare(String(a.notice_time)))[0];
      if (inSubject) return { kind: "unknown", companies: [],
        text: `No open deadline for ${name} in the ERP data (last checked ${checked}). It isn't on your companies list; the last notice that mentions it: "${inSubject.subject}" (${shortName(inSubject.company)}), ${when(inSubject.notice_time)}.` };
      return { kind: "unknown", companies: [],
        text: `I don't have ${name} in your ERP data: no role on the companies list and no notice from it (last checked ${checked}).` };
    }
    if (intents.has("deadline") || (range && !intents.size)) {
      const r = range || { from: now.getTime(), to: now.getTime() + 3 * 86400000, label: "in the next 3 days" };
      const ls = deadlineEntries(data, ents, r.from, r.to).map((m) => deadlineLine(m, now));
      return { kind: "intent", companies: [], text: ls.length ? `Due ${r.label}:\n${cap(ls).join("\n")}`
        : `Nothing due ${r.label} in the ERP data (last checked ${checked}).` };
    }
    if (intents.has("test") || intents.has("shortlist")) {
      // tests earlier today count too (marked "over"): "any tests today?" at 17:30 still names the 15:00 one
      const from = range ? (range.dayStart ?? range.from) : now.getTime() - 86400000, to = range ? range.to : now.getTime() + 7 * 86400000;
      const ev = (data.items || []).filter((i) => ["test", "shortlist", "result"].includes(i.category) && i.event_at &&
        (i.level !== "hidden" || /digest|message|collapse|merged|already happened/.test(i.hidden_because || "")) &&
        new Date(i.event_at).getTime() >= from && new Date(i.event_at).getTime() < to)
        .sort((a, b) => String(a.event_at).localeCompare(String(b.event_at)));
      const label = range ? range.label : "from yesterday to the next 7 days";
      return { kind: "intent", companies: [], text: ev.length ? `Tests and lists ${label}:\n${cap(ev.map((i) => `- ${i.title}${new Date(i.event_at) < now ? " (over)" : ""}`)).join("\n")}`
        : `No tests or lists ${label} in the ERP data (last checked ${checked}).` };
    }
    if (intents.size) {
      const ex = deadlineEntries(data, ents)[0];
      return { kind: "intent", companies: [], text: `Which company? For example: "${[...intents][0] === "whichcv" ? "which cv for" : [...intents][0] === "pay" ? "ctc at" : "deadline for"} ${ex ? ex.ent.name : "Groww"}".` };
    }
    const soon = deadlineEntries(data, ents, now.getTime(), now.getTime() + 3 * 86400000).map((m) => deadlineLine(m, now));
    return { kind: "digest", companies: [], text: "I couldn't tell what you meant. Here's what's due soon:\n" +
      (soon.length ? cap(soon).join("\n") : `- nothing in the next 3 days (last checked ${checked})`) };
  }

  const api = { answer, matchCompanies, intentsOf, entities, shortName, deadlineEntries };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingRules = api;
})(typeof window !== "undefined" ? window : globalThis);
