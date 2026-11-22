// Every failure a visitor can run into, simulated on the live site in one anonymous demo session (?anon-demo=1): what the page says,
// and that there is a way on. (The run's own failures, ERP refused and 3 failed checks, are chat messages written by
// the hourly run: tests/test_end_to_end.py covers them.)
//   node setup/failure_states.js [url]
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const OPEN_Q = "why should I pick slice over groww?";
let bad = 0;
const rows = [];
const check = (ok, state, said) => { if (!ok) bad++; rows.push([state, ok ? "ok" : "FAIL", said]); };

async function ask(p, q, ms = 30000) {
  const n = await p.locator(".msg.ping:not(.typing)").count();
  await p.fill("#ask-input", q); await p.press("#ask-input", "Enter");
  await p.waitForFunction((n) => !document.querySelector(".msg.typing") && document.querySelectorAll(".msg.ping:not(.typing)").length > n, n, { timeout: ms });
  return (await p.locator(".msg.ping:not(.typing) .text").last().innerText()).replace(/\s+/g, " ");
}

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto(`${BASE}?anon-demo=1`); await p.click("#view-demo");
  await p.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
  if (await p.locator(".chips .chip:has-text('Use the demo profile')").count()) await p.click(".chips .chip:has-text('Use the demo profile')");
  await p.waitForSelector("#ask-input"); await p.waitForTimeout(1500);

  // 1. the function is down (network error): FACT still answered in the page; OPEN gets the rules answer + why
  await p.route("**/functions/v1/ask-ping", (r) => r.abort("failed"));
  let a = await ask(p, OPEN_Q);
  check(/couldn.t be reached/.test(a) && a.length > 80, "Ask Ping function unreachable", a.slice(-160));
  a = await ask(p, "what's due tomorrow");
  check(!/reached/.test(a), "  a FACT question meanwhile (answered in the page)", a.slice(0, 120));
  await p.unroute("**/functions/v1/ask-ping");

  // 2. the function errors (HTTP 500)
  await p.route("**/functions/v1/ask-ping", (r) => r.request().postData()?.includes("question")
    ? r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: "boom" }) }) : r.continue());
  a = await ask(p, OPEN_Q);
  check(/couldn.t be reached/i.test(a) && !/boom/.test(a) && a.length > 80, "Ask Ping function error (500)", a.slice(-160));
  await p.unroute("**/functions/v1/ask-ping");

  // 3. Gemini busy: the function answers by rules (no_ai stands in for a model that didn't answer)
  await p.route("**/functions/v1/ask-ping", (r) => { const d = JSON.parse(r.request().postData() || "{}");
    if (d.question) d.no_ai = true; r.continue({ postData: JSON.stringify(d) }); });
  a = await ask(p, OPEN_Q);
  check(a.length > 40 && !/error/i.test(a), "Gemini busy (the rules answer)", a.slice(0, 160));
  await p.unroute("**/functions/v1/ask-ping");

  // 4. the demo's hourly question limit (HTTP 429)
  await p.route("**/functions/v1/ask-ping", (r) => r.request().postData()?.includes("question")
    ? r.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ error: "The demo has had a lot of questions this hour. Try again in a few minutes." }) }) : r.continue());
  a = await ask(p, OPEN_Q);
  check(/a lot of questions|try again/i.test(a) && /Meanwhile/.test(a), "Demo rate limit (429)", a.slice(0, 200));
  await p.unroute("**/functions/v1/ask-ping");

  // 5. offline: the banner, and a message waits and is sent when the connection is back
  await ctx.setOffline(true);
  await p.evaluate(() => window.dispatchEvent(new Event("offline"))); await p.waitForTimeout(500);
  const banner = await p.locator(".offline, [data-offline], .banner").first().innerText().catch(() => "");
  await p.fill("#ask-input", "what's due tomorrow"); await p.press("#ask-input", "Enter"); await p.waitForTimeout(600);
  const queued = await p.locator(".msg.me").last().innerText().catch(() => "");
  check(/offline|connection/i.test(banner) || /wait|queued|send when/i.test(queued), "Offline (banner, message waits)", `${banner.slice(0, 100)} | ${queued.slice(0, 100)}`);
  await ctx.setOffline(false);
  await p.evaluate(() => window.dispatchEvent(new Event("online"))); await p.waitForTimeout(2500);
  const after = await p.locator(".msg.ping:not(.typing) .text").last().innerText().catch(() => "");
  check(/tomorrow|due/i.test(after), "  back online: the waiting message is answered", after.replace(/\s+/g, " ").slice(0, 100));

  // 6. Realtime (the socket) down: the page says so and catches up on focus (setup/live_page_test.py checks this live)
  check(errs.length === 0, "No page errors through all of it", errs.slice(0, 2).join("; ") || "none");

  // 7. the demo sign-in refused (Supabase's anonymous sign-ins per hour used up): a plain message, then the same snapshot
  //    from the site's own copy
  const c2 = await b.newContext({ viewport: { width: 390, height: 844 } }); const p2 = await c2.newPage();
  await p2.route("**/auth/v1/signup**", (r) => r.fulfill({ status: 429, contentType: "application/json",
    body: JSON.stringify({ code: 429, error_code: "over_request_rate_limit", msg: "Request rate limit reached" }) }));
  await p2.goto(`${BASE}?anon-demo=1`); await p2.click("#view-demo"); await p2.waitForTimeout(300);
  const said = (await p2.locator("body").innerText()).replace(/\s+/g, " ").match(/The live demo[^…]*…/)?.[0] || "";
  const opened = await p2.waitForSelector(".msg.item", { timeout: 30000 }).then(() => true).catch(() => false);
  check(!!said && !/rate limit/i.test(said) && opened && /demo=1/.test(p2.url()), "Demo sign-in refused (429)", `${said} -> ${p2.url().replace(BASE, "")}`);
  await c2.close();
  await b.close();
  for (const [s, r, said] of rows) console.log(`${r.padEnd(4)} ${s}\n       "${said}"`);
  console.log(`\n${bad} problem(s)`);
  process.exit(bad ? 1 : 0);
})();
