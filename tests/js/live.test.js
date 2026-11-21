// Live updates without page code (dashboard/live.js): progress steps, the run bubble's words, what's in the thread.
const test = require("node:test");
const assert = require("node:assert");
const L = require("../../dashboard/live.js");

const NOW = "2026-11-21T12:17:30+05:30";
const run = (o) => ({ id: "x", trigger: "manual", requested_at: "2026-11-21T12:15:00+05:30", ...o });

test("steps follow the run: queued -> logging in -> reading -> done", () => {
  const s = (stage) => L.steps(run({ stage })).map((x) => x.state).join(",");
  assert.strictEqual(s("queued"), "now,todo,todo,todo");
  assert.strictEqual(s("logging in"), "done,now,todo,todo");
  assert.strictEqual(s("reading notices"), "done,done,now,todo");
  assert.strictEqual(s("reading PDFs"), "done,done,now,todo");
  assert.strictEqual(s("done"), "done,done,done,done");
});

test("what the bubble says while it runs, when it's done, when it fails", () => {
  const going = L.describe(run({ stage: "reading notices", started_at: "2026-11-21T12:15:20+05:30" }), [], NOW);
  assert.deepStrictEqual([going.state, going.line], ["active", "Checking the ERP now… usually takes 1–2 minutes"]);
  const runs = [{ id: "a", finished_at: "2026-11-21T11:43:00+05:30", stage: "done" }];
  const two = L.describe(run({ stage: "done", status: "ok", finished_at: "2026-11-21T12:17:05+05:30", new_items: 2 }), runs, NOW);
  assert.strictEqual(two.line, "Done at 12:17 — 2 new items");
  const none = L.describe(run({ stage: "done", status: "ok", started_at: "2026-11-21T12:15:20+05:30",
                                finished_at: "2026-11-21T12:17:05+05:30", new_items: 0 }), runs, NOW);
  assert.strictEqual(none.line, "Done — nothing new since 11:43");
  const failed = L.describe(run({ stage: "failed", status: "failed: no_otp", note: "Couldn't get into the ERP this time (no_otp); that happens." }), runs, NOW);
  assert.deepStrictEqual([failed.state, failed.line], ["failed", "Couldn't get into the ERP this time (no_otp); that happens."]);
  const slow = L.describe(run({ stage: "queued", requested_at: "2026-11-21T12:00:00+05:30" }), [], NOW);
  assert.strictEqual(slow.line, "Still waiting for GitHub to start the check…");
  assert.strictEqual(L.describe(run({ stage: "done", demo: true, finished_at: NOW }), [], NOW).line, "Demo: sample data, nothing new to fetch");
  assert.strictEqual(L.describe(run({ stage: "done", demo: true, finished_at: NOW, new_items: 1 }), [], NOW).line,
    "Demo: found 1 new from the snapshot's last check");
});

test("in the thread: every Check now; an hourly run only when it brought something new", () => {
  assert.ok(L.inThread(run({ stage: "queued" }), NOW));
  assert.ok(!L.inThread({ trigger: "schedule", stage: "done", new_items: 0 }, NOW));
  assert.ok(L.inThread({ trigger: "schedule", stage: "done", new_items: 3 }, NOW));
  assert.ok(!L.inThread({ trigger: "schedule", stage: "reading notices" }, NOW));
  assert.ok(!L.inThread({ trigger: "manual", stage: null }, NOW));          // rows from before live updates
});

test("a stuck run stops counting as running; polling is faster while one runs", () => {
  assert.ok(L.isActive(run({ stage: "logging in" }), NOW));
  assert.ok(!L.isActive(run({ stage: "logging in", requested_at: "2026-11-21T11:00:00+05:30" }), NOW));
  assert.strictEqual(L.pollEvery(true), 15000);
  assert.strictEqual(L.pollEvery(false), 60000);
  assert.strictEqual(L.buttonLabel(run({ stage: "reading PDFs" }), NOW), "Checking… reading PDFs");
  assert.strictEqual(L.buttonLabel(run({ stage: "done" }), NOW), "Check now");
});

test("checks in a row that found nothing: one thin line that updates in place; a find keeps its bubble", () => {
  const r = (id, fin, n = 0, extra = {}) => ({ id, trigger: "manual", stage: "done", status: "ok", requested_at: fin, started_at: fin,
                                              finished_at: fin, new_items: n, ...extra });
  const hourly = r("h0", "2026-11-21T02:53:00+05:30", 0, { trigger: "schedule" });
  const a = r("a", "2026-11-21T03:05:00+05:30"), b = r("b", "2026-11-21T03:18:00+05:30");
  const found = r("c", "2026-11-21T03:40:00+05:30", 2), d = r("d", "2026-11-21T03:55:00+05:30");
  const runs = [hourly, a, b, found, d];
  const e = (run) => ({ kind: "run", at: run.requested_at, run });
  const out = L.collapseQuiet([e(a), e(b), e(found), { kind: "me", at: "2026-11-21T03:50:00+05:30" }, e(d)], runs, Date.parse("2026-11-21T04:00:00+05:30"));
  assert.deepStrictEqual(out.map((x) => x.kind), ["quiet", "run", "me", "quiet"]);
  assert.strictEqual(out[0].line, "Checked 03:18 · nothing new since 02:53");
  assert.strictEqual(out[0].key, "run:a");                       // the line keeps the first check's place and key
  assert.strictEqual(out[3].line, "Checked 03:55 · nothing new since 03:40");
  const going = { ...d, stage: "reading notices", finished_at: null };
  assert.strictEqual(L.collapseQuiet([e(going)], runs, Date.parse("2026-11-21T03:56:00+05:30"))[0].kind, "run");   // still going: its bubble
  const failed = { ...d, stage: "failed", status: "failed: erp" };
  assert.strictEqual(L.collapseQuiet([e(failed)], runs, Date.now())[0].kind, "run");
});
