// Ask Ping's router (supabase/functions/_shared/answer_rules.js route): FACT questions are answered by rules with no
// model call; OPEN ones go to the model; follow-ups resolve against the last turn first. On a small made-up data set.
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../supabase/functions/_shared/answer_rules.js");

const data = {
  now: "2026-11-21T17:30:00+05:30", lastChecked: "2026-11-21T17:11:00+05:30",
  profile: { cgpa: 8.0, department: null, degree: null }, prefs: { listOthers: true },
  roles: [
    { id: "r1", company: "Slice", designation: "Associate Product Manager", deadline: "2026-11-21T20:00:00+05:30", applied: false, for_you: true,
      cv: "Product CV", ctc: 2800000, currency: "INR", cgpa_cutoff: 7.5,
      pay: { "1st Year CTC": "2800000", "CTC Breakup": "22L Fixed + 2L Retention Bonus + 4L ESOPs", "Bonds": "No", "Joining Bonus, if any": "0" } },
    { id: "r2", company: "Slice", designation: "Analyst", deadline: "2026-11-21T20:00:00+05:30", applied: true, for_you: true, ctc: 2500000,
      pay: { "1st Year CTC": "2500000", "CTC Breakup": "19L base + 2L RB + 4L ESOPs", "Bonds": "No" } },
    { id: "r3", company: "AiPrise", designation: "Software Engineer I", deadline: "2026-11-21T20:00:00+05:30", applied: false, for_you: false },
    { id: "r4", company: "Harness", designation: "Software Engineer I", deadline: "2026-10-14T12:00:00+05:30", applied: false, cgpa_cutoff: 7.5,
      pay: { "Bonds": "No", "Fixed Take Home Salary (per Annum)": "2700000" } },
  ],
  items: [
    { id: "t1", company: "Groww", category: "test", level: "always", event_at: "2026-11-21T15:00:00+05:30", title: "Groww test (APM) Sat 21 Nov 15:00." },
    { id: "t2", company: "Eternal", category: "test", level: "always", event_at: "2026-11-19T19:15:00+05:30", venue: "Nalanda Classroom Complex",
      title: "Eternal test room list (Product Analyst). Test Thu 19 Nov 19:15.", pdf: { status: "yes", details: { room: "NR 121" } }, pdf_status: "yes" },
  ],
  notices: [{ company: "SLICE", subject: "PPT", notice_time: "2026-11-20T10:00:00+05:30" }],
};
const route = (q, prev = []) => R.route(q, prev, data);
const reply = (q, prev = []) => R.routed(route(q, prev), q, data).text;

test("FACT questions are answered by rules; OPEN ones go to the model; requests to act get the read-only answer", () => {
  for (const q of ["which cv for slice", "what's due tonight?", "any tests today?", "slice ctc breakdown", "am I eligible for harness",
                   "did i apply to slice", "does harness have a bond", "am I shortlisted anywhere", "latest notice for slice",
                   "how many roles close tonight", "what's due on 25 November", "summarise slice's JD"]) {
    assert.strictEqual(route(q).kind, "fact", q);
  }
  for (const q of ["why should I pick slice over harness", "compare slice and aiprise", "tell me about slice", "hmm",
                   "give me a plan for today's deadlines", "summarise this week for me in three lines",
                   "what do you think about slice's roles for a data person?"]) {  // the last three: found by the live provider run
    assert.strictEqual(route(q).kind, "open", q);
  }
  // when the model can't answer an open question, the rules don't read its words as a company ("I don't have Plan")
  assert.doesNotMatch(reply("give me a plan for today's deadlines"), /I don't have Plan/);
  assert.strictEqual(route("apply to slice for me").kind, "act");
  assert.match(reply("apply to slice for me"), /^Ping is read-only, so I can't apply for you/);
  assert.strictEqual(route("ok").kind, "ack");
});

test("what's due tonight: the digest's counts (for you = not applied yet), never a count without names", () => {
  const t = reply("what's due tonight?");
  assert.match(t, /^Close tonight 20:00 \(in 2h 30m\), Sat 21 Nov — 1 for you, 1 applied:\nFor you:\n- Slice — Associate Product Manager \(apply with Product CV\)\nApplied:\n- Slice — Analyst ✓ applied\nOthers \(1\):\n- AiPrise — Software Engineer I$/);
});

test("pay: the parts asked about, and a bond question answered as one", () => {
  assert.match(reply("slice ctc breakdown"), /Slice \(Associate Product Manager\): CTC 28,00,000 INR: 1st Year CTC: 28,00,000; CTC Breakup: 22L Fixed \+ 2L Retention Bonus \+ 4L ESOPs; Bonds: No/);
  assert.strictEqual(reply("does harness have a bond"), "Harness (Software Engineer I): no bond (Bonds: No).");
  assert.match(reply("harness take home salary"), /Fixed Take Home Salary \(per Annum\): 27,00,000/);
});

test("follow-ups resolve against the last turn, then route the same way", () => {
  // a new company, the same question
  assert.strictEqual(route("and harness?", ["does slice have a bond"]).kind, "fact");
  assert.match(reply("and harness?", ["does slice have a bond"]), /^Harness \(Software Engineer I\): no bond/);
  // a role of the same company
  const analyst = reply("same for analyst role?", ["slice ctc breakdown"]);
  assert.match(analyst, /Slice \(Analyst\)/);
  assert.doesNotMatch(analyst, /Associate Product Manager/);
  // "where?" after a test question: the same company's test, with the venue
  assert.match(reply("where?", ["when is the eternal test"]), /Nalanda Classroom Complex/);
  // "nothing else?" after tests today: no other test, then the most urgent thing left today
  assert.match(reply("nothing else?", ["any tests today?"]), /^No other test today: that was the only one\. 3 roles close at 20:00 today \(in 2h 30m\), 2 not applied \(1 for you\): Slice\.$/);
  // a past deadline, by pronoun
  assert.match(reply("when is it?", ["latest notice for harness"]), /Harness \(Software Engineer I\): closed Wed 14 Oct 12:00 \(already passed\)\.$/);
  // nothing new to go on: the model
  assert.strictEqual(route("and?", ["slice ctc"]).kind, "open");
  assert.strictEqual(route("why not?", ["am I eligible for slice"]).kind, "open");
  // a new topic is not a follow-up
  assert.match(reply("ok. what's due this week?", ["slice ctc"]), /^Close tonight 20:00/);
});

test("the model's numbers must be in the facts", () => {
  const facts = "Close tonight 20:00 — 8 for you, 9 applied: ... CTC 28,00,000 INR";
  assert.deepStrictEqual(R.unsupportedNumbers("8 roles for you close at 20:00; CTC 28 LPA.", facts, ""), []);
  assert.deepStrictEqual(R.unsupportedNumbers("17 roles for you close at 20:00.", facts, ""), ["17"]);
  assert.deepStrictEqual(R.unsupportedNumbers("They close at 21:00.", facts, ""), ["21:00"]);
  assert.deepStrictEqual(R.unsupportedNumbers("CTC is 30 L.", facts, ""), ["30 L"]);
});

// ---- help: Ping about itself (docs/HELP.md -> help.js), never "I don't have any information"
test("help questions route to help, with the asker's platform for installing", () => {
  const d = { now: new Date("2026-11-21T10:00:00+05:30"), roles: [{ id: "1", company: "Groww", designation: "PA" }], items: [], notices: [] };
  const topic = (q) => { const r = R.route(q, [], d); return r.kind === "help" ? r.topic : r.kind; };
  assert.equal(topic("how to install"), "install");
  assert.equal(topic("how do I get notifications"), "notifications");
  assert.equal(topic("what can you do"), "can");
  assert.equal(topic("help"), "overview");
  assert.equal(topic("how often do you check?"), "checks");
  assert.equal(topic("how do I change my preferences"), "preferences");
  assert.equal(topic("where is my data stored"), "data");
  assert.notEqual(topic("any alerts for groww?"), "notifications");       // a company: a question about Groww
  assert.equal(topic("whats due tonight"), "fact");
  const steps = (q, platform, installed) => R.routed(R.route(q, [], d), q, { ...d, platform, installed }).text;
  assert.match(steps("how to install", "windows"), /⋮ menu → "Install Ping…"/);
  assert.match(steps("how to install", "android"), /Install app/);
  assert.match(steps("how to install", "ios"), /Add to Home Screen/);
  assert.match(steps("how do I install on iphone", "windows"), /Add to Home Screen/);   // the named platform wins
  assert.match(steps("how to install", "windows", true), /already using Ping as an installed app/);
  assert.equal(R.platformOf("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131"), "windows");
  assert.equal(R.platformOf("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari", 5), "ios");   // an iPad
  assert.equal(R.platformOf("Mozilla/5.0 (Linux; Android 14) Chrome/131 Mobile"), "android");
});

// ---- placement mail: "any mails for X", "did I get a test link for Y", "what's due from mail"
test("mail questions are answered from the mail messages, with their links", () => {
  const now = "2026-11-20T10:00:00+05:30";
  const items = [
    { id: "mail:a", company: "Pine Labs", category: "todo", level: "show", due_at: "2026-11-22T17:00:00+05:30",
      title: "Pine Labs: fill the form by Sun 22 Nov 17:00.", via: "email", mail: { link: "https://forms.gle/x" }, todo: { action: "fill_form", link: "https://forms.gle/x" } },
    { id: "mail:b", company: "Atlassian", category: "todo", level: "always", due_at: "2026-11-25T23:59:00+05:30",
      title: "Atlassian: take the online test by Wed 25 Nov 23:59.", via: "email", mail: { link: "https://www.hackerrank.com/tests/atl" }, todo: { action: "take_test" } },
    { id: "notice:x:0", company: "Groww", category: "test", level: "always", event_at: "2026-11-23T15:00:00+05:30",
      title: "Groww test (PA) Mon 23 Nov 15:00.", mail: { note: "also mailed to you", link: "https://www.hackerrank.com/tests/groww" } }];
  const roles = ["Pine Labs", "Atlassian", "Groww", "Navi"].map((c, i) => ({ id: `r${i}`, company: c, designation: "Analyst" }));
  const d = { now, roles, items, notices: [], lastChecked: now };
  const ask = (q) => { const r = R.route(q, [], d); assert.strictEqual(r.kind, "fact", q); return R.routed(r, q, d).text; };
  assert.match(ask("any mails for pine labs?"), /fill the form by Sun 22 Nov 17:00 · via email\n  https:\/\/forms\.gle\/x/);
  assert.match(ask("did I get a test link for groww"), /Groww test .* · also on the ERP\n  https:\/\/www\.hackerrank\.com\/tests\/groww/);
  assert.match(ask("did i get a test link for navi"), /^No test link from Navi/);
  const due = ask("whats due from mail");
  assert.ok(due.indexOf("Pine Labs") < due.indexOf("Atlassian") && !/Groww/.test(due));
});

test("'that' starting a clause doesn't make a new question a follow-up (found by the page evals)", () => {
  const d = { now: "2026-11-21T18:35:00+05:30", roles: [
    { id: "e1", company: "Esri", designation: "Data Scientist I", deadline: "2026-11-21T20:00:00+05:30", applied: false, for_you: true },
    { id: "a1", company: "Axis Bank", designation: "BIU", deadline: "2026-11-21T20:00:00+05:30", applied: false, for_you: true }], items: [], notices: [] };
  const r = R.route("what's due tonight that's relevant to me", ["when does ESRI close?"], d);
  assert.deepStrictEqual(r.spec.hits, []);
  assert.notStrictEqual(r.why, "follow-up");
  const f = R.route("what about that one", ["when does ESRI close?"], d);       // a real follow-up still is one
  assert.match(f.why, /follow-up/);
  assert.deepStrictEqual(f.spec.hits.map((h) => h.name), ["Esri"]);
});
