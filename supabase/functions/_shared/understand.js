/* Ask Ping, the model's two small jobs (the rules do everything in between). Plain script like answer_rules.js:
 * window.PingUnderstand in the page, globalThis.PingUnderstand in the function, module.exports in Node tests.
 *
 * 1. understand: the question + the last 6 turns + the known companies and roles -> JSON only
 *    {company, role, fact, source, is_followup, scope}. Validated against the data: a company or role the data
 *    doesn't have becomes null; anything else unknown becomes "other" / "any". It never answers anything.
 *    The rules then get the question with what it left out filled in ("what all roles?" after "risa jd?" ->
 *    "what all roles? RISA Labs"): what the student said always wins.
 * 2. compose: the rules' answer (every fact fetched) rewritten as a short, natural reply. Kept only if every date,
 *    time, number, company, role, status word and link in it is in the rules' answer, and every link and chip of the
 *    rules' answer is still there. Otherwise the rules' answer is sent as it is.
 * Both have a time cap; past it, or on any error, the rules path alone answers. Tested in tests/js/understand.test.js.
 */
(function (root) {
  const FACTS = ["jd", "ctc", "eligibility", "deadline", "form", "test", "shortlist", "roles", "cv", "other"];
  const SOURCES = ["erp", "notice", "mail", "form", "any"];
  // a fact as the rules' router spells it, when the question didn't
  const FACT_WORDS = { jd: "jd", ctc: "ctc", eligibility: "eligibility", deadline: "deadline", form: "form", test: "test",
                       shortlist: "shortlist", roles: "what all roles", cv: "which cv" };
  const FACT_INTENT = { jd: "jd", ctc: "pay", eligibility: "eligible", deadline: "deadline", form: "form", test: "test",
                        shortlist: "shortlist", roles: "roles", cv: "whichcv" };
  const SOURCE_WORDS = { erp: "on the erp", notice: "in notices", mail: "on mail", form: "on the form page" };

  function prompt({ question, turns, companies, roles }) {
    const convo = (turns || []).slice(-6).map((t) => `${t.role === "me" ? "Student" : "Ping"}: ${String(t.text || "").slice(0, 300)}`).join("\n");
    return `You read a student's message to a placement assistant. Reply with ONE JSON object and nothing else:
{"company": string|null, "role": string|null, "fact": one of ${JSON.stringify(FACTS)}, "source": one of ${JSON.stringify(SOURCES)}, "is_followup": true|false, "scope": "one"|"all"}
- company: the company the message is about, written as in the list below; if the message names none but continues the conversation, the company the conversation is about; null if none.
- role: a role of that company from the list below if the message names or means one; else null.
- fact: what is asked (jd = job description, ctc = pay, eligibility, deadline, form, test, shortlist, roles = which roles, cv = which CV to use; other).
- source: where the student wants it looked up (erp, notice, mail, form) if they say so; else any.
- is_followup: the message only makes sense with the earlier messages.
- scope: "all" when the message asks about every role / every company ("all roles", "everything"), else "one".
Never invent a company or role that isn't in the lists.

Companies: ${(companies || []).slice(0, 200).join("; ")}
Roles of the companies in the conversation: ${(roles || []).slice(0, 60).join("; ") || "(none)"}

Conversation, oldest first:
${convo || "(none)"}

Message: ${question}`;
  }

  function parse(text) {
    const m = String(text || "").match(/\{[\s\S]*\}/);
    if (!m) return null;
    try { return JSON.parse(m[0]); } catch { return null; }
  }

  const words = (s) => String(s || "").toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length >= 2);
  // the model's JSON, checked against the data: names it can't point to are dropped
  function validate(raw, data, Rules) {
    if (!raw || typeof raw !== "object") return null;
    const out = { company: null, companyRaw: [], role: null, fact: FACTS.includes(raw.fact) ? raw.fact : "other",
                  source: SOURCES.includes(raw.source) ? raw.source : "any", is_followup: raw.is_followup === true,
                  scope: raw.scope === "all" ? "all" : "one" };
    if (raw.company && typeof raw.company === "string") {
      const hits = Rules.matchCompanies(raw.company, data).hits;
      if (hits.length === 1) { out.company = hits[0].name; out.companyRaw = [...hits[0].raw]; }
    }
    if (out.company && raw.role && typeof raw.role === "string") {
      const want = new Set(words(raw.role));
      const own = (data.roles || []).filter((r) => out.companyRaw.includes(r.company));
      const exact = own.find((r) => words(r.designation).join(" ") === words(raw.role).join(" "));
      // distinct words in common, then the fewest extra words ("APM - Growth" over "APM - Product Operations")
      const scored = own.map((r) => { const w = new Set(words(r.designation)); const hit = [...w].filter((x) => want.has(x)).length;
                                      return [r, hit, w.size - hit]; });
      const best = Math.max(0, ...scored.map((x) => x[1]));
      const top = scored.filter((x) => x[1] === best && best > 0).sort((a, b) => a[2] - b[2]);
      if (exact) out.role = exact.designation;
      else if (top.length === 1 || (top.length > 1 && top[0][2] < top[1][2])) out.role = top[0][0].designation;
    }
    return out;
  }

  // the question with what it left out filled in from the understanding; never changes what it says
  function augment(question, u, data, Rules) {
    if (!u) return question;
    let q = String(question || "");
    const add = [];
    if (u.company && !Rules.matchCompanies(q, data).hits.length) add.push(u.company);
    if (u.role && !words(q).some((w) => w.length >= 4 && words(u.role).includes(w))) add.push(u.role);
    const intents = Rules.intentsOf(q);
    if (u.fact !== "other" && !intents.has(FACT_INTENT[u.fact]) && !(u.fact === "roles" && intents.has("roles"))) add.push(FACT_WORDS[u.fact]);
    if (u.source !== "any" && !Rules.sourcesOf(q).length) add.push(SOURCE_WORDS[u.source]);
    return add.length ? `${q} ${add.join(" ")}` : q;
  }

  // ---------------------------------------------------------------- compose + the check
  function composePrompt({ question, answer }) {
    return `Rewrite this answer from a placement assistant so it reads naturally for a hurried student: short, plain, no greeting, no sign-off. Use ONLY what the answer says: do not add, drop or change any company, role, date, time, number, status or link. Keep every markdown link and button exactly as written, e.g. [Open](https://...) or [Associate Product Manager](#ask:...). Keep it at most as long as the answer. Reply with the rewritten answer only.

Student asked: ${question}

Answer:
${answer}`;
  }
  const LINK = /\[([^\]]+)\]\(([^)\s]+)\)/g;
  const linksOf = (s) => [...String(s || "").matchAll(LINK)].map((m) => `[${m[1]}](${m[2]})`);
  const lower = (s) => String(s || "").toLowerCase().replace(/\s+/g, " ");
  const STATUS = /\b(not applied|applied|not eligible|eligible|closed|open|past due|over|filled|shortlisted|on the list|not on the list|extended|cancelled|postponed|no deadline)\b/g;
  const MON = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec";
  function verify(reply, facts, data, companyNames = []) {
    const r = String(reply || "").trim(), f = String(facts || "");
    if (!r) return { ok: false, why: "empty" };
    if (r.length > f.length * 1.25 + 60) return { ok: false, why: "longer than the facts" };
    const fl = lower(f), rl = lower(r);
    const fLinks = new Set(linksOf(f)), rLinks = linksOf(r);
    for (const l of rLinks) if (!fLinks.has(l)) return { ok: false, why: `link not in the facts: ${l.slice(0, 60)}` };
    for (const l of fLinks) if (!rLinks.includes(l)) return { ok: false, why: `link dropped: ${l.slice(0, 60)}` };
    const bare = rl.replace(LINK, " ");
    for (const m of bare.matchAll(/https?:\/\/\S+/g)) if (!fl.includes(m[0])) return { ok: false, why: "url not in the facts" };
    for (const m of bare.matchAll(new RegExp(`\\b\\d{1,2}:\\d{2}\\b|\\b\\d{1,2} (?:${MON})[a-z]*\\b|\\b(?:${MON})[a-z]* \\d{1,2}\\b|\\b\\d+(?:[.,]\\d+)?\\b`, "g")))
      if (!fl.includes(m[0])) return { ok: false, why: `"${m[0]}" not in the facts` };
    for (const m of bare.matchAll(STATUS)) if (!fl.includes(m[0])) return { ok: false, why: `status "${m[0]}" not in the facts` };
    // companies and roles: any the data knows that the reply names must be in the facts
    const names = new Set();
    for (const ro of data?.roles || []) {
      if (ro.designation && ro.designation.length >= 4) names.add(lower(ro.designation));
    }
    for (const e of companyNames) if (e) names.add(lower(e));
    for (const n of names) if (n.length >= 4 && bare.includes(n) && !fl.includes(n)) return { ok: false, why: `name "${n}" not in the facts` };
    return { ok: true };
  }

  // ---------------------------------------------------------------- with a time cap
  const capped = (p, ms) => Promise.race([p, new Promise((res) => setTimeout(() => res({ timeout: true }), ms))]);

  // call(prompt, ms) -> Promise<{text, model}> (the environment's model chain); never throws
  async function understand({ question, turns, data, Rules, call, capMs = 3000 }) {
    const t0 = Date.now();
    const ents = Rules.entities(data);
    const companies = [...new Set(ents.filter((e) => e.roles || (data.roles || []).some((r) => e.raw.has(r.company))).map((e) => e.name))];
    const about = new Set((turns || []).slice(-6).concat([{ text: question }]).flatMap((t) => Rules.matchCompanies(String(t.text || ""), data).hits.flatMap((e) => [...e.raw])));
    const roles = (data.roles || []).filter((r) => about.has(r.company)).map((r) => `${Rules.shortName(r.company)}: ${r.designation}`);
    let res;
    try { res = await capped(call(prompt({ question, turns, companies, roles }), capMs), capMs); } catch (e) { res = { error: String(e) }; }
    const ms = Date.now() - t0;
    if (!res || res.timeout || res.error || !res.text) return { u: null, ms, model: res?.model || null, fell: true, why: res?.timeout ? "timeout" : res?.error || "empty" };
    const u = validate(parse(res.text), data, Rules);
    return { u, ms, model: res.model, fell: !u, why: u ? null : "unparsable" };
  }

  async function compose({ question, answer, data, companyNames = [], call, capMs = 2500 }) {
    const t0 = Date.now();
    if (!answer || answer.length < 40) return { text: answer, ms: 0, used: false, why: "short" };
    let res;
    try { res = await capped(call(composePrompt({ question, answer }), capMs), capMs); } catch (e) { res = { error: String(e) }; }
    const ms = Date.now() - t0;
    if (!res || res.timeout || res.error || !res.text) return { text: answer, ms, used: false, why: res?.timeout ? "timeout" : res?.error || "empty" };
    const v = verify(res.text, answer, data, companyNames);
    return v.ok ? { text: res.text.trim(), ms, used: true, model: res.model } : { text: answer, ms, used: false, why: v.why };
  }

  const api = { FACTS, SOURCES, prompt, parse, validate, augment, composePrompt, verify, understand, compose };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingUnderstand = api;
})(typeof window !== "undefined" ? window : globalThis);
