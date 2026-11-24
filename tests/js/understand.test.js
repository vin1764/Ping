// The model's two small jobs (supabase/functions/_shared/understand.js), with made-up model replies: what it reads is
// checked against the data, the rules still answer, and a reply is kept only if every fact in it is in the facts.
const { test } = require("node:test");
const assert = require("node:assert");
const U = require("../../supabase/functions/_shared/understand.js");
const R = require("../../supabase/functions/_shared/answer_rules.js");
const spec = require("../../evals/conversations/risa_jd.json");

const data = {
  now: spec.now, lastChecked: spec.last_checked, profile: {}, prefs: {}, items: [], notices: spec.notices, emails: [], forms: [],
  pdf_checks: [{ notice_id: "2026-2027:1841", status: "jd", context: spec.jd_text }],
  roles: spec.roles.map((d, i) => ({ id: `risa${i}`, company: spec.company, designation: d, applied: false, deadline: "2026-11-24T22:00:00+05:30",
    jd_source: "notice", jd_text: spec.jd_text, jd_note: "the PDF on notice 1841 (23 Nov)",
    jd_url: "https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=2026-2027&id=1841" }))
    .concat([{ id: "zs1", company: "ZS ASSOCIATES", designation: "Business Analyst", applied: false, deadline: "2026-11-25T20:00:00+05:30" }]),
};
const call = (text, ms = 5) => () => new Promise((res) => setTimeout(() => res({ text, model: "fake" }), ms));

test("understand: the JSON is checked against the data; unknown names become null", async () => {
  const ok = await U.understand({ question: "what all roles?", turns: [{ role: "me", text: "risa jd?" }], data, Rules: R,
    call: call('{"company":"RISA Labs","role":null,"fact":"roles","source":"any","is_followup":true,"scope":"all"}') });
  assert.deepStrictEqual([ok.u.company, ok.u.fact, ok.u.is_followup, ok.u.scope, ok.fell], ["RISA Labs", "roles", true, "all", false]);
  const made = await U.understand({ question: "jd?", turns: [], data, Rules: R,
    call: call('{"company":"Acme Rockets","role":"Pilot","fact":"salary","source":"tv"}') });
  assert.deepStrictEqual([made.u.company, made.u.role, made.u.fact, made.u.source], [null, null, "other", "any"]);
  const role = await U.understand({ question: "and the apm one?", turns: [{ role: "me", text: "risa jd" }], data, Rules: R,
    call: call('{"company":"RISA Labs","role":"Associate Product Manager - Growth","fact":"jd","source":"any"}') });
  assert.strictEqual(role.u.role, "Associate Product Manager - Growth");
});

test("understand: past the cap, or unreadable, the rules answer alone", async () => {
  const slow = await U.understand({ question: "x", turns: [], data, Rules: R, call: call("{}", 200), capMs: 50 });
  assert.ok(slow.fell && slow.why === "timeout" && slow.ms < 150);
  const junk = await U.understand({ question: "x", turns: [], data, Rules: R, call: call("sure! here you go") });
  assert.ok(junk.fell && junk.why === "unparsable");
  const err = await U.understand({ question: "x", turns: [], data, Rules: R, call: () => Promise.reject(new Error("503")) });
  assert.ok(err.fell);
});

test("augment: fills in only what the question left out; what it says wins", () => {
  const u = { company: "RISA Labs", role: null, fact: "roles", source: "any" };
  assert.strictEqual(U.augment("what all roles?", u, data, R), "what all roles? RISA Labs");
  assert.ok(!/RISA/.test(U.augment("zs roles?", u, data, R)));                                // a company named: kept
  assert.strictEqual(U.augment("and on mail?", { company: "RISA Labs", role: null, fact: "jd", source: "mail" }, data, R),
    "and on mail? RISA Labs jd");
  assert.strictEqual(U.augment("ok", null, data, R), "ok");
});

test("the rules answer the augmented follow-up: every RISA role, not random ones", () => {
  const q = U.augment("what all roles?", { company: "RISA Labs", role: null, fact: "roles", source: "any" }, data, R);
  const text = R.routed(R.route(q, ["risa jd?"], data), q, data).text;
  for (const d of spec.roles) assert.ok(text.includes(d), `missing ${d}: ${text}`);
  assert.ok(!/Business Analyst/.test(text));
});

test("verify: a reply keeps every fact and link, adds none", () => {
  const facts = "RISA Labs JDs are in the CDC notice PDF (23 Nov) — [Open](https://x.example/1841).\n[Associate Product Manager](#ask:risa%20apm%20jd)";
  const names = ["RISA Labs", "ZS Associates"];
  assert.ok(U.verify("RISA Labs' JDs: the CDC notice PDF from 23 Nov — [Open](https://x.example/1841). [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);
  assert.ok(!U.verify("RISA Labs JDs are in the CDC notice PDF (24 Nov) — [Open](https://x.example/1841). [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);  // a date changed
  assert.ok(!U.verify("RISA Labs JDs are in the CDC notice PDF (23 Nov). [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);  // link dropped
  assert.ok(!U.verify("RISA Labs JDs are in the PDF (23 Nov) — [Open](https://evil.example). [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);
  assert.ok(!U.verify("ZS Associates and RISA Labs JDs (23 Nov) — [Open](https://x.example/1841) [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);  // a company added
  assert.ok(!U.verify("You applied. RISA Labs JDs (23 Nov) — [Open](https://x.example/1841) [Associate Product Manager](#ask:risa%20apm%20jd)", facts, data, names).ok);  // a status added
});

test("compose: a reply that fails the check is replaced by the rules' answer", async () => {
  const answer = "Nothing in placement mail for the RISA Labs JD. It's in the CDC notice PDF (23 Nov) — [Open](https://x.example/1841).";
  const good = await U.compose({ question: "risa jd on mail??", answer, data, companyNames: ["RISA Labs"],
    call: call("Not in your mail. The RISA Labs JD is in the CDC notice PDF (23 Nov) — [Open](https://x.example/1841).") });
  assert.ok(good.used && /CDC notice PDF/.test(good.text));
  const bad = await U.compose({ question: "risa jd on mail??", answer, data, companyNames: ["RISA Labs"],
    call: call("Not in your mail; the JD is attached to the notice.") });
  assert.ok(!bad.used && bad.text === answer);                // the link was dropped: the rules' answer is sent
});
