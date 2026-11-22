// The multi-turn and re-check evals (evals/ask_ping/multiturn.json) typed into the page, the way a person asks:
// once with the model on (an anonymous demo session: the ask-ping function answers OPEN questions) and once with it
// off (the ask-ping function blocked: the page's rules answer everything). Each turn records who answered and the
// text; a re-check turn must be answered by a re-check (a fetch, with its time), never by the old answer again.
//   node setup/multiturn_page_evals.js [url]     -> evals/ask_ping/MULTITURN.md, evals/ask_ping/multiturn_results.json
const fs = require("fs");
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const E = JSON.parse(fs.readFileSync("evals/ask_ping/multiturn.json", "utf8"));
const NEVER = new RegExp(E.never.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "i");

async function session(b, modelOn) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  if (!modelOn) await ctx.route(/functions\/v1\/ask-ping/, (r) => r.abort());
  await p.goto(`${BASE}?anon-demo=1`); await p.click("#view-demo");
  await p.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
  if (await p.locator(".chips .chip:has-text('Use the demo profile')").count()) await p.click(".chips .chip:has-text('Use the demo profile')");
  await p.waitForSelector("#ask-input", { timeout: 30000 });
  await p.waitForTimeout(1500);
  return { ctx, p };
}
async function ask(p, q) {
  const n = await p.locator(".msg.ping:not(.typing):not(.r-active)").count();
  await p.fill("#ask-input", q); await p.press("#ask-input", "Enter");
  const sawCheck = p.waitForSelector(".msg.ping.r-active[data-recheck]", { timeout: 4000 }).then(() => true).catch(() => false);
  await p.waitForFunction((n) => document.querySelectorAll(".msg.ping:not(.typing):not(.r-active)").length > n, n, { timeout: 60000 });
  const last = p.locator(".msg.ping:not(.typing):not(.r-active)").last();
  return { text: (await last.locator(".text").innerText()).replace(/\s+/g, " ").trim(), by: await last.getAttribute("data-answered-by"),
           checking: await sawCheck };
}
(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  const results = [];
  for (const modelOn of [true, false]) {
    const { ctx, p } = await session(b, modelOn);
    for (const c of E.cases) {
      const turns = [];
      let pass = true;
      for (const t of c.turns) {
        const a = await ask(p, t.q);
        const why = [];
        if (t.route === "recheck") {
          if (a.by !== "recheck") why.push(`answered by ${a.by}, not a re-check`);
          if (!/\(\d{2}:\d{2}\)/.test(a.text)) why.push("no fetch time");
          if (t.company && !a.text.toLowerCase().includes(t.company.toLowerCase())) why.push(`not about ${t.company}`);
        } else if (a.by === "recheck") why.push("a re-check where a question was asked");
        if (t.company && t.route !== "recheck" && !a.text.toLowerCase().includes(t.company.toLowerCase())) why.push(`doesn't mention ${t.company}`);
        if (t.company === null && /groww/i.test(a.text) && !/due/i.test(a.text)) why.push("stayed on the old topic");
        if (NEVER.test(a.text)) why.push("asserts absence");
        if (/\*\*/.test(a.text)) why.push("literal **");
        if (why.length) pass = false;
        turns.push({ q: t.q, expected: t.route, ...a, problems: why });
      }
      results.push({ id: c.id, model: modelOn ? "on" : "off", pass, turns });
      console.log(`${pass ? "ok  " : "FAIL"} ${c.id} model ${modelOn ? "on " : "off"}: ${turns.map((t) => `${t.q} -> [${t.by}] ${t.text.slice(0, 70)}${t.problems.length ? ` !! ${t.problems.join("; ")}` : ""}`).join(" | ")}`);
    }
    await ctx.close();
  }
  await b.close();
  const passed = results.filter((r) => r.pass).length;
  fs.writeFileSync("evals/ask_ping/multiturn_results.json", JSON.stringify({ at: new Date().toISOString(), url: BASE, results }, null, 1));
  const md = [`# Multi-turn and re-check evals (page)`, "", `Run ${new Date().toISOString()} on ${BASE}, demo session. ${passed}/${results.length} passed (${E.cases.length} conversations, model on and off).`, "",
    "A re-check in the demo answers from the snapshot (the demo can't log in to the ERP) and says so; for the owner it is a live, read-only fetch of that company's notices and files.", "",
    "| case | model | result | turns |", "|---|---|---|---|",
    ...results.map((r) => `| ${r.id} | ${r.model} | ${r.pass ? "pass" : "FAIL"} | ${r.turns.map((t) => `"${t.q}" → ${t.by}: ${t.text.slice(0, 90).replace(/\|/g, "/")}${t.problems.length ? ` (${t.problems.join("; ")})` : ""}`).join("<br>")} |`)];
  fs.writeFileSync("evals/ask_ping/MULTITURN.md", md.join("\n") + "\n");
  console.log(`\n${passed}/${results.length} passed`);
  process.exit(passed === results.length ? 0 : 1);
})();
