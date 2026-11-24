// The self-generated Ask Ping evals (evals/generated/generate.js) on the demo snapshot, on every change: every
// company with an open or recent role, eight facts, five phrasings each, scored against the data itself.
const test = require("node:test");
const assert = require("node:assert");
const G = require("../../evals/generated/generate.js");
const demoData = require("../../evals/generated/demo_data.js");

test("generated evals on the demo: right fact and source, no false absence, no repeat, short", () => {
  const { summary, results } = G.run(demoData());
  const bad = results.filter((r) => !r.open && !(r.fact && r.source && !r.falseAbsence && !r.repeat && !r.long));
  const show = bad.slice(0, 5).map((r) => `${r.company} | ${r.field} | ${r.style} | ${r.q}\n${r.answer}`).join("\n---\n");
  assert.ok(summary.questions >= 1000, `questions: ${summary.questions}`);
  assert.strictEqual(summary.false_absences, 0, show);
  assert.strictEqual(summary.repeats, 0, show);
  assert.ok(summary.correct_pct >= 99, `${summary.correct_pct}% correct\n${show}`);
});
