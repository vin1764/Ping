// The real-history follow-up cases (evals/followups/real_cases.js), on the demo data with a made-up chat.
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../supabase/functions/_shared/answer_rules.js");
const C = require("../../evals/followups/real_cases.js");
const data = require("../../evals/generated/demo_data.js")();

const at = (min) => new Date(Date.UTC(2026, 10, 24, 10, min)).toISOString();
const chat = [
  { role: "me", text: "navi ctc?", created_at: at(0) },
  { role: "ping", text: "Navi: CTC …", created_at: at(0) },
  { role: "me", text: "deadline?", created_at: at(5) },                                 // A: after a question
  { role: "ping", text: "…", created_at: at(5) },
  { role: "me", text: "and jd", created_at: at(9) },                                    // A: still Navi (last 3)
  { role: "ping", text: "…", created_at: at(9) },
  { role: "me", text: "eligible?", created_at: at(55) },                                // over 30 min: not a follow-up
  { role: "ping", text: "…", created_at: at(55) },
  { role: "me", text: "link?", created_at: at(57), reply_to: "ping-x",                  // A: a reply to an Ather card
    reply_quote: { sender: "Ping", text: "Ather Energy: fill the form by Fri 17:00" } },
  { role: "me", text: "ather energy jd", created_at: at(70) },
  { role: "me", text: "show me ather again", created_at: at(71) },                     // feedback: skipped
  { role: "me", text: "navi and ather ctc", created_at: at(80) },
  { role: "me", text: "cutoff?", created_at: at(81) },                                  // after two companies: skipped
];

test("A: real follow-ups after a question (last 3, within 30 min) and replies; never after two companies", () => {
  const { A } = C.build(R, data, chat);
  const got = A.map((c) => [c.q, R.shortName(c.company), c.how]);
  assert.deepStrictEqual(got, [["deadline?", "Navi", "after a question"], ["and jd", "Navi", "after a question"],
                               ["link?", "Ather Energy", "reply"]]);
  assert.match(A[2].ask, /^link\? Ather Energy$/);                                       // routed as the page does
  assert.ok(A[0].previous[0] === "navi ctc?" && A[0].history.length === 2);
});

test("B: your own questions with the company left out, about the nearest other company you asked about", () => {
  const { B } = C.build(R, data, chat);
  assert.ok(B.length >= 2, JSON.stringify(B));
  for (const c of B) {
    assert.strictEqual(R.matchCompanies(c.q, data).hits.length, 0, c.q);               // names no company now
    assert.notStrictEqual(R.matchCompanies(c.previous[0], data).hits[0].name, undefined);
  }
  const jd = B.find((c) => c.q === "jd");
  assert.ok(jd && R.shortName(jd.company) === "Navi", JSON.stringify(B.map((c) => [c.q, c.company])));
});
