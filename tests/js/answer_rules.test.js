// The answers Ping gives without the AI (supabase/functions/_shared/answer_rules.js), on a small made-up data set.
const test = require("node:test");
const assert = require("node:assert");
const R = require("../../supabase/functions/_shared/answer_rules.js");

const NOW = "2026-11-21T17:30:00+05:30";
const data = {
  now: NOW,
  lastChecked: "2026-11-21T17:11:00+05:30",
  roles: [
    { id: "r1", company: "Meesho", designation: "Senior Associate - BM", applied: false, deadline: "2026-11-22T18:00:00+05:30" },
    { id: "r2", company: "Microsoft Corporation", designation: "Software Engineer", applied: false, deadline: "2026-11-08T16:00:00+05:30" },
    { id: "r3", company: "BlackBuck", designation: "Associate Manager", applied: true, deadline: "2026-11-21T20:00:00+05:30", cv: "Consulting CV" },
    { id: "r4", company: "Ather Energy", designation: "Product Ownership", applied: false, deadline: "2026-11-21T20:00:00+05:30" },
    { id: "r5", company: "Energy Aspects", designation: "Energy Market Analyst", applied: true, deadline: "2026-11-12T20:00:00+05:30" },
    { id: "r6", company: "Auro Group(www.AuroIM.com)", designation: "Data Analyst", applied: false, deadline: "2026-11-21T20:00:00+05:30" },
    { id: "r7", company: "Auro Group(www.AuroIM.com)", designation: "Product Manager", applied: true, deadline: "2026-11-21T20:00:00+05:30" },
  ],
  items: [
    // a form and a CV submission for the same role and deadline: one line
    { id: "i1", company: "Meesho", category: "todo", title: "Meesho (Senior Associate - BM): fill the form by Sun 22 Nov 18:00.",
      due_at: "2026-11-22T18:00:00+05:30", role_ids: ["r1"], subject: "Google form" },
    { id: "i2", company: "Meesho", category: "todo", title: "Meesho (Senior Associate - BM): submit by Sun 22 Nov 18:00.",
      due_at: "2026-11-22T18:00:00+05:30", role_ids: ["r1"], subject: "Submission" },
    // a submission for a shortlist the student isn't on: hidden in the feed, so not "due" for them
    { id: "i4", company: "Pine Labs", category: "todo", title: "Pine Labs (SDE): submit by Sun 22 Nov 20:00.",
      due_at: "2026-11-22T20:00:00+05:30", level: "hidden" },
    // hidden only because the form digest carries it: still due
    { id: "i5", company: "BlackBuck", category: "todo", title: "BlackBuck (Associate Manager): fill the form by Sun 22 Nov 12:00.",
      due_at: "2026-11-22T12:00:00+05:30", level: "hidden", hidden_because: "in the form digest", role_ids: ["r3"] },
    { id: "i3", company: "Microsoft Corporation", category: "test", title: "Microsoft Corporation test room list is out (Software Engineer). You're not on it.",
      event_at: "2026-11-10T18:00:00+05:30", pdf_status: "no" },
  ],
  notices: [
    { company: "MICROSOFT", subject: "CV Submission", notice_time: "2026-11-07T18:35:00+05:30" },
    { company: "Microsoft", subject: "PPO", notice_time: "2026-11-11T17:59:00+05:30" },
    { company: "MEESHO", subject: "Submission", notice_time: "2026-11-20T10:00:00+05:30" },
    { company: "CDC Placement Schedule for 21st November 2026", subject: "Schedule", notice_time: "2026-11-20T21:00:00+05:30" },
  ],
};
const ask = (q) => R.answer(q, data);

test("a company with an open deadline: only that company, form + submission merged on one line", () => {
  const a = ask("meesho cv submission deadline");
  assert.strictEqual(a.kind, "company");
  assert.match(a.text, /^Meesho: open deadlines \(last checked Sat 21 Nov 17:11\):/);
  assert.match(a.text, /- Senior Associate - BM: form \+ submission \+ application by Sun 22 Nov 18:00 · not applied/);
  assert.strictEqual((a.text.match(/by Sun 22 Nov 18:00/g) || []).length, 1);
  assert.match(a.text, /Last Meesho notice: "Submission", Fri 20 Nov 10:00\./);
  assert.doesNotMatch(a.text, /BlackBuck|Ather|Auro/);
});

test("a company with no open deadline: says so plainly, with the last notice", () => {
  const a = ask("microsoft cv submission deadline");
  assert.strictEqual(a.kind, "company");
  assert.match(a.text, /^No open deadline for Microsoft in the ERP data \(last checked Sat 21 Nov 17:11\)\./);
  assert.match(a.text, /Last Microsoft notice: "PPO", Wed 11 Nov 17:59\./);
  assert.match(a.text, /You're not on it/);
  assert.doesNotMatch(a.text, /Meesho|BlackBuck|due/i);
});

test("a company Ping has no data on", () => {
  const a = ask("google cv deadline");
  assert.strictEqual(a.kind, "unknown");
  assert.match(a.text, /^I don't have Google in your ERP data/);
  assert.match(a.text, /last checked Sat 21 Nov 17:11/);
});

test("typos, aliases and shared words", () => {
  assert.match(ask("blakbuck deadline").text, /^BlackBuck: open deadlines/);
  assert.match(ask("mircosoft deadline").text, /^No open deadline for Microsoft/);
  assert.match(ask("msft deadline").text, /^No open deadline for Microsoft/);
  assert.match(ask("MS deadline").text, /Microsoft/);
  const ather = ask("ather energy deadline");
  assert.deepStrictEqual(ather.companies, ["Ather Energy"]);             // not Energy Aspects too
  assert.deepStrictEqual(ask("auro group deadline").companies, ["Auro Group"]);  // the website in brackets is dropped
  assert.match(ask("which cv for blackbuck").text, /BlackBuck \(Associate Manager\): apply with Consulting CV\./);
});

test("no company: the intent decides; nothing understood: labelled, then what's due soon", () => {
  const tom = ask("what's due tomorrow?");
  assert.strictEqual(tom.kind, "intent");
  assert.match(tom.text, /^Due tomorrow \(Sun 22 Nov\):\n- BlackBuck[^\n]*\n- Meesho \(Senior Associate - BM\): form \+ submission \+ application by Sun 22 Nov 18:00/);
  assert.doesNotMatch(tom.text, /Pine Labs/);
  assert.match(tom.text, /- BlackBuck \(Associate Manager\): form by Sun 22 Nov 12:00/);
  const d = ask("hmm");
  assert.strictEqual(d.kind, "digest");
  assert.match(d.text, /^I couldn't tell what you meant\. Here's what's due soon:/);
  // never a count without names: every line names its company
  for (const line of d.text.split("\n").slice(1)) assert.match(line, /^- (Meesho|BlackBuck|Ather Energy|Auro Group) \(/);
  assert.doesNotMatch(d.text, /Pine Labs/);
  assert.match(d.text, /Auro Group \(Data Analyst, Product Manager\): application by Sat 21 Nov 20:00 \(in 2h 30m\) · applied to 1 of 2/);
  assert.match(ask("which cv should i use").text, /^Which company\?/);
});

test("tests today include the one earlier today, marked over; tests not about you are left out", () => {
  const d2 = { ...data, items: [...data.items,
    { id: "t1", company: "Groww", category: "test", title: "Groww test (APM) Sat 21 Nov 15:00.", event_at: "2026-11-21T15:00:00+05:30", level: "always" },
    { id: "t2", company: "NexusOne", category: "test", title: "NexusOne test (Data Engineer) Sat 21 Nov 19:00.", event_at: "2026-11-21T19:00:00+05:30", level: "hidden" }] };
  const a = R.answer("any tests today?", d2);
  assert.match(a.text, /^Tests and lists today \(Sat 21 Nov\):\n- Groww test \(APM\) Sat 21 Nov 15:00\. \(over\)$/);
});

test("schedule notices are not companies", () => {
  assert.ok(!R.entities(data).some((e) => /schedule/i.test(e.name)));
});

test("JD questions: the stored summary (≤120 words), a link that can't be opened, no JD", () => {
  const d = { ...data, roles: [
    { id: "j1", company: "JP MorganChase", designation: "Global Research - Full Time Analyst", cgpa_cutoff: 7.0, jd_source: "detail",
      jd_text: "Developing deep insights ...", jd_summary: { role_team: "Analyst, Global Research (CIB Research & Analytics)",
        do: ["Analyse public data for deep insights", "Build and maintain financial models", "Service key stakeholders"],
        must_have: ["Strong analytical skills", "Excel and financial modelling"], location: "Mumbai", eligibility: null,
        unusual: [], key: "k" } },
    { id: "j2", company: "Searce Inc.", designation: "Associate Data Engineer", jd_source: "link-unreadable",
      jd_url: "https://docs.google.com/document/d/14dVgbE3ZQouUB93/edit" },
    { id: "j3", company: "Cars24", designation: "Data Science", jd_source: "none", jd_note: "-" },
  ] };
  const a = R.answer("summarise JPMC's JD", d);
  assert.strictEqual(a.kind, "company");
  assert.match(a.text, /^JP MorganChase \(Global Research - Full Time Analyst\): Analyst, Global Research/);
  assert.match(a.text, /What you'd do:\n- Analyse public data for deep insights\n- Build and maintain financial models/);
  assert.match(a.text, /Must-have: Strong analytical skills; Excel and financial modelling\nLocation: Mumbai\nEligibility: CG cut-off 7 \(ERP\)/);
  assert.ok(a.text.split(/\s+/).length <= 125, a.text);          // 120 words + the "(From ...)" source line
  assert.strictEqual(R.answer("what's the JD for searce associate data engineer", d).text,
    "Searce (Associate Data Engineer): The JD is a link I can't open: https://docs.google.com/document/d/14dVgbE3ZQouUB93/edit");
  assert.strictEqual(R.answer("what do they want for cars24", d).text, "Cars24 (Data Science): no JD on the ERP.");
  const d3 = { ...data, roles: [{ id: "j5", company: "Accenture", designation: "AI and Data", jd_source: "none", jd_note: "As mentioned in Registration Email" }] };
  assert.strictEqual(R.answer("summarise accenture's jd", d3).text,
    'Accenture (AI and Data): no JD on the ERP (the ERP says: "As mentioned in Registration Email").');
  assert.match(R.answer("summarise google's jd", d).text, /^I don't have Google/);
  // the JD came from the ERP's details, the fuller JD is a private link; a model that sent [] for "no location"
  const d2 = { ...data, roles: [{ id: "j4", company: "Searce Inc.", designation: "Associate Data Engineer", jd_source: "detail",
    jd_url: "https://docs.google.com/document/d/x/edit", jd_text: "Role: Build data pipelines ...",
    jd_summary: { role_team: "Data Engineer", do: ["Build data pipelines"], must_have: ["Python", "SQL"], location: [], eligibility: [] } }] };
  const t = R.answer("what's the JD for searce", d2).text;
  assert.match(t, /^Searce \(Associate Data Engineer\): Data Engineer\nWhat you'd do:\n- Build data pipelines\nMust-have: Python; SQL\n/);
  assert.doesNotMatch(t, /Location|Eligibility/);
  assert.match(t, /\(From the ERP's role details\.\)\nThe full JD is a link I can't open: https:\/\/docs\.google\.com\/document\/d\/x\/edit$/);
});
