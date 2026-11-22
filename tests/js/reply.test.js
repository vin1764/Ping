// Replying to a message: the quoted message is the topic (dashboard/reply.js). The five reply cases of
// evals/ask_ping/multiturn.json ("replies"), and the anchor of a digest / test alert / form line.
const test = require("node:test");
const assert = require("node:assert");
const P = require("../../dashboard/reply.js");
const R = require("../../supabase/functions/_shared/answer_rules.js");
const E = require("../../evals/ask_ping/multiturn.json");

const data = {
  now: new Date("2026-11-22T14:30:00+05:30"),
  roles: [{ id: "r1", company: "GROWW", designation: "APM", applied: true, cv: "Product CV" },
          { id: "r2", company: "Zeta", designation: "Business Analyst", applied: false, cv: "Analyst CV" },
          { id: "r3", company: "Slice", designation: "Product Analyst", applied: false, cv: null },
          { id: "r4", company: "FirstClub", designation: "Product Management", applied: true }],
  items: [
    { id: "digest:application:20261122T2000", category: "digest", due_at: "2026-11-22T20:00:00+05:30", role_ids: ["r1", "r2", "r3"],
      title: "3 applications (Groww, Zeta, Slice) close today 20:00", details: { kind: "application", list: [{ head: "For you", rows: [{ id: "r1" }, { id: "r2" }] }, { head: "", rows: [{ id: "r3" }] }] } },
    { id: "notice:1817:0", category: "shortlist", company: "FirstClub", notice_id: 1817, title: "You're on the FirstClub shortlist (Product Management).",
      role_ids: ["r4"], details: { kind: "shortlist", pdf: { status: "yes" } } },
    { id: "notice:1801:0", category: "test", company: "Pine Labs", event_at: "2026-11-23T10:00:00+05:30", notice_id: 1801,
      title: "You're on the Pine Labs test room list.", details: { kind: "test_rooms", venue: "Nalanda", pdf: { status: "yes", details: { room: "V2", slot_from_heading: "Slot 1" } } } },
    { id: "notice:1790:todo0", category: "todo", company: "Groww", title: "Groww (APM): fill the form by Sun 22 Nov 20:00.",
      details: { todo: { action: "fill_form" }, form: { key: "gform:abc" } } },
  ],
};
const item = (id) => data.items.find((i) => i.id === id);

for (const c of E.replies) {
  test(`${c.id}: reply to ${c.to} — "${c.q}"`, () => {
    const a = P.anchorOf(item(c.to), data);
    const out = P.answer(c.q, a, { isFilled: () => false, when: (v) => v });
    assert.ok(out, `no direct answer for ${c.q}`);
    if (c.recheck) assert.strictEqual(R.shortName(out.recheck), c.recheck);
    if (c.tick) assert.strictEqual(out.tick, c.tick);
    for (const m of c.must_contain || []) assert.ok((out.text || "").includes(m), `missing "${m}" in ${out.text}`);
    for (const m of c.must_not_contain || []) assert.ok(!(out.text || "").includes(m), `"${m}" in ${out.text}`);
  });
}

test("a reply that isn't answered directly carries the anchor to the router", () => {
  const a = P.anchorOf(item("notice:1817:0"), data);
  const ctx = P.context("what's the next step?", a);
  assert.match(ctx, /about: FirstClub/);
});
