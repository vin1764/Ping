// Every answer the live bot gave that said something isn't there ("no JD", "I don't have", "No open deadline", "not
// found"...), asked again now with the same earlier questions, against today's data and rules; and checked against
// the data itself (the oracle in generate.js). Lists the ones that were wrong.
//   node evals/generated/audit_chat.js <facts.json> <chat.json>     (chat: [{role, text, created_at}] oldest first)
const fs = require("fs");
const R = require(process.env.PING_RULES || "../../supabase/functions/_shared/answer_rules.js");
const G = require("./generate.js");

const ABSENT = /\bno jd\b|\bi don'?t have\b|\bno open deadline\b|\bnot found\b|\bno (ctc|pay|cg cut-off|test|shortlist|form|cv suggestion|location|job location)\b|\bnone\b|\bnothing (is )?(due|in|on|new)\b|\bcouldn'?t find\b(?! your roll)/i;
const FIELD_OF = { jd: "jd", pay: "ctc", eligible: "eligibility", deadline: "deadline", form: "form", test: "test", shortlist: "shortlist", whichcv: "whichcv" };

function audit(d, chat) {
  const out = [];
  for (let i = 0; i < chat.length; i++) {
    const a = chat[i];
    if (a.role !== "ping" || !ABSENT.test(a.text)) continue;
    const qi = chat.slice(0, i).map((m, k) => [m, k]).filter(([m]) => m.role === "me").pop();
    if (!qi) continue;
    const [q, k] = qi;
    const earlier = chat.slice(0, k).filter((m) => m.role === "me").map((m) => m.text).reverse().slice(0, 3);
    const lastAnswer = chat.slice(0, k).filter((m) => m.role === "ping").map((m) => m.text).pop() || null;
    const data = { ...d, lastAnswer };
    const r = R.route(q.text, earlier, data);
    const now = r.kind === "open" ? null : R.routed(r, q.text, data).text;
    // what the data says, for the company and the field asked about
    const field = (r.spec?.intents || []).map((x) => FIELD_OF[x]).find(Boolean);
    const company = r.spec?.hits?.[0] ? [...r.spec.hits[0].raw][0] : null;
    const t = field && company ? G.truth(company, field, d) : null;
    const present = t && !t.absent && !t.soft;
    const nowAbsent = now ? ABSENT.test(now.split("\n")[0]) : null;
    out.push({ at: a.created_at, q: q.text, then: a.text.split("\n")[0].slice(0, 160), now: (now || "(left to the model)").split("\n")[0].slice(0, 200),
               field, company: company ? R.shortName(company) : null, truth: t,
               verdict: present ? "WRONG: the data has it" : now && !nowAbsent && !/^As in my last answer|^Nothing new|^Still nothing/.test(now) ? "WRONG: found now" : "ok" });
  }
  return out;
}

if (require.main === module) {
  const d = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const chat = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
  const rows = audit(d, chat);
  const wrong = rows.filter((x) => x.verdict !== "ok");
  console.log(`absence answers in the chat history: ${rows.length}; wrong: ${wrong.length}`);
  for (const x of rows) console.log(`${x.verdict === "ok" ? "  ok   " : "  WRONG"} ${String(x.at).slice(0, 16)} | ${x.q.slice(0, 60)} | then: ${x.then} | now: ${x.now}` +
    (x.verdict !== "ok" ? ` | ${x.verdict}${x.truth ? ` (${JSON.stringify(x.truth)})` : ""}` : ""));
}
module.exports = { audit };
