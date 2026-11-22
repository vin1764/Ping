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
    "share send link links portal website site mail email notification notifications message messages question answer " +
    "summarise summarize summary summaries jd jds description descriptions they them their would role's " +
    "relevant anywhere located location based office city many number count cut off cutoff cgpa cg departments department " +
    "branch branches degree degrees backlog backlogs joining bonus bonuses take home breakdown breakup brekdown esop esops stock " +
    "retention relocation base fixed variable gross score scores marks rank percentile contact contacts phone poc spoc coordinator " +
    "after before day night january february march april may june july august september october november december jan feb mar apr " +
    "jun jul aug sep sept oct nov dec st nd rd th whats wheres whens hows lets yet so then too much ones one two three tonight's " +
    "allowed criteria cutoffs").split(" "));

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
    // "summarise X's JD", "what's the JD for X", "what do they want for X", "job description of X"
    if (has(/\bjds?\b|\bjob desc\w*|\bwhat do they (want|look|need)|\bwhat (is|s) the role\b|\bwhat would i do\b|\bsummari[sz]e\b/)) {
      out.add("jd");
      return out;                                  // a JD question is only that (its CV/skill words aren't a deadline)
    }
    if (has(/\b(deadlines?|due|last date|closes?|closing|closed|submit\w*|submissions?|forms?|apply by|register\w*|registration)\b/) ||
        (has(/\b(cv|resume)\b/) && !out.has("whichcv"))) out.add("deadline");
    if (has(/\bshort ?list\w*|\bselected\b|\bresults?\b|\b(am|was|are|is) (i|my name) (on|in) (the |a |any )?([a-z0-9]+ ){0,4}lists?\b/)) out.add("shortlist");
    if (has(/\b(tests?|exams?|assessments?|oa|rooms?|venue|slots?|interviews?|ppt|dates?)\b/) && !has(/\blast date\b/)) out.add("test");
    if (has(/\b(ctc|pay|salary|package|stipend|lpa|compensation|bond)\b/)) out.add("pay");
    if (has(/\beligib\w*/)) out.add("eligible");
    if (has(/\b(did i apply|have i applied|applied)\b/)) out.add("applied");
    if (has(/\b(bond|take ?home|joining|bonus\w*|esops?|stocks?|retention|relocation|base salary|break ?(down|up)|brekdown)\b/)) out.add("pay");
    if (has(/\bcut ?offs?\b|\bcgpa\b|\bcg\b|\b(departments?|branch\w*|degrees?)\b.*\b(apply|allowed|eligible|can)\b|\bwho can apply\b/)) out.add("eligible");
    if (has(/\b(notices?|announcements?|circulars?)\b/)) out.add("notice");
    // placement mail: "any mails for X", "did I get a test link for Y", "what's due from mail"
    if (has(/\b(e ?mails?|mails?|mailed|inbox|via email)\b/) || has(/\b(test|assessment|oa|interview|meeting) links?\b/)) out.add("mail");
    if (has(/\b(what|which) roles\b|\broles? (does|do|at|in)\b|\bopenings?\b|\bpositions?\b/) && !out.has("deadline")) out.add("roles");
    if (has(/\b(located|location|based (in|at)|which city|office)\b/)) out.add("location");
    else if (has(/\bwhere\b/)) out.add("test");
    if (has(/\b(score|scores|marks|rank|percentile)\b/)) out.add("score");
    if (has(/\b(contacts?|phone|poc|spoc|coordinator|email id|number of the)\b/) && !has(/\bhow many\b/)) out.add("contact");
    if (has(/\b(anything|whats|what is|something) (new )?for me\b|\bfor me today\b/) && !out.size) out.add("foryou");
    if (has(/\bwhen\b/) && !out.size) out.add("deadline").add("test");
    if (has(/\bhow many\b|\bnumber of\b|\bcount\b/)) out.add("count");
    if (out.has("score") || out.has("contact")) { out.delete("test"); out.delete("shortlist"); out.delete("deadline"); }
    return out;
  }
  const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
  const WEEKDAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
  function timeRange(question, now) {
    const q = norm(question);
    const start = new Date(`${dayKey(now)}T00:00:00+05:30`).getTime();
    const day = (t, label) => ({ from: t, to: t + 86400000, label });
    if (/\bday after\b/.test(q)) return day(start + 2 * 86400000, `on ${dayName(start + 2 * 86400000)}`);
    // "25 november", "nov 25", "25th nov"
    const md = q.match(/\b(\d{1,2})(?:st|nd|rd|th)? (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b/) ||
      q.match(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* (\d{1,2})(?:st|nd|rd|th)?\b/);
    if (md) {
      const [dd, mon] = /^\d/.test(md[1]) ? [md[1], md[2]] : [md[2], md[1]];
      const y = Number(dayKey(now).slice(0, 4));
      const t = new Date(`${y}-${String(MONTHS.indexOf(mon) + 1).padStart(2, "0")}-${String(dd).padStart(2, "0")}T00:00:00+05:30`).getTime();
      if (!isNaN(t)) return day(t, `on ${dayName(t)}`);
    }
    const wd = WEEKDAYS.findIndex((w) => new RegExp(`\\b(on |this |next )?${w}\\b`).test(q));
    if (wd >= 0) {
      const today = new Date(start + 12 * 3600000).getUTCDay();
      const t = start + (((wd - today + 7) % 7) || 7) * 86400000;
      return day(t, `on ${dayName(t)}`);
    }
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
    return ` (today, in ${mins >= 60 ? `${Math.floor(mins / 60)}h ` : ""}${mins % 60}m)`;
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

  // ---------------------------------------------------------------- job descriptions
  // The summary Ping made of a role's JD (roles.jd_summary, from the JD's own text: ping/jd.py), at most 120 words:
  // role & team, what you'd do, must-haves, location, eligibility, anything unusual. Never written fresh here.
  const words = (s) => String(s || "").split(/\s+/).filter(Boolean).length;
  function jdAnswer(role, name) {
    const who = `${name} (${role.designation})`;
    if (role.jd_source === "link-unreadable" && role.jd_url) return `${who}: The JD is a link I can't open: ${role.jd_url}`;
    const s = role.jd_summary;
    // a link Ping couldn't open, next to the JD it did find (the ERP's details)
    const linkNote = role.jd_url && role.jd_source === "detail" ? `\nThe full JD is a link I can't open: ${role.jd_url}` : "";
    const one = (v) => (Array.isArray(v) ? v.filter(Boolean).join("; ") : v ? String(v) : "");
    if (!s) {
      if (role.jd_text) return `${who}: ${String(role.jd_text).split(/\s+/).slice(0, 90).join(" ")}…` + linkNote;
      const note = String(role.jd_note || "").trim();
      // the ERP's own words when they say something ("As mentioned in Registration Email"), not "-" or "NA"
      const said = /[a-z]{3}/i.test(note) && !/^(n\/?a|nil|none|no jd on the erp)$/i.test(note) ? ` (the ERP says: "${note.slice(0, 80)}")` : "";
      return `${who}: no JD on the ERP${said}.`;
    }
    const team = one(s.role_team);
    const lines = [team && team.toLowerCase() !== String(role.designation || "").toLowerCase() ? `${who}: ${team}` : `${who}:`];
    if ((s.do || []).length) lines.push("What you'd do:", ...s.do.slice(0, 3).map((x) => `- ${x}`));
    if ((s.must_have || []).length) lines.push(`Must-have: ${s.must_have.slice(0, 5).join("; ")}`);
    if (one(s.location)) lines.push(`Location: ${one(s.location)}`);
    const elig = one(s.eligibility) || (role.cgpa_cutoff ? `CG cut-off ${role.cgpa_cutoff} (ERP)` : "");
    if (elig) lines.push(`Eligibility: ${elig}`);
    const odd = [...(s.unusual || [])];
    if (role.bond && !odd.some((x) => /bond|service/i.test(x)) && !/^no$/i.test(String(role.bond).trim())) odd.push(`bond: ${role.bond} (ERP)`);
    if (odd.length) lines.push(`Unusual: ${odd.slice(0, 3).join("; ")}`);
    // at most 120 words: drop from the end of the longest lists first
    let out = lines;
    while (words(out.join(" ")) > 120 && out.length > 2) {
      const i = out.findLastIndex((l) => l.startsWith("- "));
      out = out.filter((_, k) => k !== (i > 1 ? i : out.length - 1));
    }
    const src = role.jd_source === "attachment" ? "the JD file on the ERP" : role.jd_source === "link" ? "the JD link"
      : role.jd_source === "detail" ? "the ERP's role details" : "the ERP's job description";
    return out.join("\n") + `\n(From ${src}.)` + linkNote;
  }

  function jdForCompany(ent, question, data) {
    let roles = (data.roles || []).filter((r) => ent.raw.has(r.company));
    // a role named in the question narrows it ("searce associate data engineer")
    const q = new Set(tokensOf(question));
    const scored = roles.map((r) => [r, keyWords(r.designation).filter((w) => q.has(w) && !LEGAL.has(w)).length]);
    const best = Math.max(0, ...scored.map((x) => x[1]));
    if (best > 0) roles = scored.filter((x) => x[1] === best).map((x) => x[0]);
    if (!roles.length) return `I don't have a ${ent.name} role on your companies list.`;
    const shown = roles.slice(0, 3).map((r) => jdAnswer(r, ent.name));
    return shown.join("\n\n") + (roles.length > 3 ? `\n\n+${roles.length - 3} more ${ent.name} roles: name one to see its JD.` : "");
  }

  // ---------------------------------------------------------------- one company: the parts asked about
  const money = (v, cur) => (v == null || v === "" || isNaN(Number(v)) ? String(v ?? "") : `${Number(v).toLocaleString("en-IN")}${cur ? ` ${cur}` : ""}`);
  const PAYF = /ctc|salary|gross|take ?home|bonus|bond|stipend|esop|stock|variable|incentive|retention|relocation|joining|allowance|compensation|base/i;
  // the pay parts a question names ("joining bonus", "take home", "bond"): only those fields; none named: all of them
  const PART = [["bond", /\bbonds?\b/, /bond/i], ["take home", /take ?home/, /take ?home/i], ["joining", /joining/, /joining/i],
    ["retention", /retention/, /retention/i], ["relocation", /relocation/, /relocation/i], ["esop", /esops?|stocks?/, /esop|stock/i],
    ["base", /\bbase\b|\bfixed\b/, /base|fixed/i], ["variable", /variable|incentive/, /variable|incentive/i]];
  // roles of a company, narrowed by role words in the question ("same for analyst role?")
  function narrow(roles, question) {
    const q = new Set(tokensOf(question || ""));
    const scored = roles.map((r) => [r, keyWords(r.designation).filter((w) => q.has(w) && !LEGAL.has(w)).length]);
    const best = Math.max(0, ...scored.map((x) => x[1]));
    return best > 0 ? scored.filter((x) => x[1] === best).map((x) => x[0]) : roles;
  }
  const label = (ent, r) => `${ent.name} (${r.designation})`;
  function payLinesFor(ent, r, question) {
    const fields = r.pay || {};
    const q = norm(question || "");
    const parts = PART.filter(([, inQ]) => inQ.test(q));
    const pick = Object.entries(fields).filter(([k, v]) => PAYF.test(k) && String(v ?? "").trim() !== "" &&
      (!parts.length || parts.some(([, , inField]) => inField.test(k))));
    const head = `${label(ent, r)}: CTC ${r.ctc ? money(r.ctc, r.currency || "INR") : "not given"}`;
    if (parts.length === 1 && parts[0][0] === "bond") {
      const b = fields.Bonds ?? r.bond;
      const none = /^(no|nil|none|0)$/i.test(String(b ?? "").trim()) || Number(fields["Bond Amount"]) === 0;
      return `${label(ent, r)}: ${b == null ? "the ERP doesn't say whether there's a bond" : none ? "no bond (Bonds: No)" : `bond: ${b}${fields["Bond Amount"] ? `, amount ${money(fields["Bond Amount"])}` : ""}${fields["Bond Duration"] ? `, ${fields["Bond Duration"]}` : ""}`}.`;
    }
    if (!pick.length) return parts.length ? `${label(ent, r)}: the ERP doesn't give ${parts.map((p) => p[0]).join(" or ")}.` : `${head}.`;
    return `${parts.length ? label(ent, r) : head}: ${pick.map(([k, v]) => `${k}: ${/^\d+(\.\d+)?$/.test(String(v).trim()) ? money(v) : String(v).trim()}`).join("; ")}.`;
  }
  function eligibleLine(ent, r, data, question) {
    const p = data.profile || {};
    const bits = [];
    if (r.cgpa_cutoff != null && r.cgpa_cutoff !== "") {
      const cut = Number(r.cgpa_cutoff);
      bits.push(`CG cut-off ${cut % 1 ? cut : cut.toFixed(1)}` + (p.cgpa != null ? `, your CGPA ${Number(p.cgpa).toFixed(1)}: ${Number(p.cgpa) >= cut ? "met" : "not met"}` : ""));
    } else bits.push("no CG cut-off given");
    const depts = [...new Set((r.allowed || []).map((a) => a.department).filter(Boolean))];
    if (/\b(department|branch|who can apply)/.test(norm(question || ""))) bits.push(depts.length ? `departments allowed: ${depts.join(", ")}` : "the ERP doesn't list departments");
    if (r.backlog_rule) bits.push(`backlogs: ${r.backlog_rule}`);
    const status = r.eligible === true ? "eligible (ERP)" : r.eligible === false ? "not eligible (ERP)"
      : !p.department || !p.degree ? "the rest can't be checked until your department and degree are on the Profile page" : "eligibility not sure";
    return `${label(ent, r)}: ${bits.join("; ")}; ${status}.`;
  }
  function testLines(items, now) {
    return items.map((i) => {
      const at = i.event_at && new Date(i.event_at);
      const pdf = i.pdf || {};
      const row = pdf.details || {};
      const t = String(i.title || "");
      const where = [i.venue && !t.includes(i.venue) ? i.venue : "", row.room && !t.includes(row.room) ? `your room: ${row.room}` : "",
                     row.slot && !t.includes(row.slot) ? `your slot: ${row.slot}` : ""].filter(Boolean).join(" · ");
      const st = pdf.status || i.pdf_status;
      const list = /you're (now )?(on|not on)|you are (not )?on/i.test(t) ? "" : st === "yes" ? "you're on the list" : st === "no" ? "you're not on the list" : "";
      const time = at ? (at < now ? ` (${dayKey(at) === dayKey(now) ? "earlier today, " : ""}over)` : relTime(at.getTime(), now) || "") : "";
      return `- ${i.title}${time}${where ? ` · ${where}` : ""}${list ? ` · ${list}` : ""}`;
    });
  }
  const isListItem = (i) => ["test", "shortlist", "result", "offer"].includes(i.category) || ["test_rooms", "shortlist", "result", "interview"].includes(i.kind);

  function aboutCompany(ent, intents, data, ents, checked, question, spec = {}) {
    if (intents.has("jd")) return jdForCompany(ent, question, data);
    const now = data.now;
    const all = (data.roles || []).filter((r) => ent.raw.has(r.company));
    const roles = narrow(all, spec.roleQuestion || question);
    const items = (data.items || []).filter((i) => i.company && ent.raw.has(i.company));
    const lines = [];
    const open = deadlineEntries(data, ents).filter((m) => m.ent === ent);
    const notice = latestNotice(data, ent);
    const noticeLine = notice ? `Last ${ent.name} notice: "${notice.subject}", ${when(notice.notice_time)}.` : `No ${ent.name} notice in the data yet.`;
    let saidNotice = false, saidApplied = false;

    if (intents.has("score")) lines.push(`I don't have your scores: the ERP doesn't publish test scores or ranks for ${ent.name}.`);
    if (intents.has("contact")) lines.push(`I don't have contact details for ${ent.name}: Ping leaves out names and phone numbers from notices.`);
    if (intents.has("location")) {
      const locs = roles.map((r) => r.jd_location && `${label(ent, r)}: ${r.jd_location}`).filter(Boolean);
      lines.push(locs.length ? locs.join("\n") : `I don't have a job location for ${ent.name}: the ERP's role details don't give one.`);
    }
    if (intents.has("whichcv")) {
      const withCv = roles.filter((r) => r.cv);
      lines.push(withCv.length ? withCv.map((r) => `${label(ent, r)}: apply with ${r.cv}.`).join("\n")
        : `No CV suggestion for ${ent.name} yet (it comes from your targets and CVs on the Profile page).`);
    }
    if (intents.has("roles")) lines.push(`${ent.name} roles (${all.length}):\n` + all.map((r) => `- ${r.designation}${r.ctc ? ` · CTC ${money(r.ctc, r.currency || "INR")}` : ""}${r.deadline ? ` · ${new Date(r.deadline) > now ? "closes" : "closed"} ${when(r.deadline)}` : ""}${r.applied ? " · ✓ applied" : ""}`).join("\n"));
    if (intents.has("pay")) lines.push(roles.length ? roles.map((r) => payLinesFor(ent, r, spec.payQuestion || question)).join("\n") : `No pay details for ${ent.name} in the data.`);
    if (intents.has("eligible")) lines.push(roles.length ? roles.map((r) => eligibleLine(ent, r, data, question)).join("\n") : `No ${ent.name} role in your companies list.`);
    if (intents.has("applied")) {
      const ap = roles.filter((r) => r.applied).map((r) => r.designation);
      lines.push(!roles.length ? `No ${ent.name} role in your companies list.` : ap.length ? `Yes, you applied to ${ent.name}: ${names(ap, 4)}.`
        : `No, you haven't applied to ${roles.length === 1 ? `the ${ent.name} role (${roles[0].designation})` : `any of the ${roles.length} ${ent.name} roles`}.`);
      saidApplied = true;
    }
    if (intents.has("test") || intents.has("shortlist")) {
      const ev = items.filter(isListItem).sort((a, b) => String(b.event_at || b.due_at || "").localeCompare(String(a.event_at || a.due_at || "")));
      if (intents.has("shortlist") && !intents.has("test")) {
        const lists = ev.filter((i) => (i.pdf?.status || i.pdf_status) === "yes" || (i.pdf?.status || i.pdf_status) === "no");
        // the latest list decides the yes / no; the ones before it follow, one line each
        const st = (i) => i.pdf?.status || i.pdf_status;
        lines.push(lists.length ? [`${st(lists[0]) === "yes" ? "Yes, you're on" : "No, you're not on"} the latest ${ent.name} list: ${lists[0].title}`,
          ...lists.slice(1, 3).filter((i) => st(i) !== st(lists[0])).map((i) => `Earlier: ${i.title}`)].join("\n")
          : `No ${ent.name} shortlist or result that names you or leaves you out in the data.`);
      } else {
        // "which room was I in": the one list that has your row
        const mineRow = /\b(room|slot|seat)\b/.test(norm(question)) ? ev.filter((i) => i.pdf?.details?.room || i.pdf?.details?.slot).slice(0, 1) : [];
        // a bare "when is it?" asks for both: say "no test" only when there's no deadline answer either
        if (ev.length) lines.push(testLines(mineRow.length ? mineRow : ev.slice(0, 3), now).join("\n"));
        else if (!intents.has("deadline")) lines.push(`No test, shortlist or result for ${ent.name} in the data.`);
      }
    }
    if (intents.has("notice")) {
      const fromIt = notice && items.filter((i) => i.notice_id && i.notice_id === notice.notice_id && i.title)
        .sort((a, b) => String(b.first_seen || "").localeCompare(String(a.first_seen || "")))[0];
      lines.push(notice ? noticeLine + (fromIt ? `\nPing's message about it: ${fromIt.title}` : "") : `I don't have any notice for ${ent.name} in the ERP data.`);
      saidNotice = true;
    }
    // deadlines: always for a deadline question, and for any question that isn't one of the above
    const deadlineAsked = intents.has("deadline") || (!lines.length && !intents.has("notice"));
    if (deadlineAsked) {
      const mine = open.filter((m) => !spec.roleQuestion || [...m.roles].some((d) => roles.some((r) => r.designation === d)));
      if (mine.length) lines.unshift(`${ent.name}: open deadlines (last checked ${checked}):\n` + mine.map((m) => deadlineLine(m, now, false)).join("\n"));
      else {
        const closed = roles.filter((r) => r.deadline && new Date(r.deadline) <= now).sort((a, b) => String(b.deadline).localeCompare(String(a.deadline))).slice(0, 3);
        lines.unshift(`No open deadline for ${ent.name} in the ERP data (last checked ${checked}).` +
          (closed.length ? "\n" + closed.map((r) => `${label(ent, r)}: closed ${when(r.deadline)} (already passed).`).join("\n") : ""));
      }
    }
    const short = intents.has("pay") || intents.has("eligible") || intents.has("location") || intents.has("score") || intents.has("contact") ||
      intents.has("whichcv") || intents.has("roles") || intents.has("test") || intents.has("shortlist");
    if (!saidNotice && !short) lines.push(noticeLine);
    // status: applied or not, and the latest list that names you
    if (roles.length && !saidApplied && !short) {
      const ap = roles.filter((r) => r.applied).map((r) => r.designation);
      lines.push(ap.length ? `You applied to: ${names(ap, 4)}.` : `You haven't applied to ${roles.length === 1 ? `the ${ent.name} role` : `any of the ${roles.length} ${ent.name} roles`}.`);
    }
    const mine = items.filter((i) => i.pdf_status === "yes" || i.pdf_status === "no")
      .sort((a, b) => String(b.event_at || b.due_at || "").localeCompare(String(a.event_at || a.due_at || "")))[0];
    if (mine && !short) lines.push(mine.title);
    return lines.join("\n");
  }

  // ---------------------------------------------------------------- no company: lists for a time
  const HM = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  function dayWord(at, now) {
    const d = dayKey(at), n = dayKey(now), tm = dayKey(now.getTime() + 86400000);
    if (d === n) return Number(HM.format(at).slice(0, 2)) >= 17 ? "tonight" : "today";
    if (d === tm) return "tomorrow";
    return dayName(at);
  }
  // Applications closing in a range, one block per closing time, the same counts as the digest and Today:
  // "Close tonight 20:00 (in 2h 28m), Sat 21 Nov — 8 for you, 9 applied:" (for you = not applied yet and for you)
  function dueBlocks(data, from, to) {
    const now = data.now;
    const open = (data.roles || []).filter((r) => r.eligible !== false && r.deadline && new Date(r.deadline) > now &&
      new Date(r.deadline).getTime() >= from && new Date(r.deadline).getTime() < to);
    const byTime = new Map();
    for (const r of open) { const k = new Date(r.deadline).getTime(); byTime.set(k, [...(byTime.get(k) || []), r]); }
    const marked = (data.roles || []).some((r) => r.for_you !== undefined);
    const listOthers = data.prefs?.listOthers !== false;
    const line = (r) => `- ${shortName(r.company)} — ${r.designation}`;
    const sort = (rs) => [...rs].sort((a, b) => shortName(a.company).localeCompare(shortName(b.company)) || a.designation.localeCompare(b.designation));
    return [...byTime.entries()].sort((a, b) => a[0] - b[0]).map(([t, rs]) => {
      const at = new Date(t), day = dayWord(at, now);
      const rel = relTime(t, now).replace("(today, in ", "(in ");
      const head = `Close ${day} ${HM.format(at)}${rel}${/^(tonight|today|tomorrow)$/.test(day) ? `, ${dayName(at)}` : ""}`;
      const applied = rs.filter((r) => r.applied);
      if (!marked) return [`${head} — ${rs.length} role${rs.length === 1 ? "" : "s"}, ${applied.length} applied:`, ...sort(rs).map((r) => line(r) + (r.applied ? " ✓ applied" : ""))].join("\n");
      const mine = rs.filter((r) => !r.applied && r.for_you);
      const others = rs.filter((r) => !r.applied && !r.for_you);
      return [`${head} — ${mine.length} for you, ${applied.length} applied:`,
        "For you:", ...(mine.length ? sort(mine).map((r) => line(r) + (r.cv ? ` (apply with ${r.cv})` : "")) : ["- none"]),
        ...(applied.length ? ["Applied:", ...sort(applied).map((r) => `${line(r)} ✓ applied`)] : []),
        ...(others.length ? (listOthers ? [`Others (${others.length}):`, ...sort(others).map(line)] : [`Others: ${others.length} more (not listed)`]) : []),
      ].join("\n");
    });
  }
  // forms and submissions due in a range (from the feed), one line per company and time
  function formLines(data, ents, from, to) {
    // the application itself is in the blocks above: here only the forms and submissions
    return deadlineEntries(data, ents, from, to).filter((m) => [...m.kinds].some((k) => k !== "application"))
      .map((m) => deadlineLine({ ...m, kinds: new Set([...m.kinds].filter((k) => k !== "application")), apps: [] }, data.now));
  }
  // the most urgent thing left today, for "anything else?": "48 roles close at 20:00 today (in 2h 28m), 39 not applied: ..."
  function urgentLine(data) {
    const now = data.now, end = new Date(`${dayKey(now)}T00:00:00+05:30`).getTime() + 86400000;
    const open = (data.roles || []).filter((r) => r.eligible !== false && r.deadline && new Date(r.deadline) > now && new Date(r.deadline).getTime() < end);
    if (!open.length) return "";
    const t = Math.min(...open.map((r) => new Date(r.deadline).getTime()));
    const rs = open.filter((r) => new Date(r.deadline).getTime() === t);
    const not = rs.filter((r) => !r.applied);
    const mine = not.filter((r) => r.for_you);
    const cos = [...new Set((mine.length ? mine : not).map((r) => shortName(r.company)))].sort((a, b) => a.localeCompare(b));
    return `${rs.length} roles close at ${HM.format(new Date(t))} today${relTime(t, now).replace("(today, in ", "(in ")}, ${not.length} not applied` +
      `${mine.length ? ` (${mine.length} for you)` : ""}: ${names(cos, 5)}.`;
  }
  function nextDeadline(data, after) {
    const r = (data.roles || []).filter((x) => x.eligible !== false && x.deadline && new Date(x.deadline).getTime() >= after)
      .sort((a, b) => String(a.deadline).localeCompare(String(b.deadline)))[0];
    return r ? ` Next: ${shortName(r.company)} (${r.designation}) closes ${when(r.deadline)}.` : "";
  }

  function capitalised(words) { return words.map((w) => w[0].toUpperCase() + w.slice(1)).join(" "); }

  // spec (from route): { intents, hits, range, else, roleQuestion, payQuestion } instead of reading the question again
  function answer(question, data, spec) {
    data = { ...data, now: new Date(data.now || Date.now()) };
    const now = data.now;
    const checked = data.lastChecked ? when(data.lastChecked) : "not yet";
    const ents = spec?.ents || entities(data);
    const m0 = spec ? { hits: spec.hits, used: new Set() } : matchCompanies(question, data, ents);
    const { hits, used } = m0;
    const intents = spec ? new Set(spec.intents) : intentsOf(question);
    const range = spec ? spec.range : timeRange(question, now);
    if (intents.has("mail") && !intents.has("contact")) return mailAnswer(question, data, hits, intents, range, checked);

    if (hits.length) {
      return { kind: "company", companies: hits.map((e) => e.name),
               text: hits.slice(0, 3).map((e) => aboutCompany(e, intents, data, ents, checked, question, spec || {})).join("\n\n") };
    }
    // a name Ping has no company for: the words left once question words, intents and times are gone
    const left = spec ? spec.unknown || [] : tokensOf(question).filter((t) => !STOP.has(t) && !used.has(t) && t.length >= 3 && !/^\d+$/.test(t));
    const factual = [...intents].some((i) => !["count", "foryou"].includes(i));
    if (left.length && factual && left.length <= 3) {        // "google cv deadline"; a bare "hmm" is not a company
      const name = capitalised(left.slice(0, 3));
      const inSubject = (data.notices || []).filter((n) => left.some((t) => t.length >= 4 && norm(n.subject).split(" ").includes(t)))
        .sort((a, b) => String(b.notice_time).localeCompare(String(a.notice_time)))[0];
      if (inSubject) return { kind: "unknown", companies: [],
        text: `No open deadline for ${name} in the ERP data (last checked ${checked}). It isn't on your companies list; the last notice that mentions it: "${inSubject.subject}" (${shortName(inSubject.company)}), ${when(inSubject.notice_time)}.` };
      return { kind: "unknown", companies: [],
        text: `I don't have ${name} in your ERP data: no role on the companies list and no notice from it (last checked ${checked}).` };
    }
    if (intents.has("score")) return { kind: "intent", companies: [], text: "I don't have your scores: the ERP doesn't publish test scores or ranks." };
    if (intents.has("contact")) return { kind: "intent", companies: [], text: "I don't have contact details: Ping leaves out names and phone numbers from notices." };
    if (intents.has("foryou")) {
      const r = { from: now.getTime(), to: now.getTime() + 3 * 86400000 };
      const blocks = dueBlocks(data, r.from, r.to).map((b) => b.split("\nApplied:")[0].split("\nOthers")[0]);
      const tests = (data.items || []).filter((i) => isListItem(i) && i.event_at && dayKey(i.event_at) === dayKey(now) && i.level !== "hidden");
      const parts = [...blocks, ...(tests.length ? ["Tests today:", ...testLines(tests, now)] : [])];
      return { kind: "intent", companies: [], text: parts.length ? parts.join("\n\n") : `Nothing for you in the next 3 days (last checked ${checked}).` };
    }
    if (intents.has("deadline") || (range && !intents.size)) {
      const r = range || { from: now.getTime(), to: now.getTime() + 3 * 86400000, label: "in the next 3 days" };
      const blocks = dueBlocks(data, r.from, r.to);
      const forms = formLines(data, ents, r.from, r.to);
      if (spec?.else) {
        return { kind: "intent", companies: [], text: blocks.length || forms.length
          ? `That's everything due ${r.label}: nothing else in the ERP data.${nextDeadline(data, r.to)}`
          : `Nothing else due ${r.label} (last checked ${checked}).${nextDeadline(data, r.to)}` };
      }
      const count = intents.has("count") ? `${blocks.reduce((n, b) => n + (b.match(/^- /gm) || []).length, 0)} roles close ${r.label}.\n\n` : "";
      return { kind: "intent", companies: [], text: blocks.length || forms.length
        ? count + [...blocks, ...(forms.length ? [`Forms and submissions due ${r.label}:\n${cap(forms).join("\n")}`] : [])].join("\n\n")
        : `Nothing due ${r.label} in the ERP data (last checked ${checked}).${nextDeadline(data, r.to)}` };
    }
    if (intents.has("shortlist") && !intents.has("test")) {
      const since = now.getTime() - 21 * 86400000;
      const yes = (data.items || []).filter((i) => (i.pdf?.status || i.pdf_status) === "yes" && new Date(i.event_at || i.notice_time || i.due_at || 0).getTime() >= since - 86400000)
        .sort((a, b) => String(b.event_at || "").localeCompare(String(a.event_at || "")));
      return { kind: "intent", companies: [], text: yes.length ? `${intents.has("count") ? `${yes.length} lists name you` : "Lists that name you"} (last 3 weeks):\n${cap(testLines(yes, now)).join("\n")}`
        : `No shortlist or list names you in the last 3 weeks (last checked ${checked}).` };
    }
    if (intents.has("test") || intents.has("shortlist")) {
      // tests earlier today count too (marked "over"): "any tests today?" at 17:30 still names the 15:00 one
      const from = range ? (range.dayStart ?? range.from) : now.getTime() - 86400000, to = range ? range.to : now.getTime() + 7 * 86400000;
      const ev = (data.items || []).filter((i) => ["test", "shortlist", "result"].includes(i.category) && i.event_at &&
        (i.level !== "hidden" || /digest|message|collapse|merged|already happened/.test(i.hidden_because || "")) &&
        new Date(i.event_at).getTime() >= from && new Date(i.event_at).getTime() < to)
        .sort((a, b) => String(a.event_at).localeCompare(String(b.event_at)));
      const label = range ? range.label : "from yesterday to the next 7 days";
      if (spec?.else) {
        const u = urgentLine(data);
        return { kind: "intent", companies: [], text: `No other test ${label.replace(/ \(.*\)$/, "")}${ev.length ? `: ${ev.length === 1 ? "that was the only one" : `those ${ev.length} are all`}` : ""}.${u ? ` ${u}` : ""}` };
      }
      return { kind: "intent", companies: [], text: ev.length ? `${intents.has("count") ? `${ev.length} ` : ""}Tests and lists ${label}:\n${cap(testLines(ev, now)).join("\n")}`
        : `No tests or lists ${label} in the ERP data (last checked ${checked}).` };
    }
    if (intents.has("applied")) {
      const ap = (data.roles || []).filter((r) => r.applied);
      return { kind: "intent", companies: [], text: ap.length ? `You applied to ${ap.length} roles at ${new Set(ap.map((r) => r.company)).size} companies, for example ${names([...new Set(ap.map((r) => shortName(r.company)))].sort(), 6)}. Ask about one company for its roles.`
        : "You haven't applied to any role on the companies list yet." };
    }
    if (intents.has("jd")) return { kind: "intent", companies: [], text: 'Which company\'s JD? For example: "summarise the JD for Groww".' };
    if (intents.size) {
      const ex = deadlineEntries(data, ents)[0];
      const first = [...intents].filter((i) => i !== "count")[0];
      return { kind: "intent", companies: [], text: `Which company? For example: "${first === "whichcv" ? "which cv for" : first === "pay" ? "ctc at" : first === "eligible" ? "am I eligible for" : "deadline for"} ${ex ? ex.ent.name : "Groww"}".` };
    }
    const soon = deadlineEntries(data, ents, now.getTime(), now.getTime() + 3 * 86400000).map((m) => deadlineLine(m, now));
    return { kind: "digest", companies: [], text: "I couldn't tell what you meant. Here's what's due soon:\n" +
      (soon.length ? cap(soon).join("\n") : `- nothing in the next 3 days (last checked ${checked})`) };
  }

  // ---------------------------------------------------------------- placement mail
  // Messages from your mail: "via email" (only the mail has it) and ERP messages the mail repeated ("also mailed").
  const TEST_URL = /hackerrank|hackerearth|mettl|codility|codesignal|imocha|shl\.|talview|hirepro|amcat|cocubes|glider|testgorilla|hirevue|\/test|assess/i;
  const mailOf = (i) => i.via === "email" || i.details?.via === "email" ? "via email" : (i.mail || i.details?.mail)?.note ? "also on the ERP" : null;
  const linkOf = (i) => (i.mail || i.details?.mail)?.link || (i.todo || i.details?.todo)?.link || null;
  function mailAnswer(question, data, hits, intents, range, checked) {
    const now = data.now.getTime(), q = norm(question);
    const wantsTest = /\b(test|assessment|oa)\b/.test(q), wantsDue = intents.has("deadline") || /\b(due|deadline|pending|to do|todo)\b/.test(q);
    let list = (data.items || []).filter((i) => mailOf(i));
    if (hits.length) list = list.filter((i) => hits.some((e) => e.raw.has(i.company) || norm(e.name) === norm(shortName(i.company))));
    else list = list.filter((i) => i.level !== "hidden");
    if (wantsTest) list = list.filter((i) => i.category === "test" || ["test", "interview"].includes(i.kind) ||
      (i.todo || i.details?.todo)?.action === "take_test" || TEST_URL.test(linkOf(i) || ""));
    if (wantsDue) list = list.filter((i) => i.due_at && Date.parse(i.due_at) > now)
      .sort((a, b) => Date.parse(a.due_at) - Date.parse(b.due_at));
    else list.sort((a, b) => String(b.first_seen || b.sort_at || "").localeCompare(String(a.first_seen || a.sort_at || "")));
    const who = hits.length ? hits.map((e) => e.name).join(", ") : "";
    if (!list.length) {
      const what = wantsTest ? "No test link" : wantsDue ? "Nothing due" : "No placement mail";
      return { kind: "mail", companies: hits.map((e) => e.name), text: `${what}${who ? ` from ${who}` : ""} in your mail${wantsTest ? " or on the ERP" : ""} so far (last checked ${checked}). I read placement mail only: from the placement office, companies on your list, test platforms, or with words like test, shortlist, interview, form, offer.` };
    }
    const line = (i) => {
      const t = String(i.title || "").replace(/\.$/, "");
      const link = linkOf(i);
      return `- ${t}${i.due_at && !/ by /.test(t) ? ` (due ${when(i.due_at)})` : ""} · ${mailOf(i)}${link ? `\n  ${link}` : ""}`;
    };
    const head = wantsTest ? `Test link${list.length === 1 ? "" : "s"}${who ? ` for ${who}` : ""}:` : wantsDue ? "Due from your mail:"
      : `Placement mail${who ? ` about ${who}` : ""} (newest first):`;
    return { kind: "mail", companies: hits.map((e) => e.name), text: [head, ...list.slice(0, 8).map(line),
      ...(list.length > 8 ? [`+${list.length - 8} more in the Feed`] : [])].join("\n") };
  }

  // ---------------------------------------------------------------- the router
  // Every message, before any model: FACT (answered here, no model call), ACT (a request to do something on the ERP:
  // the read-only answer), ACK ("ok", "thanks") or OPEN (summaries, "why", comparisons, anything else: the model,
  // with these facts). Follow-ups ("and slice?", "and tomorrow?", "nothing else?") are resolved against the last turn
  // first, then routed the same way.
  const FACT = ["whichcv", "deadline", "test", "shortlist", "pay", "eligible", "applied", "notice", "roles", "location", "score",
                "contact", "foryou", "jd", "mail"];
  const ACK = /^(ok(ay)?|k|kk|thanks?|thank you|thx|ty|cool|great|nice|got it|alright|fine|sure|perfect|noted|done)[\s.!]*$/i;
  const OPEN = /\b(why|how come|explain|compare|comparison|versus|vs|better|difference|differ|should i|recommend|suggest\w*|advice|advise|tips?|prepare|preparation|tell me (more )?about|what do you think|worth|pros|cons|opinion|which (one|company|role|offer) (is|should|would))\b/;
  const ELSE = /\b(nothing|anything|what|something|any|whats) else\b|\bany ?more\b|\bothers?\s*$|^else$/;
  const FOLLOW = /^(and|but|also|then|so|plus|what about|how about|same for|same|same with|and for)\b/;
  const PRONOUN = /\b(it|its|they|them|their|that|there|this one|those|these)\b/;
  const ACTIONS = "apply|withdraw|submit|upload|change|update|edit|accept|decline|reject|fill|register|cancel|sign\\s?up|opt\\s(?:in|out)|delete|remove|book|send|email|mail";
  const ACT_WORD = new RegExp(`\\b(${ACTIONS})\\b`, "i");
  const STARTS_WITH_ACT = new RegExp(`^(?:please\\s+|pls\\s+|kindly\\s+|ping,?\\s+)?(?:${ACTIONS})\\b`, "i");
  const ASKS_YOU = /^(?:please\s+|pls\s+|kindly\s+)?(?:can|could|would|will)\s+(?:you|ping)\b/i;
  function asksToAct(message) {
    const t = String(message || "").trim();
    if (!ACT_WORD.test(t)) return false;
    return /\b(?:for me|on my behalf)\b/i.test(t) || ASKS_YOU.test(t) || STARTS_WITH_ACT.test(t);
  }
  function parse(text, data, ents) {
    const { hits, used } = matchCompanies(text, data, ents);
    const intents = intentsOf(text);
    const range = timeRange(text, data.now);
    const unknown = hits.length ? [] : tokensOf(text).filter((t) => !STOP.has(t) && !used.has(t) && t.length >= 3 && !/^\d+$/.test(t));
    return { intents, hits, range, unknown, toks: tokensOf(text) };
  }
  // ---------------------------------------------------------------- help: Ping about itself (docs/HELP.md -> help.js)
  const HELP_DOC = () => root.PingHelp || (typeof require === "function" ? (() => { try { return require("./help.js"); } catch { return null; } })() : null);
  const HELP_TOPICS = [
    ["install", /\binstall\w*\b|\bhome ?screen\b|\badd (?:it |ping |this )?to (?:my |the )?(?:home|dock|desktop|taskbar)|\bdownload (?:ping|the app|this app|an app|app)\b|\b(?:get|use|have|is there) (?:ping |this )?(?:as )?an? (?:app|desktop app|mobile app)\b|\bpwa\b|\b(?:ping|this|there an?) app\b|\bapp version\b/],
    ["notifications", /\bnotif\w*|\bpush(?: messages?| alerts?)?\b(?! (?:the|my) )|\balerts?\b|\bnotify\b|\bbuzz\b|\bquiet hours\b/],
    ["checks", /\bhow (?:often|frequently)\b|\bwhen (?:do|does|will) (?:you|ping|it) (?:check|look|refresh|update)|\bcheck(?:ing)? (?:interval|frequency|schedule|window)\b|\bhow (?:do i|can i|to) (?:change|set) (?:the |how often|when)|\bevery (?:hour|30 min)\b.*\?|\bhow (?:fresh|up to date|recent)\b|\blast check(?:ed)?\b.*\bhow\b/],
    ["can", /\bwhat (?:can|can't|cannot|do|does|are) (?:you|ping)(?: do| help with| for)?\b|\bwho are you\b|\bwhat is ping\b|\bwhat(?:'s| is) this\b|\b(?:your|ping'?s) (?:features|abilities|capabilities|limits|limitations)\b|\bread[- ]only\b|\bcan (?:you|ping) (?:apply|submit|fill|upload|withdraw|accept)\b(?! (?:for|to) )|\bis it (?:safe|read[- ]only)\b|\bare you (?:a bot|an ai|real)\b/],
    ["preferences", /\b(?:how (?:do|can) i|how to|where (?:do|can) i) (?:change|set|edit|update|see|reset|pick|choose) (?:my )?(?:preferences|settings|targets?|interests?|feed|cgpa|cv|profile|companies)|\bwhere (?:are|is) (?:my )?(?:preferences|settings|profile)\b|\bhow (?:do|does) (?:the )?(?:targets?|preferences|for you) work\b/],
    ["data", /\bwhere (?:is|does|do) (?:my )?(?:data|info|information|password|passwords|cv|cvs) (?:live|go|stored|kept|saved)?|\b(?:is|are) my (?:data|password|passwords|cvs?|mails?|email) (?:safe|stored|private|shared|secure)\b|\bprivacy\b|\bwho can see\b|\bdo you (?:store|keep|save|read) (?:my )?(?:data|password|passwords|mails?|emails?|otp)\b|\bwhat do you (?:store|keep|save)\b/],
  ];
  const HELP_ALONE = /^(?:help|\?+|menu|commands|options|how (?:do i|to) use (?:ping|this|you)|how does (?:ping|this|it) work|about(?: ping)?|getting started|start|hi|hello|hey)[\s.!?]*$/;
  function helpTopic(question) {
    const q = norm(question);
    if (HELP_ALONE.test(q)) return "overview";
    for (const [topic, re] of HELP_TOPICS) if (re.test(q)) return topic;
    if (/\bhelp\b/.test(q) && tokensOf(q).length <= 4) return "overview";
    return null;
  }
  // "windows" | "mac" | "android" | "ios" | "other", from a browser's user agent (and touch points: an iPad says Mac)
  function platformOf(ua, touchPoints) {
    const u = String(ua || "");
    if (/iphone|ipad|ipod/i.test(u) || (/macintosh/i.test(u) && Number(touchPoints) > 1)) return "ios";
    if (/android/i.test(u)) return "android";
    if (/windows/i.test(u)) return "windows";
    if (/macintosh|mac os x/i.test(u)) return "mac";
    return "other";
  }
  function helpAnswer(topic, data) {
    const doc = HELP_DOC();
    if (!doc || !doc[topic]) return { kind: "help", topic, companies: [], text: "Ask me what's due, about a company, or say \"help\"." };
    const t = doc[topic];
    let text = t.text;
    if (topic === "install") {
      const plat = (data && data.platform) || "other";
      const steps = (t.platforms || {})[plat] || (t.platforms || {}).other || "";
      text = data && data.installed ? "You're already using Ping as an installed app." :
        `${t.text}\n${steps}${plat !== "other" ? "\n(On another device? Ask \"how do I install on iPhone\" or Android, Windows, Mac.)" : ""}`;
    }
    return { kind: "help", topic, companies: [], text };
  }
  // "how do I install on iphone": the platform named in the question wins over the browser asking
  function platformNamed(question) {
    const q = norm(question);
    return /\b(iphone|ipad|ios|safari)\b/.test(q) ? "ios" : /\bandroid\b/.test(q) ? "android" : /\b(windows|pc|laptop)\b/.test(q) ? "windows"
      : /\b(mac|macbook|macos)\b/.test(q) ? "mac" : null;
  }

  // -> { kind: "fact" | "act" | "ack" | "help" | "open", spec, why, resolved }  (spec goes to answer(question, data, spec))
  function route(question, previous, data) {
    data = { ...data, now: new Date(data.now || Date.now()) };
    const ents = entities(data);
    const raw = String(question || "").trim();
    if (ACK.test(raw)) return { kind: "ack", why: "acknowledgement" };
    const text = raw.replace(/^(ok(ay)?|alright|cool|thanks|great|right|hmm+)[,.!]+\s*/i, "");
    const q = norm(text);
    const cur = parse(text, data, ents);
    // about Ping itself ("how do I install", "help"); a company in the question makes it a question about that company
    const topic = helpTopic(raw);
    if (topic && (!cur.hits.length || ["install", "can", "data"].includes(topic) && !cur.intents.size))
      return { kind: "help", topic, platform: platformNamed(raw), why: `help: ${topic}` };
    let spec = { ents, intents: [...cur.intents], hits: cur.hits, range: cur.range, unknown: cur.unknown };
    let resolved = text, why = "";
    const isElse = ELSE.test(q);
    const prevQs = (previous || []).filter(Boolean);
    const follow = prevQs.length && (FOLLOW.test(q) || isElse || PRONOUN.test(q) || cur.toks.length <= 2 ||
      (!cur.intents.size && !cur.hits.length && !cur.unknown.length));
    if (follow) {
      // the last question that had something to go on (a company, an intent or a time)
      const prev = prevQs.map((p) => parse(String(p).replace(/^(ok(ay)?|alright|cool|thanks|great)[,.!]+\s*/i, ""), data, ents))
        .find((p) => p.intents.size || p.hits.length || p.range) || null;
      if (prev) {
        const ownIntents = [...cur.intents].filter((i) => i !== "count");
        const intents = ownIntents.length && !(isElse && !cur.hits.length) ? cur.intents : new Set([...prev.intents, ...cur.intents]);
        const hits = cur.hits.length ? cur.hits : prev.hits;
        const range = cur.range || (cur.hits.length ? null : prev.range);
        const news = cur.hits.length || cur.range || ownIntents.length || isElse ||
          cur.toks.some((t) => hits.some((e) => (data.roles || []).some((r) => e.raw.has(r.company) && keyWords(r.designation).includes(t))));
        if (!news) return { kind: "open", why: "follow-up with nothing new", spec: { ents, intents: [...prev.intents], hits: prev.hits, range: prev.range, unknown: [] }, resolved: prevQs[0] };
        spec = { ents, intents: [...intents], hits, range, unknown: cur.hits.length ? cur.unknown : [], else: isElse,
                 roleQuestion: cur.hits.length ? text : `${text} ${cur.toks.length <= 6 ? "" : ""}`.trim(),
                 payQuestion: [...cur.intents].includes("pay") ? text : prevQs[0] };
        if (!cur.hits.length && !cur.toks.some((t) => hits.some((e) => (data.roles || []).some((r) => e.raw.has(r.company) && keyWords(r.designation).includes(t))))) spec.roleQuestion = "";
        resolved = `${text} [about: ${hits.map((e) => e.name).join(", ") || "-"}; ${[...intents].join(", ")}${range ? `; ${range.label}` : ""}]`;
        why = "follow-up";
      }
    }
    if (asksToAct(text)) return { kind: "act", spec, why: "asks Ping to act", resolved };
    if (OPEN.test(q) && !spec.intents.includes("whichcv")) return { kind: "open", spec, why: "open-ended", resolved };
    const facts = spec.intents.filter((i) => FACT.includes(i));
    if (facts.length) return { kind: "fact", spec, why: why || `intent: ${facts.join(", ")}`, resolved };
    if (spec.range) return { kind: "fact", spec: { ...spec, intents: ["deadline", ...spec.intents] }, why: why || "a time", resolved };
    if (spec.hits.length && cur.toks.length <= 4) return { kind: "fact", spec, why: why || "a company", resolved };
    return { kind: "open", spec, why: why || "no fact intent", resolved };
  }
  // the reply for a routed message that the model doesn't answer
  function routed(r, question, data) {
    if (r.kind === "ack") return { kind: "ack", companies: [], text: "👍" };
    if (r.kind === "help") return helpAnswer(r.topic, { ...data, platform: r.platform || data.platform, installed: r.platform ? false : data.installed });
    if (r.kind === "act") {
      const verb = (String(question).match(ACT_WORD) || ["do that"])[0].toLowerCase();
      const base = r.spec?.hits?.length ? answer(question, data, { ...r.spec, intents: ["deadline"] }).text.split("\n").slice(0, 3).join("\n") : "";
      return { kind: "act", companies: [], text: `Ping is read-only, so I can't ${verb} for you: it only reads the ERP.${base ? `\n${base}` : ""}` };
    }
    return answer(question, data, r.spec);
  }

  // ---------------------------------------------------------------- numbers in a model's reply
  // Every number, time and amount the model writes must be in the facts it was given ("model_count_mismatch" if not).
  function numbersIn(text) {
    const t = String(text || "");
    const out = [];
    const re = /(\d{1,2}):(\d{2})|(\d+(?:[.,]\d+)*)\s*(lpa|lakhs?|lacs?|l\b|cr\b|crores?)?/gi;
    let m;
    while ((m = re.exec(t))) {
      if (m[1]) { out.push({ kind: "time", v: `${m[1].padStart(2, "0")}:${m[2]}`, raw: m[0] }); continue; }
      let s = m[3];
      const indian = /^\d{1,3}(,\d{2})*,\d{3}$/.test(s), western = /^\d{1,3}(,\d{3})+$/.test(s);
      if (indian || western) s = s.replace(/,/g, ""); else if (s.includes(",")) { s.split(",").forEach((x) => x && out.push({ kind: "num", v: Number(x), raw: x })); continue; }
      let v = Number(s);
      if (isNaN(v)) continue;
      const unit = (m[4] || "").toLowerCase();
      if (/^(lpa|lakh|lakhs|lac|lacs|l)$/.test(unit)) v *= 1e5; else if (/^(cr|crore|crores)$/.test(unit)) v *= 1e7;
      out.push({ kind: "num", v, raw: m[0].trim() });
    }
    return out;
  }
  // -> the numbers in the reply that aren't in the facts (empty: the reply is fine)
  function unsupportedNumbers(reply, facts, question) {
    const have = numbersIn(`${facts}\n${question || ""}`);
    const times = new Set(have.filter((x) => x.kind === "time").map((x) => x.v));
    const nums = have.filter((x) => x.kind === "num").map((x) => x.v);
    return numbersIn(reply).filter((x) => x.kind === "time" ? !times.has(x.v)
      : !(x.v <= 1 || nums.some((n) => (x.v >= 1e5 ? Math.abs(n - x.v) <= x.v * 0.005 : n === x.v)))).map((x) => x.raw);
  }

  const api = { answer, route, routed, helpTopic, helpAnswer, platformOf, asksToAct, numbersIn, unsupportedNumbers, dueBlocks, urgentLine, matchCompanies, intentsOf, entities, shortName, deadlineEntries, jdAnswer, timeRange };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingRules = api;
})(typeof window !== "undefined" ? window : globalThis);
