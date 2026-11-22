// Ask Ping's router and rules on the demo snapshot, offline (no function, no model): every case and conversation in
// cases.json goes through route() and, when it is a FACT / ACT / ACK, through the rules answer, scored with the same
// checks as the live evals. OPEN cases are listed (they need the model).
//   node evals/ask_ping/route_offline.js [--all] [--only ID,ID]
// --all also scores OPEN cases with the rules answer (what they'd get if the model were down).
const fs = require("fs");
const path = require("path");
const R = require("../../supabase/functions/_shared/answer_rules.js");

const ROOT = path.join(__dirname, "..", "..");
const spec = JSON.parse(fs.readFileSync(path.join(__dirname, "cases.json"), "utf8"));
const demo = JSON.parse(fs.readFileSync(path.join(ROOT, "dashboard", "demo-data.json"), "utf8"));

// the same shape the function builds from the database (supabase/functions/ask-ping/index.ts, factsData)
function data(asOf) {
  const hasTargets = !!demo.profile.targets && demo.profile.feed_mode !== "all";
  return {
    now: asOf, lastChecked: asOf,
    profile: demo.profile, prefs: { listOthers: demo.profile.list_other_roles !== false },
    roles: demo.roles.map((r) => ({ ...r, deadline: r.effective_deadline,
      for_you: hasTargets ? !!r.relevance?.relevant : undefined,
      cv: r.relevance?.relevant ? r.relevance?.best_cv || null : null,
      pay: r.more_details?.fields || {}, jd_location: r.jd_summary?.location || null })),
    items: demo.items.filter((i) => !i.dismissed).map((i) => ({ ...i, hidden_because: i.details?.hidden_because,
      subject: i.details?.subject, venue: i.details?.venue, pdf: i.details?.pdf, kind: i.details?.kind, notice_time: i.details?.notice_time,
      via: i.details?.via, mail: i.details?.mail, todo: i.details?.todo })),
    notices: demo.notices,
  };
}

// the live evals' checks (evals/ask_ping/run_ask_ping_evals.py score)
const norm = (s) => s.toLowerCase().replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
function numbersIn(text) {
  const out = [];
  for (const m of text.matchAll(/(\d+(?:[.,]\d+)*)\s*(lpa|lakhs?|l\b|cr\b|crores?)?/gi)) {
    let s = m[1];
    if (/^\d{1,3}(,\d{2})*,\d{3}$/.test(s) || /^\d{1,3}(,\d{3})+$/.test(s)) s = s.replace(/,/g, "");
    let v = Number(s.replace(/,/g, ""));
    if (isNaN(v)) continue;
    const u = (m[2] || "").toLowerCase();
    if (/^(lpa|lakh|lakhs|l)$/.test(u)) v *= 1e5; else if (/^(cr|crore|crores)$/.test(u)) v *= 1e7;
    out.push(v);
  }
  return out;
}
function score(answer, checks) {
  const a = norm(answer), failed = [];
  for (const item of checks.must_contain || []) if (!item.split("|").some((alt) => a.includes(alt.trim().toLowerCase()))) failed.push(`must_contain '${item.slice(0, 60)}'`);
  for (const item of checks.must_not_contain || []) if (a.includes(item.toLowerCase())) failed.push(`must_not_contain '${item}'`);
  for (const n of checks.numbers_present || []) {
    const want = Number(n);
    if (!numbersIn(answer).some((v) => (want >= 1e5 ? Math.abs(v - want) <= want * 0.005 : v === want))) failed.push(`numbers_present ${n}`);
  }
  if (checks.max_words && answer.split(/\s+/).length > checks.max_words) failed.push(`max_words ${checks.max_words} (had ${answer.split(/\s+/).length})`);
  return failed;
}

const all = process.argv.includes("--all");
const only = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1].split(",") : null;
const show = process.argv.includes("--show");
const rows = [];
function ask(q, previous, asOf) {
  const d = data(asOf || spec.snapshot_as_of);
  const t = Date.now();
  // preferences and JD questions are answered before the router (prefs.ts, the JD path): counted as rules too
  if (/^(only show|also include|don't count|remind me|stop listing|reset my|what are my preferences|show me product)/i.test(q)) return { kind: "prefs", text: "(preferences: prefs.ts)", ms: 0 };
  const r = R.route(q, previous, d);
  const out = r.kind === "open" && !all ? { text: "(model)" } : R.routed(r, q, d);
  return { kind: r.kind, why: r.why, text: out.text, ms: Date.now() - t };
}
for (const c of spec.cases) {
  if (only && !only.some((o) => c.id === o || c.id.startsWith(o))) continue;
  const a = ask(c.question, [], c.as_of);
  const failed = a.kind === "open" && !all ? null : a.kind === "prefs" ? [] : score(a.text, c.checks);
  rows.push({ id: c.id, q: c.question, kind: a.kind, why: a.why, failed, text: a.text, ms: a.ms });
}
for (const conv of only ? [] : spec.conversations || []) {
  const prev = [];
  conv.turns.forEach((t, k) => {
    const a = ask(t.question, [...prev].reverse(), conv.as_of);
    const failed = a.kind === "open" && !all ? null : a.kind === "prefs" ? [] : score(a.text, t.checks);
    rows.push({ id: `${conv.id}.${k + 1}`, q: t.question, kind: a.kind, why: a.why, failed, text: a.text, ms: a.ms });
    prev.push(t.question);
  });
}
for (const r of rows) {
  const st = r.failed == null ? "OPEN" : r.failed.length ? "FAIL" : "pass";
  console.log(`${r.id.padEnd(6)} ${st.padEnd(4)} ${r.kind.padEnd(5)} ${r.q.slice(0, 52).padEnd(52)} ${r.failed?.length ? r.failed.join("; ") : ""}`);
  if (show || (r.failed && r.failed.length)) console.log("        " + r.text.replace(/\n/g, "\n        ").slice(0, 900));
}
const singles = rows.filter((r) => !r.id.includes("."));
const turns = rows.filter((r) => r.id.includes("."));
const sum = (rs) => `${rs.filter((r) => r.failed && !r.failed.length).length} pass, ${rs.filter((r) => r.failed?.length).length} fail, ${rs.filter((r) => r.failed == null).length} open`;
console.log(`\nsingle questions: ${sum(singles)}  |  conversation turns: ${sum(turns)}`);
