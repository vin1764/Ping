const { test } = require("node:test");
const assert = require("node:assert");
const F = require("../../dashboard/forms.js");

const now = Date.parse("2026-11-21T12:00:00+05:30");
const when = (v) => new Date(v).toISOString().slice(5, 16);
const forms = [
  { key: "g1", company: "Groww", purpose: "additional requirement", due_at: "2026-11-21T20:00:00+05:30", sources: [{ type: "notice", id: "1791" }, { type: "mail", id: "m1" }, { type: "notice", id: "1796" }],
    deadline_history: [{ from: "2026-11-20T20:00:00+05:30", to: "2026-11-21T20:00:00+05:30" }] },
  { key: "p1", company: "Piramal Pharma", purpose: "registration", due_at: "2026-11-23T17:00:00+05:30", sources: [] },
  { key: "o1", company: "Old Co", purpose: "form", due_at: "2026-11-19T17:00:00+05:30", sources: [] },
  { key: "c1", company: "Closed Co", purpose: "test slot", due_at: "2026-11-25T17:00:00+05:30", closed: true, sources: [] },
  { key: "s1", company: "Soon Co", purpose: "form", due_at: "2026-11-22T10:00:00+05:30", sources: [] },
];

test("sections: due today, upcoming, past due (not filled), closed, filled", () => {
  const status = new Map([["o1", { filled: true, filled_at: "2026-11-19T10:00:00+05:30" }]]);
  const s = F.sections(forms, status, { now });
  assert.deepEqual(s.today.map((f) => f.key), ["g1"]);
  assert.deepEqual(s.upcoming.map((f) => f.key), ["s1", "p1"]);
  assert.deepEqual(s.past.map((f) => f.key), []);
  assert.deepEqual(s.closed.map((f) => f.key), ["c1"]);
  assert.deepEqual(s.filled.map((f) => f.key), ["o1"]);
  // search, For you, one deadline
  assert.deepEqual(F.sections(forms, status, { now, query: "piramal" }).upcoming.map((f) => f.key), ["p1"]);
  assert.equal(F.sections(forms, status, { now, only: "foryou", mineOf: (f) => f.key === "g1" }).upcoming.length, 0);
  assert.deepEqual(F.sections(forms, status, { now, at: Date.parse("2026-11-21T20:00:00+05:30") }).today.map((f) => f.key), ["g1"]);
});

test("badge: not filled, open, due within 24 h", () => {
  assert.equal(F.badge(forms, new Map(), now), 2);                                  // g1 (8 h) and s1 (22 h)
  assert.equal(F.badge(forms, new Map([["g1", { filled: true }]]), now), 1);
});

test("posted and moved lines", () => {
  assert.equal(F.postedLine(forms[0]), "posted 3 times: notice 1791, mail, notice 1796");
  assert.equal(F.movedLine(forms[0], when), "deadline moved 11-20T14:30 → 11-21T14:30");
  assert.equal(F.postedLine(forms[1]), "");
});

test("Ask Ping: which forms haven't I filled, did I fill X, mark X as filled", () => {
  const status = new Map([["s1", { filled: true, filled_at: "2026-11-21T09:00:00+05:30" }]]);
  const a = F.ask("which forms haven't I filled?", forms, status, { now, when });
  assert.match(a.text, /^2 forms not ticked yet:\n- Groww: additional requirement, due/);
  assert.match(a.text, /Piramal Pharma: registration/);
  assert.doesNotMatch(a.text, /Soon Co|Old Co|Closed Co/);
  assert.match(F.ask("did I fill the Groww form?", forms, status, { now, when }).text, /^Not ticked yet: the Groww additional requirement is due/);
  assert.match(F.ask("did I fill the soon co form", forms, status, { now, when }).text, /^Yes: you ticked/);
  const m = F.ask("mark the Piramal form as filled", forms, status, { now, when });
  assert.equal(m.tick, "p1");
  assert.match(m.text, /^Done: the Piramal Pharma registration is ticked as filled\./);
  assert.equal(F.ask("what's due tomorrow", forms, status, { now, when }), null);    // not about forms: the usual answers
});
