// A demo visitor's first minutes, at 390x844 and 1280x800: View demo, the first onboarding bubble, the walk-through
// (each step), then the feed, Today, Forms, Companies and Profile. Screenshots to <out>/demo-*.png.
//   node setup/ux_walk_demo.js <out dir> [url]
const fs = require("fs");
const { chromium } = require("playwright");
const OUT = process.argv[2] || "docs/screenshots/ux/after";
const BASE = process.argv[3] || "https://vin1764.github.io/ping-dashboard/";
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hh] of [[390, 844], [1280, 800]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: hh } });
    const p = await ctx.newPage();
    const errs = []; p.on("pageerror", (e) => errs.push(e.message));
    // one tap: a fresh visitor's "Use the demo profile" lands on the feed
    { const c2 = await b.newContext({ viewport: { width: w, height: hh } }); const q = await c2.newPage();
      await q.goto(BASE); await q.click("#view-demo");
      await q.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
      const t0 = Date.now();
      await q.locator(".chip", { hasText: "Use the demo profile" }).first().click();
      await q.waitForSelector("#ask-input", { timeout: 30000 });
      await q.waitForTimeout(800);
      await q.screenshot({ path: `${OUT}/demo-one-tap-feed-${w}.png` });
      console.log(w, "Use the demo profile -> feed in", Date.now() - t0, "ms; items:", await q.locator(".msg.ping").count());
      await c2.close(); }
    await p.goto(BASE); await p.click("#view-demo");
    await p.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
    await p.waitForTimeout(600);
    await p.screenshot({ path: `${OUT}/demo-onb-welcome-${w}.png` });
    const chips = await p.locator(".composer .chips .chip, .onb-q .chip").allInnerTexts();
    console.log(w, "welcome chips:", chips.join(" | "), "| placeholder:", await p.getAttribute("#onb-input", "placeholder").catch(() => "-"));
    // walk through, if offered; else the first answer at each step
    const walk = p.locator(".chip", { hasText: "Walk me through it" });
    if (await walk.count()) { await walk.first().click(); await p.waitForTimeout(500); }
    for (let i = 0; i < 12 && await p.locator("[data-onboarding]").count(); i++) {
      const step = await p.getAttribute("[data-onboarding]", "data-onboarding");
      await p.screenshot({ path: `${OUT}/demo-onb-${step}-${w}.png` });
      const labels = await p.locator(".onb-q .chip, .composer .chips .chip").allInnerTexts();
      if (!labels.length) break;
      const want = labels.find((l) => /use the demo cvs|go to my feed/i.test(l)) || labels.find((l) => !/use the demo profile/i.test(l)) || labels[0];
      console.log("  ", step, "->", want, "| options:", labels.join(" | "));
      await p.locator(".onb-q .chip, .composer .chips .chip").filter({ hasText: want }).first().click();
      await p.waitForTimeout(300);
      if (await p.locator(".onb .typing").count()) await p.screenshot({ path: `${OUT}/demo-onb-${step}-waiting-${w}.png` });
      await p.waitForFunction(() => !document.querySelector(".onb .typing"), null, { timeout: 30000 });
      await p.waitForTimeout(300);
    }
    await p.waitForSelector("#ask-input", { timeout: 30000 }).catch(() => {});
    for (const v of ["chat", "today", "forms", "companies", "profile"]) {
      await p.evaluate((r) => { location.hash = `#${r}`; }, v);
      await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}/demo-${v}-${w}.png` });
    }
    console.log(w, "page errors:", errs.slice(0, 2).join("; ") || "none");
    await ctx.close();
  }
  await b.close();
})();
