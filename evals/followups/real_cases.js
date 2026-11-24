// The follow-up cases in your real chat history (evals/followups/run.js --real), built without any model call.
//
// A. Your real follow-ups: a question that names no company and is about one you'd just been on:
//    - a reply to a message that names one company (the page asks it about that company, as Ask Ping does), or
//    - asked within 30 min of an earlier question of yours (any of the last 3) whose newest company-naming one names
//      exactly one company.
// B. Your own questions with the company left out: each of your questions that names exactly one company, with the
//    company's words taken out ("nomura jd?" -> "jd"), asked after your nearest other question about a different
//    company. Real wording on both sides, on your real data; the answer must be about the earlier question's company.
// Preferences, help, feedback and questions too short to mean anything are skipped in both.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PingRealCases = factory();
})(typeof self !== "undefined" ? self : this, function () {
  const WINDOW = 30 * 60000, HISTORY = 12, B_CAP = 40;

  function build(R, data, chat) {
    const ents = R.entities(data);
    const hitsOf = (t) => R.matchCompanies(String(t || ""), data, ents);
    const skip = (t) => !/[a-z]{2}/i.test(t) || R.feedbackLike(t) || R.prefsLike(t) || R.helpTopic(t);
    const historyBefore = (i) => chat.slice(Math.max(0, i - HISTORY), i).map((x) => ({ role: x.role, text: x.text }));
    const previousBefore = (i) => historyBefore(i).filter((x) => x.role === "me").map((x) => x.text).reverse();
    const A = [], B = [];

    // A: real follow-ups
    for (let i = 1; i < chat.length; i++) {
      const m = chat[i];
      if (m.role !== "me" || skip(m.text) || hitsOf(m.text).hits.length) continue;
      let company = null, how = null, ask = m.text;
      const quoted = m.reply_quote && m.reply_quote.text ? hitsOf(m.reply_quote.text).hits : [];
      if (quoted.length === 1) {
        company = quoted[0].name; how = "reply";
        ask = `${m.text} ${R.shortName(company)}`;                     // what the page and the function route
      } else if (!m.reply_to) {
        const t = Date.parse(m.created_at);
        const earlier = chat.slice(0, i).filter((x) => x.role === "me" && t - Date.parse(x.created_at) <= WINDOW).slice(-3).reverse();
        const named = earlier.find((x) => hitsOf(x.text).hits.length);
        if (named && hitsOf(named.text).hits.length === 1) { company = hitsOf(named.text).hits[0].name; how = "after a question"; }
      }
      if (!company) continue;
      A.push({ group: "A", how, q: m.text, ask, company, previous: previousBefore(i), history: historyBefore(i) });
    }

    // B: your own questions with the company left out
    const named = [];
    chat.forEach((m, i) => {
      if (m.role !== "me" || skip(m.text)) return;
      const { hits, used } = hitsOf(m.text);
      if (hits.length === 1) named.push({ i, m, company: hits[0].name, used });
    });
    for (const n of named) {
      if (B.length >= B_CAP) break;
      const toks = String(n.m.text).toLowerCase().replace(/[^a-z0-9?' ]+/g, " ").split(/\s+/).filter(Boolean);
      const left = toks.filter((t) => !n.used.has(t.replace(/[?']/g, "")));
      const q = left.join(" ").trim();
      if (!/[a-z]{2}/.test(q) || q.replace(/[^a-z]/g, "").length < 2 || hitsOf(q).hits.length || skip(q)) continue;
      const route = R.route(q, [], data);
      if (route.kind === "help" || route.kind === "feedback") continue;
      // the nearest other question of yours about a different company: the topic
      const others = named.filter((x) => x.company !== n.company);
      if (!others.length) continue;
      const prev = others.reduce((a, b) => (Math.abs(b.i - n.i) < Math.abs(a.i - n.i) ? b : a));
      const pr = R.route(prev.m.text, [], data);
      const history = [{ role: "me", text: prev.m.text }, { role: "ping", text: pr.kind === "open" ? "" : R.routed(pr, prev.m.text, data).text }];
      B.push({ group: "B", how: "company left out", q, ask: q, company: prev.company, previous: [prev.m.text], history });
    }
    return { A, B };
  }
  return { build, WINDOW, HISTORY, B_CAP };
});
