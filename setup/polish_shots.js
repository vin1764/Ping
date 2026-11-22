// Before / after screenshots for the visual polish: chat, Today, Forms, Companies and sign-in, at 390x844 and
// 1280x800, light and dark.   node setup/polish_shots.js <before|after> [url]  -> docs/screenshots/polish/<tag>/
const fs = require("fs");
const { chromium } = require("playwright");
const TAG = process.argv[2] || "after";
const BASE = process.argv[3] || "https://vin1764.github.io/ping-dashboard/";
const OUT = `docs/screenshots/polish/${TAG}`;
fs.mkdirSync(OUT, { recursive: true });
(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hh] of [[390, 844], [1280, 800]]) for (const scheme of ["light", "dark"]) {
    const ctx = await b.newContext({ viewport: { width: w, height: hh }, colorScheme: scheme, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    for (const view of ["chat", "today", "forms", "companies"]) {
      await p.goto(`${BASE}?demo=1#${view}`);
      await p.waitForSelector(view === "chat" ? ".msg.item" : view === "forms" ? "#forms-list" : view === "companies" ? "#company-search, .company" : ".today, .today-row, #today", { timeout: 30000 }).catch(() => {});
      await p.waitForTimeout(700);
      await p.screenshot({ path: `${OUT}/${view}-${w}-${scheme}.png` });
    }
    await p.goto(BASE); await p.waitForSelector("#login-msg, form", { timeout: 30000 }).catch(() => {}); await p.waitForTimeout(500);
    await p.screenshot({ path: `${OUT}/signin-${w}-${scheme}.png` });
    await ctx.close();
  }
  await b.close();
  console.log(`wrote ${fs.readdirSync(OUT).length} screenshots to ${OUT}`);
})();
