// Feedback said in the chat (answer_rules.js feedbackOf / applyFeedback / pinned): the 12 cases of
// evals/feedback/cases.json, then the lists they leave and how For you follows them.
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../supabase/functions/_shared/answer_rules.js");
const E = require("../../evals/feedback/cases.json");

const data = { now: new Date("2026-11-23T04:10:00+05:30"), roles: E.roles, items: [], notices: [] };

for (const c of E.cases) {
  test(`${c.id}: ${c.case}`, () => {
    const fb = R.feedbackOf(c.message, data, { anchorCompanies: c.reply ? E.reply.companies : [] });
    const w = c.want;
    if (w.none) return assert.strictEqual(fb, null);
    assert.ok(fb, "not read as feedback");
    if (w.ask) {
      assert.ok(fb.ask && fb.ask.chips.length >= 2, JSON.stringify(fb));
      assert.ok(!/deadline|applied|notice/i.test(fb.ask.text), "no status dump");
      return;
    }
    assert.strictEqual(fb.action, w.action);
    if (w.action === "undo") return;
    assert.strictEqual(fb.level, w.level, JSON.stringify(fb));
    if (w.name) assert.strictEqual(fb.name, w.name);
    if (w.roles) assert.deepStrictEqual(fb.roles.map((r) => r.id), w.roles);
    const line = R.feedbackLine(fb);
    assert.match(line, w.action === "hide" ? /^Got it, .+ won't show as For you anymore\. \[Undo\]\(#ask:undo\)$/ : /^Got it, .+ will show as For you\./);
  });
}

test("the lists: hide, show again, role level, and For you follows them", () => {
  const piramal = R.feedbackOf("piamal not relevantt for me", data, { anchorCompanies: E.reply.companies });
  let L = R.applyFeedback({}, piramal, E.roles);
  assert.deepStrictEqual(L.not_interested_companies, ["Piramal Finance"]);
  assert.strictEqual(R.pinned(E.roles[1], L), false);
  assert.strictEqual(R.pinned(E.roles[4], L), null);
  // a role shown again inside a hidden company wins over the company
  L = R.applyFeedback(L, { action: "show", level: "role", company: "Piramal Finance", roles: [{ id: "r3" }] }, E.roles);
  assert.strictEqual(R.pinned(E.roles[2], L), true);
  assert.strictEqual(R.pinned(E.roles[1], L), false);
  // "show piramal again": the hide is gone, and Ping's own marks decide again (no forced For you)
  L = R.applyFeedback(L, R.feedbackOf("show piramal again", data), E.roles);
  assert.deepStrictEqual(L.not_interested_companies, []);
  assert.strictEqual(R.pinned(E.roles[1], L), null);
  // "zeta is relevant" when it wasn't hidden: always For you
  L = R.applyFeedback(L, R.feedbackOf("zeta is relevant", data), E.roles);
  assert.strictEqual(R.pinned(E.roles[5], L), true);
  assert.match(R.describeLists(L, E.roles), /always For you: Zeta/);
});

test("a preference about role types stays a preference", () => {
  assert.strictEqual(R.feedbackOf("not interested in sde roles", data), null);
  assert.strictEqual(R.feedbackOf("what's due tonight", data), null);
});

test("a reply that is a statement, with the model down: one question with buttons", () => {
  const c = R.clarify("these look boring", E.reply.companies, data);
  assert.match(c.text, /^I'm not sure .* Hide one of these from For you\?/);
  assert.match(c.text, /\(#ask:hide%20Piramal%20Finance\)/);
  const one = R.clarify("piramal meh", E.reply.companies, data);
  assert.match(one.text, /^Hide Piramal Finance from For you\? \[Yes\]/);
});
