// Conversation evals from real conversations that went wrong (evals/conversations/*.json): each turn goes through
// the same rules the page and the function use (route -> routed, with the earlier questions and the last answer),
// in two data states where the file gives them ('before' and 'after' a JD PDF was read).
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const R = require("../../supabase/functions/_shared/answer_rules.js");

const DIR = path.join(__dirname, "..", "..", "evals", "conversations");

function dataFor(spec, state) {
  const roles = spec.roles.map((d, i) => ({ id: `risa${i}`, company: spec.company, designation: d, applied: false,
    deadline: "2026-11-24T22:00:00+05:30", jd_source: "none", jd_note: "NA" }));
  const pdf_checks = [];
  if (state === "after") {
    for (const r of roles) Object.assign(r, { jd_source: "notice", jd_text: spec.jd_text,
      jd_url: "https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=2026-2027&id=1841",
      jd_note: "the PDF on notice 1841 (23 Nov) (one PDF for several roles)" });
    pdf_checks.push({ notice_id: "2026-2027:1841", status: "jd", context: spec.jd_text }, { notice_id: "2026-2027:1860", status: "jd", context: spec.jd_text });
  } else {
    pdf_checks.push({ notice_id: "2026-2027:1841", status: "unknown" }, { notice_id: "2026-2027:1860", status: "unknown" });
  }
  return { now: spec.now, lastChecked: spec.last_checked, profile: {}, prefs: {}, roles, items: [], notices: spec.notices,
           pdf_checks, emails: [], forms: [] };
}

function run(spec, conv, state) {
  const data = dataFor(spec, state);
  const asked = [], said = [];
  const out = [];
  for (const t of conv.turns) {
    const d = { ...data, lastAnswer: said[said.length - 1] || null };
    const r = R.route(t.q, [...asked].reverse(), d);
    const text = r.kind === "open" ? `(model) ${r.why}` : R.routed(r, t.q, d).text;
    out.push({ t, text, kind: r.kind });
    asked.push(t.q);
    said.push(text);
  }
  return out;
}

for (const file of fs.readdirSync(DIR).filter((f) => f.endsWith(".json"))) {
  const spec = JSON.parse(fs.readFileSync(path.join(DIR, file), "utf8"));
  for (const state of ["before", "after"]) {
    for (const conv of spec.conversations) {
      test(`${file} ${conv.id} (${state}): ${conv.case}`, () => {
        const turns = run(spec, conv, state);
        let prev = null;
        for (const { t, text, kind } of turns) {
          const where = `"${t.q}" ->\n${text}`;
          assert.notStrictEqual(kind, "open", `answered by the rules, not left to the model: ${where}`);
          for (const m of t.must || []) assert.ok(text.toLowerCase().includes(m.toLowerCase()), `must contain ${JSON.stringify(m)}: ${where}`);
          for (const m of t.not || []) assert.ok(!text.toLowerCase().includes(m.toLowerCase()), `must not contain ${JSON.stringify(m)}: ${where}`);
          assert.ok(text.split("\n").filter((l) => l.trim()).length <= (t.max_lines || 3), `at most ${t.max_lines || 3} lines: ${where}`);
          assert.notStrictEqual(text, prev, `never the same answer twice in a row: ${where}`);
          prev = text;
        }
      });
    }
  }
}
