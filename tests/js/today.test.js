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

test("today, in time order; what's over at the bottom; notices one line each; no 'Next ERP check' row", () => {
  const d = day();
  const kinds = d.rows.map((r) => `${r.kind}:${r.title}${r.over ? " (over)" : ""}`);
  assert.deepStrictEqual(kinds, [
    "notice:HPCL", "test:Groww test", "todo:BlackBuck", "deadline:4 applications close",
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
  assert.ok(!d.rows.some((r) => r.kind === "check"));                               // the header says the next check
  assert.strictEqual(d.nextCheck, Date.parse("2026-11-21T14:11:00+05:30"));
  assert.strictEqual(d.ahead, 3);                                                     // test, form, deadline
  assert.strictEqual(d.tomorrow.text, "Tomorrow: 1 test, 1 deadline");
  assert.ok(!d.empty);
});

test("an empty day says so", () => {
  const d = T.build({ items: [], roles: [], notices: [], runs, now: NOW });
  assert.ok(d.empty);
  assert.strictEqual(d.emptyText, "Nothing scheduled today.");
  assert.strictEqual(d.tomorrow.text, "Tomorrow: nothing scheduled yet");
  assert.strictEqual(d.ahead, 0);
});

test("next check: every N minutes from the last start, moved past now", () => {
  assert.strictEqual(T.clock(T.nextCheck(runs, { check_every_minutes: 30 }, NOW)), "13:41");
  assert.strictEqual(T.nextCheck([], {}, NOW), null);
});

test("forms due at the same time are one row that opens into the single ones; tests stay one each", () => {
  const due = "2026-11-21T20:00:00+05:30";
  const forms = ["Piramal Capital & Housing Finance Ltd", "SLB", "LTM", "Auro Group(www.AuroIM.com)", "TATA AIG General Insurance"]
    .map((c, i) => ({ id: `f${i}`, company: c, category: "todo", level: "show", due_at: due, title: `${c} (Analyst): fill the form by Sat 21 Nov 20:00.` }));
  const tests = [0, 1].map((i) => ({ id: `t${i}`, company: `Co${i}`, category: "test", level: "always", event_at: due, title: `Co${i} test`, details: {} }));
  const d = T.build({ items: [...forms, ...tests], roles: [], notices: [], runs, now: NOW });
  const g = d.rows.filter((r) => r.kind === "todo");
  assert.strictEqual(g.length, 1);
  assert.strictEqual(g[0].title, "5 forms due 20:00");
  assert.strictEqual(g[0].names, "Piramal, SLB, LTM, Auro, …");
  assert.strictEqual(g[0].children.length, 5);
  assert.deepStrictEqual(g[0].children.find((c) => c.title === "SLB").target, { item: "f1" });
  assert.strictEqual(d.rows.filter((r) => r.kind === "test").length, 2);
  const one = T.build({ items: [forms[0]], roles: [], notices: [], runs, now: NOW }).rows.find((r) => r.kind === "todo");
  assert.ok(!one.children && /Piramal/.test(one.title));
});

test("a notice for several companies says which (first 3 + N) and what it asks", () => {
  const n = { notice_id: "9", company: "Multiple Companies", subject: "Additional requirement", notice_time: "2026-11-21T11:00:00+05:30",
    analysis: { kind: "form", targets: ["Piramal Capital", "1. SLB", "LTM", "Auro Group", "Axis Bank"].map((x) => ({ name: x, company: x.replace(/^1\. /, "") })),
                todos: [{ action: "apply", due: "2026-11-21T16:00:00+05:30" }, { action: "fill_form", due: "2026-11-21T16:00:00+05:30" }] } };
  const r = T.build({ items: [], roles: [], notices: [n], runs, now: NOW }).rows.find((x) => x.kind === "notice");
  assert.strictEqual(r.title, "Additional requirement");
  assert.strictEqual(r.names, "Piramal, SLB, LTM +2");
  assert.strictEqual(r.sub, "11:00 · fill a form by 16:00");
  assert.ok(!/several companies/.test(r.sub + r.names));
});

test("mail-only items on Today carry 'via email'; a mail interview is called one", () => {
  const its = [{ id: "m1", company: "Navi", category: "test", level: "always", event_at: "2026-11-21T16:00:00+05:30", title: "Navi interview: Sat 21 Nov 16:00.",
                 details: { via: "email", kind: "interview" } },
               { id: "m2", company: "Pine Labs", category: "todo", level: "show", due_at: "2026-11-21T17:00:00+05:30", title: "Pine Labs: fill the form by Sat 21 Nov 17:00.",
                 details: { via: "email", todo: { action: "fill_form" } } }];
  const d = T.build({ items: its, roles: [], notices: [], runs, now: NOW });
  const iv = d.rows.find((r) => r.kind === "test");
  assert.strictEqual(iv.title, "Navi interview");
  assert.strictEqual(iv.via, "email");
  assert.strictEqual(d.rows.find((r) => r.kind === "todo").via, "email");
});

// ---- the detail sheet behind a row
test("Open on ERP: the role's own ERP page with your roll, else the ERP's home and what to search for", () => {
  const r = { company: "Groww Pvt Ltd", jnf_id: 7, com_id: 12, yop: "2026-2027" };
  const direct = T.erpLink(r, "21AB12345");
  assert.equal(direct.direct, true);
  assert.match(direct.href, /^https:\/\/erp\.iitkgp\.ac\.in\/TrainingPlacementSSO\/TPJNFView\.jsp\?jnf_id=7&com_id=12&yop=2026-2027&user_type=SU&rollno=21AB12345$/);
  const noRoll = T.erpLink(r, null);
  assert.equal(noRoll.direct, false);
  assert.equal(noRoll.href, "https://erp.iitkgp.ac.in/IIT_ERP3/");
  assert.equal(T.erpLink({ company: "Groww" }, "21AB12345").direct, false);    // no ids: no direct link
});

test("form links: the notice's, the mail's, web links only, once each", () => {
  assert.deepEqual(T.formLinks({ details: { todo: { link: "https://forms.gle/a" }, forms: ["https://forms.gle/a", "mailto:x@y.z"],
                                            mail: { link: "https://example.com/f" }, mail_links: ["javascript:alert(1)"] } }),
                   ["https://forms.gle/a", "https://example.com/f"]);
  assert.deepEqual(T.formLinks({}), []);
});

test("card order: for you and not applied first (soonest first), applied next, others last; no marks stays in view", () => {
  const { top, others } = T.orderCards([
    { company: "O", mine: false, at: 1 }, { company: "A", mine: true, applied: true, at: 1 },
    { company: "Late", mine: true, at: 9 }, { company: "Soon", mine: true, at: 2 }, { company: "Test", mine: null, at: 5 }]);
  assert.deepEqual(top.map((c) => c.company), ["Soon", "Test", "Late", "A"]);
  assert.deepEqual(others.map((c) => c.company), ["O"]);
  const cards = [{ mine: true }, { mine: true, applied: true }, { mine: false }];
  assert.equal(T.filterCards(cards, "notapplied").length, 2);
  assert.equal(T.filterCards(cards, "foryou").length, 2);
  assert.equal(T.filterCards(cards, "all").length, 3);
});

test("sheet title: '55 applications close today 20:00 · 3 for you · 9 applied'", () => {
  const now = Date.parse("2026-11-21T12:00:00+05:30");
  assert.equal(T.sheetTitle({ n: 55, at: Date.parse("2026-11-21T20:00:00+05:30"), now, mine: 3, applied: 9 }),
               "55 applications close today 20:00 · 3 for you · 9 applied");
  assert.equal(T.sheetTitle({ n: 1, at: Date.parse("2026-11-22T17:00:00+05:30"), now, mine: 0, applied: 0 }),
               "1 application closes tomorrow 17:00");
});

test("Today rows carry what they stand for (role ids, item ids, the notice)", () => {
  const now = Date.parse("2026-11-21T12:00:00+05:30");
  const roles = [{ id: "r1", company: "A", effective_deadline: "2026-11-21T20:00:00+05:30" }, { id: "r2", company: "B", applied: true, effective_deadline: "2026-11-21T20:00:00+05:30" }];
  const m = T.build({ roles, now });
  const d = m.rows.find((r) => r.kind === "deadline");
  assert.deepEqual(d.roleIds, ["r1", "r2"]);
  assert.equal(d.applied, 1);
  assert.equal(d.total, 2);
});
