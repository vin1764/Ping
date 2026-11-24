// The 30 hurried-student conversations (evals/followups/hurried.json) through the rules, before and with the reading
// the model is meant to give: the rules with the right reading must get them right (the model's own reading is scored
// by evals/followups/run.js with eval keys only).
const { test } = require("node:test");
const assert = require("node:assert");
const S = require("../../evals/followups/score.js");
const data = require("../../evals/generated/demo_data.js")();
const spec = require("../../evals/followups/hurried.json");

test("30 hurried-student conversations: the rules with the intended reading", async () => {
  const before = [], gold = [];
  for (const c of spec.conversations) {
    before.push(await S.run(spec, c, data, "before"));
    gold.push(await S.run(spec, c, data, "gold"));
  }
  const b = S.summary(before), g = S.summary(gold);
  console.log(`before (rules alone): ${b.ok}/${b.turns} (${b.pct}%), follow-ups ${b.followups_ok}/${b.followups} (${b.followups_pct}%)`);
  console.log(`with the intended reading: ${g.ok}/${g.turns} (${g.pct}%), follow-ups ${g.followups_ok}/${g.followups} (${g.followups_pct}%)`);
  const bad = gold.flat().filter((t) => !t.ok);
  for (const t of bad) console.log(`  FAIL "${t.q}" (as "${t.asked_as}"): ${t.why.join("; ")}\n    ${t.text.split("\n")[0].slice(0, 160)}`);
  assert.ok(g.pct >= 95, `with the right reading the rules must answer: ${g.pct}%`);
  assert.ok(g.pct >= b.pct);
});
