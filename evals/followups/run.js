// The follow-up evals with the model's own reading (Admin > followup-evals). EVAL KEYS ONLY: GROQ_API_KEY_EVALS and
// GEMINI_API_KEY_EVALS; it refuses to run with nothing else set and never reads the live keys.
//   node evals/followups/run.js                      the 30 hurried-student conversations (demo data)
//   node evals/followups/run.js --real <data.json>   your real chat history's follow-ups, replayed after their real
//                                                    previous question (the file: facts + chat, written by the Admin
//                                                    task into the runner's temp dir, never committed)
// Prints before / after scores, the reading step's latency (median, worst) and how often it fell back to the rules
// alone, and how often the worded reply passed its check. Only scores and short masked questions are printed.
const R = require("../../supabase/functions/_shared/answer_rules.js");
const U = require("../../supabase/functions/_shared/understand.js");
const S = require("./score.js");

const GROQ = process.env.GROQ_API_KEY_EVALS || "", GEMINI = process.env.GEMINI_API_KEY_EVALS || "";
if (process.env.GROQ_API_KEY || process.env.GEMINI_API_KEY_LIVE) { console.error("refusing: a live key is set"); process.exit(2); }
if (!GROQ && !GEMINI) { console.error("no eval keys (GROQ_API_KEY_EVALS / GEMINI_API_KEY_EVALS)"); process.exit(2); }
const GROQ_MODEL = process.env.PING_GROQ_MODEL || "openai/gpt-oss-120b", LITE = "gemini-3.1-flash-lite";

async function call(prompt, ms) {
  const t = Date.now();
  if (GROQ) {
    try {
      const r = await fetch("https://api.groq.com/openai/v1/chat/completions", { method: "POST", signal: AbortSignal.timeout(ms),
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${GROQ}` },
        body: JSON.stringify({ model: GROQ_MODEL, temperature: 0.2, max_tokens: 700, reasoning_effort: "low", include_reasoning: false,
                               messages: [{ role: "user", content: prompt }] }) });
      if (r.ok) { const o = await r.json(); const text = o?.choices?.[0]?.message?.content?.trim(); if (text) return { text, model: "groq" }; }
    } catch (_) {}
  }
  const left = ms - (Date.now() - t);
  if (GEMINI && left > 400) {
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${LITE}:generateContent`, { method: "POST",
        signal: AbortSignal.timeout(left), headers: { "Content-Type": "application/json", "x-goog-api-key": GEMINI },
        body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }], generationConfig: { temperature: 0, maxOutputTokens: 700 } }) });
      if (r.ok) { const o = await r.json(); const text = o?.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("").trim(); if (text) return { text, model: "gemini-lite" }; }
    } catch (_) {}
  }
  return { error: "no answer" };
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : 0; };
const mask = (q) => String(q).replace(/\b\d{2}[A-Z]{2}\d{5}\b/g, "▒").slice(0, 60);

async function hurried() {
  const data = require("../generated/demo_data.js")();
  const spec = require("./hurried.json");
  const before = [], after = [], lat = [], composed = [];
  for (const c of spec.conversations) {
    before.push(await S.run(spec, c, data, "before"));
    const turns = [];
    const res = await S.run(spec, c, data, "model", async (turn, asked, said) => {
      const history = asked.flatMap((q, i) => [{ role: "me", text: q }, { role: "ping", text: said[i] }]);
      const r = await U.understand({ question: turn.q, turns: history, data, Rules: R, call: (p) => call(p, 3000), capMs: 3000 });
      lat.push(r.ms);
      await sleep(400);                                     // the eval key's per-minute limit
      return r;
    });
    for (const t of res) {                                  // the worded reply and its check, on each answer
      const w = await U.compose({ question: t.q, answer: t.text, data, companyNames: R.entities(data).map((e) => e.name), call: (p) => call(p, 2500), capMs: 2500 });
      composed.push(w);
      await sleep(400);
    }
    after.push(res);
  }
  return { before: S.summary(before), after: S.summary(after), lat, fell: after.flat().filter((t) => t.fell).length, turns: after.flat().length,
           composed, fails: after.flat().filter((t) => !t.ok) };
}

// your real history (evals/followups/real_cases.js): A your real follow-ups, B your own questions with the company left
// out. Each is answered as Ask Ping would: rules alone (before), and with the model steps on (after: the model reads
// the question, the rules answer, the model words it and the check keeps or drops the wording). The added time is the
// reading plus the wording, per question.
async function real(file) {
  const fs = require("fs");
  const C = require("./real_cases.js");
  const { data, chat } = JSON.parse(fs.readFileSync(file, "utf8"));
  const { A, B } = C.build(R, data, chat);
  const spec = { fact_says: {}, never: ["Which company", "I don't have", "couldn't tell", "not sure what"] };
  const names = R.entities(data).map((e) => e.name);
  const out = [];
  for (const c of [...A, ...B]) {
    const d = { ...data, lastAnswer: null };
    const turn = { company: c.company, fact: null };
    const rb = R.route(c.ask, c.previous, d);
    const tb = rb.kind === "open" ? "(couldn't tell)" : R.routed(rb, c.ask, d).text;
    const u = await U.understand({ question: c.q, turns: c.history, data, Rules: R, call: (p) => call(p, 3000), capMs: 3000 });
    await sleep(400);
    const q = u.u ? U.augment(c.ask, u.u, d, R) : c.ask;
    const ra = R.route(q, c.previous, d);
    let ta = ra.kind === "open" ? "(couldn't tell)" : R.routed(ra, q, d).text;
    let w = { ms: 0, used: false, why: "not run" };
    if (ra.kind !== "open" && ra.kind !== "recheck") {
      w = await U.compose({ question: c.q, answer: ta, data: d, companyNames: names, call: (p) => call(p, 2500), capMs: 2500 });
      if (w.used) ta = w.text;
      await sleep(400);
    }
    const why = S.check(spec, turn, ta);
    out.push({ ...c, okB: !S.check(spec, turn, tb).length, okA: !why.length, why, read: u, worded: w, added: (u.ms || 0) + (w.ms || 0) });
  }
  return out;
}

(async () => {
  const realFile = process.argv.indexOf("--real") > 0 ? process.argv[process.argv.indexOf("--real") + 1] : null;
  if (realFile) {
    const rs = await real(realFile);
    const pct = (n, d) => `${n}/${d} (${Math.round(100 * n / Math.max(1, d))}%)`;
    const line = (label, xs) => console.log(`  ${label}: rules alone ${pct(xs.filter((x) => x.okB).length, xs.length)}, ` +
      `with the model steps ${pct(xs.filter((x) => x.okA).length, xs.length)}`);
    const A = rs.filter((x) => x.group === "A"), B = rs.filter((x) => x.group === "B");
    console.log(`REAL HISTORY: ${rs.length} follow-ups (A: ${A.length} real follow-ups, ${A.filter((x) => x.how === "reply").length} of them replies; ` +
                `B: ${B.length} of your own questions with the company left out)`);
    line("A, your real follow-ups", A); line("B, company left out", B); line("all", rs);
    const added = rs.map((x) => x.added), read = rs.map((x) => x.read.ms || 0), worded = rs.filter((x) => x.worded.ms).map((x) => x.worded.ms);
    const by = {}; for (const x of rs) { const k = x.read.model || "none (fell back)"; by[k] = (by[k] || 0) + 1; }
    console.log(`  added time per question (reading + wording): median ${median(added)} ms, worst ${Math.max(0, ...added)} ms`);
    console.log(`    reading: median ${median(read)} ms; wording: median ${median(worded)} ms; who answered the reading: ${JSON.stringify(by)}`);
    console.log(`  fell back to the rules alone: reading ${rs.filter((x) => x.read.fell).length}/${rs.length}; wording kept ${rs.filter((x) => x.worded.used).length}/${rs.filter((x) => x.worded.why !== "not run" && x.worded.why !== "short").length}`);
    const better = rs.filter((x) => x.okA && !x.okB), worse = rs.filter((x) => !x.okA && x.okB);
    console.log(`  the model steps fixed ${better.length} and broke ${worse.length}`);
    for (const x of worse.slice(0, 10)) console.log(`  BROKE [${x.group}] "${mask(x.q)}" (about ${x.company}): ${x.why.join("; ")}`);
    for (const x of rs.filter((x) => !x.okA && !x.okB).slice(0, 10)) console.log(`  BOTH MISS [${x.group}] "${mask(x.q)}" (about ${x.company}): ${x.why.join("; ")}`);
    // the rule for turning PING_MODEL_STEPS on: beats the rules alone on this replay and adds at most 1.5 s median,
    // measured with Groq first, then flash-lite, as live runs it
    const okA = (xs) => xs.filter((x) => x.okA).length, okB = (xs) => xs.filter((x) => x.okB).length;
    const reasons = [];
    if (!GROQ) reasons.push("no Groq eval key: live calls Groq first, so this run doesn't measure what live would do");
    if (okA(rs) <= okB(rs)) reasons.push(`doesn't beat the rules alone (${okA(rs)} vs ${okB(rs)})`);
    if (median(added) > 1500) reasons.push(`adds ${median(added)} ms median (over 1500)`);
    console.log(reasons.length ? `VERDICT: keep PING_MODEL_STEPS off: ${reasons.join("; ")}` : "VERDICT: turn PING_MODEL_STEPS on");
    return;
  }
  const h = await hurried();
  console.log(`HURRIED STUDENTS: 30 conversations, ${h.turns} turns`);
  console.log(`  before (rules alone): ${h.before.ok}/${h.before.turns} (${h.before.pct}%), follow-ups ${h.before.followups_ok}/${h.before.followups} (${h.before.followups_pct}%)`);
  console.log(`  after (model reading + rules): ${h.after.ok}/${h.after.turns} (${h.after.pct}%), follow-ups ${h.after.followups_ok}/${h.after.followups} (${h.after.followups_pct}%)`);
  console.log(`  reading step: median ${median(h.lat)} ms, worst ${Math.max(0, ...h.lat)} ms; fell back to the rules alone ${h.fell}/${h.turns} (${Math.round(100 * h.fell / h.turns)}%)`);
  const used = h.composed.filter((c) => c.used), short = h.composed.filter((c) => c.why === "short");
  console.log(`  worded reply: kept ${used.length}/${h.composed.length - short.length} (the rest failed the facts check or timed out: the rules' answer was sent); median ${median(h.composed.filter((c) => c.ms).map((c) => c.ms))} ms, worst ${Math.max(0, ...h.composed.map((c) => c.ms))} ms`);
  const whys = {}; for (const c of h.composed.filter((c) => !c.used && c.why !== "short")) { const k = String(c.why).replace(/".*"/, '"…"').slice(0, 40); whys[k] = (whys[k] || 0) + 1; }
  console.log(`  why a worded reply was dropped: ${JSON.stringify(whys)}`);
  for (const t of h.fails.slice(0, 15)) console.log(`  FAIL "${t.q}" (as "${t.asked_as}"): ${t.why.join("; ")}`);
})();
