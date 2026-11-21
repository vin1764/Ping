// The onboarding script (dashboard/onboarding.js): every branch, resume after a refresh, skip at every step.
const test = require("node:test");
const assert = require("node:assert/strict");
const ob = require("../../dashboard/onboarding.js");

// walk the flow like the page does: ask, answer, save, move on
function walk(answers, ctx = {}) {
  let step = "welcome", saved = {}, seen = [];
  for (let guard = 0; step !== "done" && guard < 30; guard++) {
    seen.push(step);
    const q = ob.question(step, { ...ctx, ...saved });
    assert.ok(q.lines.length, `a question at ${step}`);
    const a = ob.answer(step, answers[step] ? answers[step]({ ...ctx, ...saved }) : { skip: true }, { ...ctx, ...saved });
    saved = { ...saved, ...a.save, ...(a.ctxPatch || {}) };
    if (a.useDemo) return { seen, saved, useDemo: true };
    step = a.next;
  }
  return { seen, saved };
}

test("personal feed: every question, everything saved", () => {
  const r = walk({
    welcome: () => ({ value: "personal" }),
    education: (c) => (c.degree ? { text: "Computer Science and Engineering" } : { value: "B.Tech" }),
    targets: () => ({ text: "product and consulting roles" }),
    others: () => ({ value: "no" }),
    cv: () => ({ value: "later" }),
    schedule: () => ({ value: "30" }),
    hours: () => ({ text: "8 to 22" }),
    reminders: () => ({ value: "24" }),
    first_check: () => ({ value: "ok" }),
  });
  assert.deepEqual(r.seen, ["welcome", "education", "education", "targets", "others", "cv", "schedule", "hours", "reminders", "first_check"]);
  assert.equal(r.saved.feed_mode, "personal");
  assert.equal(r.saved.degree, "B.Tech");
  assert.equal(r.saved.department, "COMPUTER SCIENCE AND ENGINEERING");
  assert.equal(r.saved.list_other_roles, false);
  assert.equal(r.saved.check_every_minutes, 30);
  assert.equal(r.saved.check_from, "08:00");
  assert.equal(r.saved.check_to, "22:00");
  assert.equal(r.saved.reminder_hours, 24);
  assert.equal(r.saved.onboarding_step, "done");
});

test("targets go through Ask Ping, which saves them and answers 'Saved: ...'", () => {
  const a = ob.answer("targets", { text: "Data & analytics roles; not SDE" }, {});
  assert.equal(a.askPing, "my targets are Data & analytics roles; not SDE");
  assert.equal(a.next, "others");
  const q = ob.question("targets", {});
  assert.ok(q.chips.some((c) => c.insert === "Product & consulting roles"), "chips insert text to edit");
});

test("'Everything from the ERP' skips the questions about targets, others and CVs", () => {
  const r = walk({ welcome: () => ({ value: "all" }), schedule: () => ({ value: "120" }) });
  assert.deepEqual(r.seen, ["welcome", "education", "schedule", "hours", "reminders", "first_check"]);
  assert.equal(r.saved.feed_mode, "all");
  assert.equal(r.saved.check_every_minutes, 120);
});

test("Skip works at every step and always ends", () => {
  for (const step of ob.ORDER.filter((s) => s !== "done")) {
    const a = ob.answer(step, { skip: true }, {});
    assert.notEqual(a.next, step, `skip moves on from ${step}`);
    assert.equal(a.save.onboarding_step, a.next);
    const q = ob.question(step, {});
    if (!["first_check"].includes(step)) assert.ok(q.chips.some((c) => c.value === "__skip"), `Skip offered at ${step}`);
  }
  const r = walk({});
  assert.equal(r.saved.onboarding_step, "done");
});

test("a refresh resumes at the saved step; a finished or used profile doesn't start it", () => {
  assert.equal(ob.startStep({ onboarding_step: "hours" }), "hours");
  assert.equal(ob.shouldRun({ onboarding_step: "hours", department: "X" }, 5), true);   // unfinished: resume
  assert.equal(ob.shouldRun({ onboarding_step: "done" }, 0), false);
  assert.equal(ob.shouldRun({}, 0), true);                                                  // empty, no messages
  assert.equal(ob.shouldRun({}, 3), false);                                                 // already chatting
  assert.equal(ob.shouldRun({ targets: "x" }, 0), false);                                   // already set up
});

test("demo: the first bubble offers the demo profile, which finishes in one tap", () => {
  const q = ob.question("welcome", { demo: true });
  assert.equal(q.chips[0].label, "Use the demo profile");
  const a = ob.answer("welcome", { value: "__demo" }, { demo: true });
  assert.equal(a.useDemo, true);
  assert.deepEqual(a.save, { onboarding_step: "done" });
  assert.equal(ob.question("cv", { demo: true }).upload, false);   // the demo can't upload
});

test("hours typed in any common way", () => {
  assert.deepEqual(ob.answer("hours", { text: "7am to 11pm" }, {}).save, { check_from: "07:00", check_to: "23:00", onboarding_step: "reminders" });
  assert.deepEqual(ob.answer("hours", { value: "00:00-00:00" }, {}).save, { check_from: "00:00", check_to: "00:00", onboarding_step: "reminders" });
  assert.equal(ob.answer("hours", { text: "whenever" }, {}).next, "hours");   // not understood: asks again
});
