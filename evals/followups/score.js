// Scores a conversation's turns (evals/followups/*.json): the answer names the company meant, answers the fact asked,
// and never "Which company?" / "I don't have …". Modes: "before" (the rules alone, as before 24 Nov), "gold" (the
// rules with the intended reading filled in), "model" (with a reading from understand(): eval keys only).
const R = require("../../supabase/functions/_shared/answer_rules.js");
const U = require("../../supabase/functions/_shared/understand.js");

function check(spec, turn, text) {
  const t = String(text || ""), low = t.toLowerCase();
  const why = [];
  if (turn.company) {
    const name = turn.company.toLowerCase(), first = name.split(/\s+/)[0];
    if (!low.includes(name) && !(first.length >= 4 && low.includes(first))) why.push(`doesn't name ${turn.company}`);
  }
  const says = spec.fact_says[turn.fact];
  if (says && !new RegExp(says, "i").test(t)) why.push(`doesn't answer ${turn.fact}`);
  for (const n of spec.never) if (low.includes(n.toLowerCase())) why.push(`says "${n}"`);
  return why;
}

// one conversation; read(turn, asked, said) -> Promise<reading|null> for mode "model"
async function run(spec, conv, data, mode, read) {
  const asked = [], said = [], out = [];
  for (const turn of conv.turns) {
    const d = { ...data, lastAnswer: said[said.length - 1] || null };
    let q = turn.q, reading = null, ms = 0, fell = false;
    if (mode === "gold") reading = { company: turn.company, role: null, fact: turn.fact, source: turn.source || "any" };
    if (mode === "model") {
      const t0 = Date.now();
      const r = await read(turn, asked, said);
      ms = Date.now() - t0; reading = r?.u || null; fell = !reading;
    }
    if (reading) q = U.augment(turn.q, reading, d, R);
    const r = R.route(q, [...asked].reverse(), d);
    const text = r.kind === "open" ? `(couldn't tell) ${r.why || ""}` : R.routed(r, q, d).text;
    const why = check(spec, turn, text);
    out.push({ q: turn.q, asked_as: q, followup: turn.followup, ok: !why.length, why, text, ms, fell, reading });
    asked.push(turn.q); said.push(text);
  }
  return out;
}

function summary(results) {
  const all = results.flat(), fu = all.filter((t) => t.followup);
  const pct = (xs) => (xs.length ? Math.round((100 * xs.filter((t) => t.ok).length) / xs.length) : 0);
  return { turns: all.length, ok: all.filter((t) => t.ok).length, pct: pct(all), followups: fu.length, followups_ok: fu.filter((t) => t.ok).length, followups_pct: pct(fu) };
}

module.exports = { check, run, summary };
