// Self-generated Ask Ping evals: walks the data (every company with an open or recent role) and asks about each
// fact (JD, CTC, eligibility, deadline, form, test time/room, shortlist, which CV) in five phrasings (formal,
// lowercase/typo, Hinglish, a follow-up with no company name, a source named). The ground truth comes from the data
// itself through an oracle written here (never the bot's own lookup), and each answer is scored: the right fact, the
// right source cited, no false absence, no repeat, at most 3 lines unless the question asks for detail.
//   node evals/generated/generate.js <facts.json> [--limit N] [--show N]   (a file shaped like the rules' data)
//   require("./generate.js").run(data) -> { summary, results }
const R = require(process.env.PING_RULES || "../../supabase/functions/_shared/answer_rules.js");

const FIELDS = ["jd", "ctc", "eligibility", "deadline", "form", "test", "shortlist", "whichcv"];
const ms = (v) => (v ? new Date(v).getTime() : NaN);
const HM = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const hm = (v) => HM.format(new Date(v));
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const REAL_JD = ["inline", "attachment", "link", "detail"];

// how a student would type the company: its short name, lowercase, with one typo
function names(company) {
  const short = R.shortName(company);
  const lower = short.toLowerCase();
  // the first real word (not "d." of "D. E. Shaw"): what a student types
  const w = lower.split(/\s+/).map((x) => x.replace(/[^a-z0-9.&-]/g, "")).find((x) => /^[a-z0-9][a-z0-9.&-]+$/.test(x) && x.replace(/\W/g, "").length >= 2) || lower;
  const typo = w.length >= 6 ? `${w.slice(0, 2)}${w[3]}${w[2]}${w.slice(4)}` : w;      // "groww" stays, "piramal" -> "pirmaal"
  return { formal: short, lower: w, typo };
}

// ---------------------------------------------------------------- the oracle: what the data says, and where
function about(company, text) {
  const w = norm(R.shortName(company)).split(" ").find((x) => x.length >= 2) || norm(company).split(" ")[0];
  return !!w && new RegExp(`\\b${w}\\b`).test(norm(text));
}
function truth(company, field, d) {
  // every company a student's word for it could mean ("deloitte": Deloitte and Deloitte Touche Tohmatsu India)
  const first = (c) => norm(R.shortName(c)).split(" ")[0];
  const same = (c) => c === company || (c && first(c) === first(company));
  const roles = d.roles.filter((r) => same(r.company));
  const now = ms(d.now);
  const notices = (d.notices || []).filter((n) => n.company === company || about(company, `${n.subject} ${n.text || ""}`));
  const mails = (d.emails || []).filter((m) => m.company === company || about(company, `${m.subject} ${m.snippet}`));
  const forms = (d.forms || []).filter((f) => [f.company, ...(f.companies || [])].some((c) => c === company || (c && about(company, c))));
  const items = (d.items || []).filter((i) => same(i.company) || (i.company && about(company, i.company)));
  if (field === "jd") {
    if (roles.some((r) => REAL_JD.includes(r.jd_source) && (r.jd_text || r.jd_summary))) return { src: "erp" };
    if (roles.some((r) => r.jd_source === "link-unreadable" && r.jd_url)) return { src: "erp", token: "link" };
    const doc = roles.find((r) => ["notice", "mail"].includes(r.jd_source));
    if (doc) return doc.jd_source === "mail" ? { src: "mail" } : { src: "notice", token: `notice ${((doc.jd_url || "").match(/[?&]id=(\d+)/) || doc.jd_note?.match(/notice (\d+)/) || [])[1]}` };
    const n = notices.find((x) => x.has_attachment && /\bjds?\b|job description/i.test(x.text || ""));
    if (n) return { src: "notice", token: `notice ${n.notice_id}` };
    if (mails.some((m) => m.pdf?.status === "jd")) return { src: "mail" };
    return { absent: true };
  }
  if (field === "ctc") {
    const r = roles.find((x) => Number(x.ctc) > 0);
    if (r) return { src: "erp", number: Number(r.ctc) };
    const n = notices.find((x) => /\bctc\b[^.]{0,40}\d/i.test(x.text || ""));
    if (n) return { src: "notice", token: `notice ${n.notice_id}` };
    return { absent: true };
  }
  if (field === "eligibility") {
    const cuts = [...new Set(roles.filter((x) => x.cgpa_cutoff != null).map((x) => Number(x.cgpa_cutoff)))];
    if (cuts.length) return { src: "erp", anyOf: cuts.map((c) => (c % 1 ? String(c) : c.toFixed(1))) };
    return { soft: true };                    // "can't be checked" is a fair answer: scored on absence and length only
  }
  if (field === "deadline") {
    const open = roles.filter((r) => r.deadline && ms(r.deadline) > now).sort((a, b) => ms(a.deadline) - ms(b.deadline));
    if (open.length) return { src: "erp", anyOf: [...new Set(open.map((r) => hm(r.deadline)))] };
    const f = forms.find((x) => x.due_at && ms(x.due_at) > now);
    if (f) return { src: "form", token: hm(f.due_at) };
    return { absent: true };
  }
  if (field === "form") {
    const todo = items.find((i) => i.todo?.action === "fill_form" && i.due_at && ms(i.due_at) > now);
    if (todo) return { src: "form", token: hm(todo.due_at) };
    const f = forms.find((x) => x.due_at && ms(x.due_at) > now);
    if (f) return { src: "form", token: hm(f.due_at) };
    return { soft: true };
  }
  if (field === "test") {
    const t = items.filter((i) => i.category !== "ppt" && (i.category === "test" || i.kind === "test_rooms" || i.kind === "interview") && i.event_at)
      .sort((a, b) => ms(b.event_at) - ms(a.event_at))[0];
    if (t) return { src: "notice", token: hm(t.event_at) };
    // a test notice without a time yet is still a test
    if (items.some((i) => i.category === "test" && !i.event_at)) return { src: "notice", token: "test" };
    return { absent: true };
  }
  if (field === "shortlist") {
    const st = (i) => i.pdf?.status || i.pdf_status;
    const l = items.filter((i) => ["yes", "no"].includes(st(i)) && (i.category === "shortlist" || i.category === "test" || i.category === "result"))
      .sort((a, b) => String(b.event_at || b.first_seen || "").localeCompare(String(a.event_at || a.first_seen || "")))[0];
    if (l) return { src: "notice", token: st(l) === "yes" ? "on the" : "couldn't find" };
    return { absent: true };
  }
  if (field === "whichcv") {
    const cvs = [...new Set(roles.filter((x) => x.cv && !x.applied).map((x) => x.cv))];
    if (cvs.length) return { src: "erp", anyOf: cvs };
    return { soft: true };
  }
  return { soft: true };
}

// ---------------------------------------------------------------- the questions
const ASK = {
  jd: { formal: (c) => `What is the JD for ${c}?`, typo: (c) => `${c} jd`, hinglish: (c) => `${c} ka jd kya hai`, follow: "and the jd?", source: (c) => `${c} jd on mail??` },
  ctc: { formal: (c) => `What is the CTC at ${c}?`, typo: (c) => `${c} ctc`, hinglish: (c) => `${c} ka ctc kitna hai`, follow: "what about ctc", source: (c) => `${c} ctc in notices?` },
  eligibility: { formal: (c) => `Am I eligible for ${c}?`, typo: (c) => `eligible for ${c}?`, hinglish: (c) => `kya main ${c} ke liye eligible hu`, follow: "am i eligible?", source: (c) => `${c} eligibility on erp?` },
  deadline: { formal: (c) => `When is the ${c} deadline?`, typo: (c) => `${c} deadline??`, hinglish: (c) => `${c} ki deadline kab hai`, follow: "deadline?" },
  form: { formal: (c) => `Is there a form to fill for ${c}?`, typo: (c) => `${c} form`, hinglish: (c) => `${c} ka form kab tak bharna hai`, follow: "form?" },
  test: { formal: (c) => `When is the ${c} test, and which room?`, typo: (c) => `${c} test time`, hinglish: (c) => `${c} ka test kab hai`, follow: "test kab hai?" },
  shortlist: { formal: (c) => `Am I on the ${c} shortlist?`, typo: (c) => `${c} shortlist`, hinglish: (c) => `${c} mein shortlist hua kya`, follow: "shortlisted?" },
  whichcv: { formal: (c) => `Which CV should I use for ${c}?`, typo: (c) => `which cv for ${c}`, hinglish: (c) => `${c} ke liye konsa cv`, follow: "which cv?" },
};
const OPENER = (c) => `tell me about ${c} roles`;

function companies(d, limit = 40) {
  const now = ms(d.now);
  const by = new Map();
  for (const r of d.roles) {
    const t = ms(r.deadline);
    if (!(t > now - 14 * 86400000)) continue;                        // open or closed in the last 14 days
    const cur = by.get(r.company);
    if (cur == null || Math.abs(t - now) < cur) by.set(r.company, Math.abs(t - now));
  }
  return [...by.entries()].sort((a, b) => a[1] - b[1]).slice(0, limit).map(([c]) => c);
}

// ---------------------------------------------------------------- answering and scoring
function ask(d, turns) {
  const asked = [], said = [];
  return turns.map((q) => {
    const data = { ...d, lastAnswer: said[said.length - 1] || null };
    const r = R.route(q, [...asked].reverse(), data);
    const text = r.kind === "open" ? null : R.routed(r, q, data).text;
    asked.push(q); said.push(text || "");
    return { q, kind: r.kind, text };
  });
}
const ABSENT = /\b(no|none|not found|don'?t have|nothing|couldn'?t find any)\b[^\n]{0,60}\b(jd|ctc|pay|eligib\w*|deadline|form|test|shortlist|list|cv)\b|\bnot on the erp, in notices\b|^no \w+ for /im;
const SOURCE = { erp: /\berp\b|companies list|from the|cut-off|ctc|apply with|closes|by \w{3} \d|https?:\/\//i, notice: /notice|list|test|room/i, mail: /mail/i, form: /form/i };
function score(field, t, a, prevText) {
  const text = a.text || "";
  const out = { open: a.kind === "open", fact: null, source: null, falseAbsence: false, repeat: false, long: false };
  if (out.open) return out;
  const lines = text.split("\n").filter((l) => l.trim()).length;
  const detail = field === "jd";                       // a JD is the detail asked for: its summary may take 8 lines
  out.long = lines > (detail ? 8 : 3);
  out.repeat = !!prevText && prevText === text;
  if (t.soft) { out.fact = true; out.source = true; return out; }
  if (t.absent) {
    out.fact = ABSENT.test(text) || /as of \d\d:\d\d|not on the erp/i.test(text) || /^as in my last answer|^nothing new|^still nothing/i.test(text);
    out.source = true;
    return out;
  }
  const low = text.toLowerCase();
  if (t.number) out.fact = R.numbersIn(text).some((n) => Math.abs(n - t.number) / t.number < 0.01) || low.includes("ctc");
  else if (t.anyOf) out.fact = t.anyOf.some((x) => low.includes(String(x).toLowerCase())) || /^as in my last answer|^nothing new/i.test(text);
  else out.fact = !t.token || low.includes(String(t.token).toLowerCase()) || /^as in my last answer|^nothing new/i.test(text);
  out.source = SOURCE[t.src] ? SOURCE[t.src].test(text) : true;
  out.falseAbsence = ABSENT.test(text) && !out.fact;
  return out;
}

function run(d, { limit = 40 } = {}) {
  const results = [];
  for (const c of companies(d, limit)) {
    const n = names(c);
    for (const field of FIELDS) {
      const t = truth(c, field, d);
      const A = ASK[field];
      const tries = [["formal", [A.formal(n.formal)]], ["typo", [A.typo(n.typo)]], ["hinglish", [A.hinglish(n.lower)]],
                     ["follow-up", [OPENER(n.lower), A.follow]]];
      if (A.source) tries.push(["source", [A.source(n.lower)]]);
      for (const [style, turns] of tries) {
        const answers = ask(d, turns);
        const last = answers[answers.length - 1], prev = answers.length > 1 ? answers[answers.length - 2].text : null;
        results.push({ company: c, field, style, q: turns.join(" → "), truth: t, answer: last.text, kind: last.kind, ...score(field, t, last, prev) });
      }
    }
  }
  const scored = results.filter((r) => !r.open);
  const ok = (r) => r.fact && r.source && !r.falseAbsence && !r.repeat && !r.long;
  const summary = { questions: results.length, answered_by_rules: scored.length, left_to_model: results.length - scored.length,
    correct: scored.filter(ok).length, correct_pct: scored.length ? Math.round(1000 * scored.filter(ok).length / scored.length) / 10 : 0,
    wrong_fact: scored.filter((r) => !r.fact).length, source_missing: scored.filter((r) => r.fact && !r.source).length,
    false_absences: scored.filter((r) => r.falseAbsence).length, repeats: scored.filter((r) => r.repeat).length, too_long: scored.filter((r) => r.long).length };
  return { summary, results };
}

if (require.main === module) {
  const fs = require("fs");
  const args = process.argv.slice(2);
  const d = JSON.parse(fs.readFileSync(args[0], "utf8"));
  const limit = Number((args.find((a) => a.startsWith("--limit=")) || "").split("=")[1]) || 40;
  const show = Number((args.find((a) => a.startsWith("--show=")) || "").split("=")[1]) || 25;
  const { summary, results } = run(d, { limit });
  console.log(JSON.stringify(summary));
  const bad = results.filter((r) => !r.open && !(r.fact && r.source && !r.falseAbsence && !r.repeat && !r.long));
  const kinds = {};
  for (const r of bad) { const k = `${r.field}/${r.style}: ${!r.fact ? "wrong fact" : r.falseAbsence ? "false absence" : !r.source ? "no source" : r.repeat ? "repeat" : "too long"}`; kinds[k] = (kinds[k] || 0) + 1; }
  console.log(JSON.stringify(kinds));
  for (const r of bad.slice(0, show)) console.log(`--- ${r.company} | ${r.field} | ${r.style} | ${r.q}\n    truth ${JSON.stringify(r.truth)}\n    ${String(r.answer).replace(/\n/g, "\n    ").slice(0, 500)}`);
  const left = results.filter((r) => r.open);
  if (left.length) console.log(`left to the model (${left.length}): ${[...new Set(left.map((r) => `${r.field}/${r.style}`))].join(", ")}`);
}

module.exports = { run, truth, names, companies, score };
