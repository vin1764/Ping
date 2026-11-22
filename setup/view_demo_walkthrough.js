// View demo from the sign-in screen, as a visitor: a fresh browser at 390x844 and 1280x800, no URL parameter, tap
// View demo, ask four questions, open Today, Forms and Companies. Then the fallback: anonymous sign-ins refused (the
// hourly limit) -> the same snapshot opens from the page itself.   node setup/view_demo_walkthrough.js [url]
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
let bad = 0;
const ok = (c, what, note = "") => { if (!c) bad++; console.log(`${c ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };
async function ask(p, q) {
  const n = await p.locator(".msg.ping:not(.typing):not(.r-active)").count();
  await p.fill("#ask-input", q); await p.press("#ask-input", "Enter");
  await p.waitForFunction((n) => document.querySelectorAll(".msg.ping:not(.typing):not(.r-active)").length > n, n, { timeout: 60000 });
  return (await p.locator(".msg.ping[data-answered-by]").last().innerText()).replace(/\s+/g, " ").slice(0, 110);
}
(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hh] of [[390, 844], [1280, 800]]) {
    console.log(`\n${w}x${hh}`);
    const ctx = await b.newContext({ viewport: { width: w, height: hh } });
    const p = await ctx.newPage();
    const errs = []; p.on("pageerror", (e) => errs.push(e.message));
    await p.goto(BASE);
    const btn = p.locator("#view-demo");
    await btn.waitFor({ timeout: 30000 });
    ok(await btn.isVisible() && (await btn.innerText()).trim() === "View demo", "View demo under the sign-in (no URL parameter)");
    await btn.click();
    await p.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
    if (await p.locator(".chips .chip:has-text('Use the demo profile')").count()) await p.click(".chips .chip:has-text('Use the demo profile')");
    await p.waitForSelector("#ask-input", { timeout: 30000 });
    const keys = await p.evaluate(() => Object.keys(localStorage).filter((k) => /auth/.test(k)));
    ok(keys.includes("ping-demo-auth") && !keys.includes("ping-auth"), "its own session key (ping-demo-auth), not the owner's", keys.join(","));
    for (const q of ["what's due tonight", "any tests today?", "anything else?", "which cv for blackbuck"]) {
      const a = await ask(p, q);
      ok(a.length > 10 && !/something went wrong|error/i.test(a), `"${q}"`, a);
    }
    for (const [route, sel] of [["today", ".today-row, .today-empty"], ["forms", "#forms-list .form-row"], ["companies", "#company-search"]]) {
      await p.evaluate((r) => { location.hash = `#${r}`; }, route);
      const seen = await p.waitForSelector(sel, { timeout: 20000 }).then(() => true).catch(() => false);
      let note = "";
      if (route === "forms") {
        await p.click('[data-only="all"]').catch(() => {});
        const f = await p.evaluate(() => { const rows = [...document.querySelectorAll(".form-row")];
          const sig = rows.map((r) => r.querySelector(".fr-head")?.innerText + "|" + r.querySelector(".fr-cos")?.innerText + "|" + r.querySelector(".fr-meta .num")?.innerText);
          return { rows: rows.length, dup: sig.length - new Set(sig).size, prompts: document.querySelectorAll(".looks-like, [data-merge]").length }; });
        note = JSON.stringify(f);
        ok(f.dup === 0 && f.prompts === 0, "Forms: no duplicate rows, no merge prompts", note);
      }
      if (route === "companies") note = `${await p.locator("text=/Closes /").count()} role cards`;
      ok(seen, `${route} renders`, note);
      await p.screenshot({ path: `docs/screenshots/final/viewdemo-${route}-${w}.png` });
    }
    ok(!errs.length, "no page errors", errs.slice(0, 2).join("; "));
    await ctx.close();
  }
  // the fallback: anonymous sign-ins refused (the hourly limit) -> the snapshot from the page itself
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  await ctx.route(/\/auth\/v1\/signup/, (r) => r.fulfill({ status: 429, contentType: "application/json", body: '{"msg":"Request rate limit reached"}' }));
  const p = await ctx.newPage();
  await p.goto(BASE); await p.click("#view-demo");
  const fell = await p.waitForURL(/[?&]demo=1/, { timeout: 15000 }).then(() => true).catch(() => false);
  const chat = fell && await p.waitForSelector(".msg.item", { timeout: 30000 }).then(() => true).catch(() => false);
  ok(fell && chat, "sign-in limit reached: the same snapshot opens from the page", p.url());
  await b.close();
  console.log(`\n${bad} problem(s)`); process.exit(bad ? 1 : 0);
})();
