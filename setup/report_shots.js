// Screenshots for the report: the live demo's chat + Today after two Check nows (a "found" bubble, then the thin
// "nothing new" line), and the Help answer.   node setup/report_shots.js [url]
const { chromium } = require("playwright");
const path = require("path");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const OUT = path.join(__dirname, "..", "docs", "screenshots");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input"); await p.waitForTimeout(800);
  for (let i = 0; i < 3; i++) {
    await p.locator("[data-check-now]:visible").first().click();
    await p.waitForFunction(() => !document.querySelector(".msg.run.r-active"), null, { timeout: 20000 });
    await p.waitForTimeout(2500);
  }
  await p.evaluate(() => { const t = document.querySelector("#thread"); t.scrollTop = t.scrollHeight; });
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(OUT, "chat-today-live-1280.png") });
  await p.fill("#ask-input", "how do I get notifications"); await p.press("#ask-input", "Enter");
  await p.waitForFunction(() => [...document.querySelectorAll(".msg.ping .text")].some((t) => /Profile → Notifications/.test(t.textContent)), null, { timeout: 8000 });
  await p.waitForTimeout(500);
  await p.screenshot({ path: path.join(OUT, "help-answer-live-1280.png") });
  const m = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await m.goto(`${BASE}?demo=1#today`); await m.waitForSelector(".today-row"); await m.waitForTimeout(600);
  await m.screenshot({ path: path.join(OUT, "today-live-390.png") });
  await b.close();
})();
