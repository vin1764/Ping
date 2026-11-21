/* Live updates, the parts without page code (tested in tests/js/live.test.js):
 * a run's progress steps, what its chat bubble says, which runs belong in the thread, how often to poll when the
 * Realtime socket is down, and the button's label.
 *
 * A run row (table runs): { id, trigger: "manual" | "schedule", stage, status, requested_at, started_at,
 *   finished_at, new_items, note }. Stages in order: queued, logging in, reading companies, reading notices,
 *   reading PDFs, saving, then done or failed.
 */
(function (root) {
  "use strict";
  const ACTIVE = ["queued", "logging in", "reading companies", "reading notices", "reading PDFs", "saving"];
  // what the bubble shows as steps: queued -> logging in -> reading companies/notices/PDFs -> done
  const STEPS = [
    { label: "queued", stages: ["queued"] },
    { label: "logging in", stages: ["logging in"] },
    { label: "reading companies, notices, PDFs", stages: ["reading companies", "reading notices", "reading PDFs", "saving"] },
    { label: "done", stages: ["done"] },
  ];
  const STALE_MS = 30 * 60000;        // a run that hasn't moved for 30 minutes isn't shown as running any more
  const QUEUED_SLOW_MS = 10 * 60000;  // GitHub hasn't started it after 10 minutes: say so

  const t = (v) => (v ? new Date(v).getTime() : 0);
  const hm = (v) => new Date(v).toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit" });
  const lastMove = (run) => Math.max(t(run.requested_at), t(run.started_at), t(run.finished_at));

  function isActive(run, now) {
    if (!run || !ACTIVE.includes(run.stage)) return false;
    return (now ? new Date(now).getTime() : Date.now()) - lastMove(run) < STALE_MS;
  }

  // [{label, state: "done" | "now" | "todo"}]
  function steps(run) {
    const at = STEPS.findIndex((s) => s.stages.includes(run.stage));
    return STEPS.map((s, i) => ({ label: s.label, state: run.stage === "failed" ? (i < Math.max(at, 1) ? "done" : "todo")
      : i < at || (run.stage === "done" && i === at) ? "done" : i === at ? "now" : "todo" }));
  }

  // the run before this one that finished (for "nothing new since 11:41")
  function previousDone(run, runs) {
    return (runs || []).filter((r) => r.id !== run.id && r.finished_at && t(r.finished_at) < (t(run.started_at) || t(run.requested_at) || Infinity))
      .sort((a, b) => t(b.finished_at) - t(a.finished_at))[0] || null;
  }

  // {kicker, line, steps|null, state: "active" | "done" | "failed"}
  function describe(run, runs, now) {
    const kicker = run.trigger === "manual" ? "Check now" : "Hourly check";
    if (isActive(run, now)) {
      const slow = run.stage === "queued" && (now ? new Date(now).getTime() : Date.now()) - t(run.requested_at) > QUEUED_SLOW_MS;
      return { kicker, state: "active", steps: steps(run),
               line: slow ? "Still waiting for GitHub to start the check…" : "Checking the ERP now… usually takes 1–2 minutes" };
    }
    if (run.stage === "failed" || (run.status || "").startsWith("failed")) {
      return { kicker, state: "failed", steps: null, line: run.note || "The check couldn't finish. I'll try again at the next hourly check." };
    }
    if (run.demo) return { kicker, state: "done", steps: null, line: "Demo: sample data, nothing new to fetch" };
    const n = Number(run.new_items) || 0;
    if (n > 0) return { kicker, state: "done", steps: null, line: `Done at ${hm(run.finished_at)} — ${n} new item${n === 1 ? "" : "s"}` };
    const prev = previousDone(run, runs);
    return { kicker, state: "done", steps: null, line: prev ? `Done — nothing new since ${hm(prev.finished_at)}` : "Done — nothing new" };
  }

  // in the thread: every Check now (with its progress), and an hourly run only when it brought something new
  function inThread(run, now) {
    if (!run || !run.stage) return false;            // rows from before live updates
    if (run.trigger === "manual") return true;
    return run.stage === "done" && Number(run.new_items) > 0;
  }

  const pollEvery = (active) => (active ? 15000 : 60000);

  function buttonLabel(run, now) {
    return isActive(run, now) ? `Checking… ${run.stage === "queued" ? "queued" : run.stage}` : "Check now";
  }

  // the demo's Check now: the same steps on the sample snapshot, nothing fetched
  const DEMO_STAGES = [["queued", 700], ["logging in", 1100], ["reading companies", 900], ["reading notices", 900],
                       ["reading PDFs", 800], ["saving", 500]];

  // the latest run that is going (for the header and the buttons)
  function current(runs, now) { return (runs || []).find((r) => isActive(r, now)) || null; }
  function lastFinished(runs) {
    return (runs || []).filter((r) => r.finished_at).sort((a, b) => t(b.finished_at) - t(a.finished_at))[0] || null;
  }

  const api = { ACTIVE, STEPS, isActive, steps, describe, inThread, pollEvery, buttonLabel, DEMO_STAGES, current,
                lastFinished, previousDone };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingLive = api;
})(typeof window !== "undefined" ? window : globalThis);
