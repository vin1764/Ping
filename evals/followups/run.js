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

async function real(file) {
  const fs = require("fs");
  const { data, chat } = JSON.parse(fs.readFileSync(file, "utf8"));
  const me = chat.filter((m) => m.role === "me");
  const cases = [];
  for (let i = 1; i < chat.length; i++) {
    const m = chat[i];
    if (m.role !== "me") continue;
    const prev = [...chat.slice(0, i)].reverse().find((x) => x.role === "me");
    if (!prev || Date.parse(m.created_at) - Date.parse(prev.created_at) > 30 * 60000) continue;
    if (R.matchCompanies(m.text, data).hits.length || R.feedbackLike(m.text)) continue;          // names its company: not a follow-up
    const topic = R.matchCompanies(prev.text, data).hits;
    if (topic.length !== 1) continue;                                                           // the previous question's company
    const history = chat.slice(Math.max(0, i - 12), i).map((x) => ({ role: x.role, text: x.text }));
    cases.push({ q: m.text, prev: prev.text, company: topic[0].name, history });
  }
  const spec = { fact_says: {}, never: ["Which company", "I don't have", "couldn't tell", "not sure what"] };
  let bOk = 0, aOk = 0, fell = 0; const lat = [], fails = [];
  for (const c of cases) {
    const d = { ...data, lastAnswer: null };
    const rb = R.route(c.q, [c.prev], d);
    const tb = rb.kind === "open" ? "(couldn't tell)" : R.routed(rb, c.q, d).text;
    const turn = { company: c.company, fact: null };
    const okB = !S.check(spec, turn, tb).length;
    const u = await U.understand({ question: c.q, turns: c.history, data, Rules: R, call: (p) => call(p, 3000), capMs: 3000 });
    lat.push(u.ms); if (u.fell) fell++;
    const q = u.u ? U.augment(c.q, u.u, d, R) : c.q;
    const ra = R.route(q, [c.prev], d);
    const ta = ra.kind === "open" ? "(couldn't tell)" : R.routed(ra, q, d).text;
    const why = S.check(spec, turn, ta);
    if (okB) bOk++; if (!why.length) aOk++; else fails.push(`"${mask(c.q)}" after a ${c.company} question: ${why.join("; ")}`);
    await sleep(400);
  }
  return { cases: cases.length, bOk, aOk, lat, fell, fails };
}

(async () => {
  const realFile = process.argv.indexOf("--real") > 0 ? process.argv[process.argv.indexOf("--real") + 1] : null;
  if (realFile) {
    const r = await real(realFile);
    console.log(`REAL HISTORY: ${r.cases} follow-ups (a company-less question within 30 min of one about a company)`);
    console.log(`  before (rules alone): ${r.bOk}/${r.cases} (${Math.round(100 * r.bOk / Math.max(1, r.cases))}%)`);
    console.log(`  after (model reading + rules): ${r.aOk}/${r.cases} (${Math.round(100 * r.aOk / Math.max(1, r.cases))}%)`);
    console.log(`  reading step: median ${median(r.lat)} ms, worst ${Math.max(0, ...r.lat)} ms; fell back to the rules alone ${r.fell}/${r.cases}`);
    for (const f of r.fails.slice(0, 15)) console.log(`  FAIL ${f}`);
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
