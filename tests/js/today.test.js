// The Today panel's model (dashboard/today.js), on a small made-up day.
const test = require("node:test");
const assert = require("node:assert");
const T = require("../../dashboard/today.js");

const NOW = Date.parse("2026-11-21T13:12:00+05:30");
const items = [
  { id: "t1", company: "Groww", category: "test", level: "always", event_at: "2026-11-21T15:00:00+05:30",
    title: "Groww test (Associate Product Manager) Sat 21 Nov 15:00.", details: { kind: "test", pdf: { status: "yes", details: { room: "NR 121" } } } },
  { id: "t2", company: "NexusOne", category: "test", level: "hidden", event_at: "2026-11-21T19:00:00+05:30", title: "NexusOne test (Data Engineer)", details: {} },
  { id: "t3", company: "Meesho", category: "test", level: "hidden", event_at: "2026-11-21T10:00:00+05:30", title: "Meesho test (SDE)",
    details: { kind: "test_rooms", pdf: { status: "no" } } },
  { id: "d1", company: "", category: "digest", level: "show", due_at: "2026-11-21T20:00:00+05:30", details: { kind: "application" } },
  { id: "f1", company: "BlackBuck", category: "todo", level: "show", due_at: "2026-11-21T18:00:00+05:30",
    title: "BlackBuck (Associate Manager): fill the form by Sat 21 Nov 18:00." },
  { id: "t4", company: "Swiggy", category: "test", level: "always", event_at: "2026-11-22T11:00:00+05:30", title: "Swiggy test (DS)", details: {} },
];
const roles = [
  { id: "r1", company: "Auro Group(www.AuroIM.com)", apply_end: "2026-11-21T20:00:00+05:30", mine: true },
  { id: "r2", company: "Axis Bank", apply_end: "2026-11-21T20:00:00+05:30", mine: true },
  { id: "r3", company: "AiPrise", apply_end: "2026-11-21T20:00:00+05:30", mine: false },
  { id: "r4", company: "Waterfly", apply_end: "2026-11-21T20:00:00+05:30", applied: true, mine: true },
  { id: "r5", company: "ICICI", apply_end: "2026-11-21T12:00:00+05:30", mine: true },
  { id: "r6", company: "Cars24", apply_end: "2026-11-22T18:00:00+05:30", mine: true },
  { id: "r7", company: "Ather", apply_end: "2026-11-22T18:00:00+05:30", mine: false },
];
const notices = [{ id: "n1", company: "HPCL", subject: "CV Submission", notice_time: "2026-11-21T12:34:00+05:30" },
                 { id: "n0", company: "Old", subject: "x", notice_time: "2026-11-20T12:34:00+05:30" }];
const runs = [{ id: "a", started_at: "2026-11-21T12:11:00+05:30", finished_at: "2026-11-21T12:13:00+05:30" }];
const day = (o = {}) => T.build({ items, roles, notices, runs, profile: {}, now: NOW, isMine: (r) => r.mine, inChat: (it) => it.level !== "hidden", ...o });

test("countdowns: format and colour", () => {
  const at = (min) => new Date(NOW + min * 60000).toISOString();
  assert.deepStrictEqual(T.countdown(at(108), NOW), { text: "in 1 h 48 m", level: "amber" });
  assert.deepStrictEqual(T.countdown(at(42), NOW), { text: "in 42 m", level: "red" });
  assert.deepStrictEqual(T.countdown(at(0.5), NOW), { text: "in 30 s", level: "red" });
  assert.deepStrictEqual(T.countdown(at(400), NOW), { text: "in 6 h 40 m", level: "plain" });
  assert.deepStrictEqual(T.countdown(at(240), NOW), { text: "in 4 h", level: "plain" });
  assert.deepStrictEqual(T.countdown(at(-1), NOW), { text: "over", level: "over" });
  assert.strictEqual(T.countdown(at(60 * 50), NOW).text, "in 2 days");
});

test("today, in time order; what's over at the bottom; notices one line each; the next check", () => {
  const d = day();
  const kinds = d.rows.map((r) => `${r.kind}:${r.title}${r.over ? " (over)" : ""}`);
  assert.deepStrictEqual(kinds, [
    "notice:HPCL", "check:Next ERP check", "test:Groww test", "todo:BlackBuck", "deadline:4 applications close",
    "test:Meesho test (over)", "deadline:1 application closes (over)"]);
  const groww = d.rows.find((r) => r.title === "Groww test");
  assert.strictEqual(groww.sub, "Associate Product Manager · 15:00 · room NR 121");
  assert.strictEqual(groww.status, "on");
  assert.deepStrictEqual(groww.target, { item: "t1" });
  assert.strictEqual(d.rows.find((r) => r.title === "Meesho test").status, "off");     // a list says you're not on it
  assert.ok(!d.rows.some((r) => /NexusOne/.test(r.title)));                          // not about you
  const dl = d.rows.find((r) => r.kind === "deadline" && !r.over);
  assert.strictEqual(dl.sub, "20:00 · 2 for you · 1 applied");
  assert.strictEqual(dl.names, "Auro Group, Axis Bank");                              // display names
  assert.deepStrictEqual(dl.target, { item: "d1" });                                  // the digest that lists them
  assert.strictEqual(d.rows.find((r) => r.kind === "check").sub, "14:11");
  assert.strictEqual(d.ahead, 3);                                                     // test, form, deadline
  assert.strictEqual(d.tomorrow.text, "Tomorrow: 1 test, 1 deadline");
  assert.ok(!d.empty);
});

test("an empty day says so, with the next check", () => {
  const d = T.build({ items: [], roles: [], notices: [], runs, now: NOW });
  assert.ok(d.empty);
  assert.strictEqual(d.emptyText, "Nothing scheduled today. Next check 14:11.");
  assert.strictEqual(d.tomorrow.text, "Tomorrow: nothing scheduled yet");
  assert.strictEqual(d.ahead, 0);
});

test("next check: every N minutes from the last start, moved past now", () => {
  assert.strictEqual(T.clock(T.nextCheck(runs, { check_every_minutes: 30 }, NOW)), "13:41");
  assert.strictEqual(T.nextCheck([], {}, NOW), null);
});
