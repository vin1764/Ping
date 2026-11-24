// The conversation follows the topic and re-checks on request (evals/ask_ping/multiturn.json): routing of every
// multi-turn case, and the re-check answer's wording (found / not found / unreadable / unreachable; never "not on it").
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../supabase/functions/_shared/answer_rules.js");
const evals = require("../../evals/ask_ping/multiturn.json");

const data = { now: new Date("2026-11-22T14:30:00+05:30"), lastChecked: "2026-11-22T12:41:00+05:30",
  roles: [{ id: "r1", company: "FirstClub", designation: "Product Management" }, { id: "r2", company: "GROWW", designation: "APM" },
          { id: "r3", company: "Auro Group([www.AuroIM.com](https://www.AuroIM.com))", designation: "Analyst" }],
  items: [], notices: [] };

for (const c of evals.cases) {
  test(`${c.id}: ${c.turns.map((t) => t.q).join(" → ")}`, () => {
    const prev = [];
    for (const t of c.turns) {
      const r = R.route(t.q, [...prev].reverse(), data);
      assert.strictEqual(r.kind, t.route, `${t.q}: ${r.kind} (${r.why})`);
      const names = r.kind === "recheck" ? r.companies : (r.spec?.hits || []).map((e) => e.name);
      if (t.company) assert.ok(names.some((n) => R.shortName(n).toLowerCase() === t.company.toLowerCase()), `${t.q}: about ${names}`);
      if (t.company === null) assert.deepStrictEqual(names, [], `${t.q}: should start a new topic, got ${names}`);
      if (r.kind === "recheck") assert.match(R.routed(r, t.q, data).text, /^Checking the ERP for .+ now…$/);
      prev.push(t.q);
    }
  });
}

const LINK = "https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=2026-2027&id=1817";
const row = (fileStatus) => ({ status: "done", company: "FirstClub", result: { company: "FirstClub", read_at: "2026-11-22T09:10:00Z",
  notices: [{ notice_id: 1817, subject: "Shortlist", kind: "shortlist", notice_time: "2026-11-22T11:45:00+05:30", has_attachment: true, link: LINK,
              file: { status: fileStatus, read_at: "2026-11-22T09:10:00Z", reliability: fileStatus === "unknown" ? "scanned file" : null,
                      details: fileStatus === "yes" ? { room: "NC 231" } : {} } }], changes: [] } });
for (const w of evals.render) {
  test(`${w.id}: ${w.about}`, () => {
    const rc = w.status === "done" ? row(w.file) : { status: w.status, company: "FirstClub", note: "the ERP didn't answer" };
    const text = R.recheckAnswer(rc, new Date("2026-11-22T14:41:00+05:30"), LINK).text;
    for (const m of w.must_contain || []) assert.ok(text.includes(m), `missing "${m}" in: ${text}`);
    for (const m of w.must_not_contain || []) assert.ok(!text.includes(m), `"${m}" in: ${text}`);
    for (const m of evals.never) assert.ok(!text.toLowerCase().includes(m), `"${m}" in: ${text}`);
    if (w.status === "done") assert.match(text, /just now \(14:40\)/);
  });
}

test("re-check phrases, and questions that aren't", () => {
  for (const q of ["check again", "recheck", "are you sure?", "that's wrong", "I think I'm on it", "I got a call from firstclub",
                   "check the erp for the latest", "don't answer on old data", "double check", "Check erp bruh for latest updates, dont answer on old data",
                   "check i guess it has listed on epr", "it's up on the portal now", "check epr"])
    assert.ok(R.isRecheck(q), q);
  for (const q of ["what's due tonight", "groww ctc", "which cv for zeta", "am I on the firstclub shortlist", "latest notice from groww", "what's listed on the erp today?"])
    assert.ok(!R.isRecheck(q), q);
});

test("staleness note over 30 min only", () => {
  assert.strictEqual(R.staleNote("2026-11-22T14:10:00+05:30", new Date("2026-11-22T14:30:00+05:30")), null);
  assert.strictEqual(R.staleNote("2026-11-22T12:41:00+05:30", new Date("2026-11-22T14:30:00+05:30")), "ERP data from 12:41 (1 h 49 min ago).");
});

test("company names without their website", () => {
  assert.strictEqual(R.cleanNames("Auro Group([www.AuroIM.com](https://www.AuroIM.com)): Analyst"), "Auro Group: Analyst");
});

test("unresolved: the questions the page hands to the function (the model reads them first)", () => {
  const D = require("../../evals/generated/demo_data.js")();
  const un = (q, prev = []) => { const r = R.route(q, prev, D); return R.unresolved(q, r, r.kind === "open" ? null : R.routed(r, q, D), D); };
  for (const q of ["ctc?", "elig?", "roles", "and jd", "process till now?"]) assert.ok(un(q), q);
  for (const q of ["navi ctc?", "what's due tonight?", "any test today?", "deadline?"]) assert.ok(!un(q), q);
  assert.ok(!un("ctc?", ["navi roles"]), "a follow-up the rules resolve stays on the page");
});
