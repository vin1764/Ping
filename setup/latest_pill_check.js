// The "Latest ↓" / "N new ↓" pill is docked above the composer and never covers message text: the thread scrolled
// up, at 390x844 and 1280x800, light and dark, the pill's box overlaps no message bubble. Screenshots to
// docs/screenshots/final/latest-pill-*.png.   node setup/latest_pill_check.js [url]
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8799/";
let bad = 0;
const ok = (c, what, note = "") => { if (!c) bad++; console.log(`${c ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };
(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hh] of [[390, 844], [1280, 800]]) for (const scheme of ["light", "dark"]) {
    const ctx = await b.newContext({ viewport: { width: w, height: hh }, colorScheme: scheme, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 30000 });
    await p.evaluate(() => { const t = document.querySelector(".thread"); t.scrollTop = Math.max(0, t.scrollHeight / 3); t.dispatchEvent(new Event("scroll")); });
    await p.waitForTimeout(500);
    const r = await p.evaluate(() => {
      const pill = document.querySelector("#jump");
      if (!pill || pill.hidden) return { shown: false };
      const a = pill.getBoundingClientRect();
      // only what you can see of a bubble: the thread clips it at its own edges
      const tr = document.querySelector(".thread").getBoundingClientRect();
      const hits = [...document.querySelectorAll(".thread .msg")].filter((m) => { const r = m.getBoundingClientRect();
        const top = Math.max(r.top, tr.top), bottom = Math.min(r.bottom, tr.bottom);
        return bottom > top && bottom > a.top && top < a.bottom && r.right > a.left && r.left < a.right; }).length;
      const comp = document.querySelector(".composer").getBoundingClientRect();
      return { shown: true, text: pill.textContent, inComposer: a.top >= comp.top - 1 && a.bottom <= comp.bottom + 1, hits };
    });
    ok(r.shown, `${w} ${scheme}: the pill shows when scrolled up`, r.text || "");
    ok(r.shown && r.inComposer && r.hits === 0, `${w} ${scheme}: docked above the composer, over no message`, JSON.stringify(r));
    await p.screenshot({ path: `docs/screenshots/final/latest-pill-${w}-${scheme}.png` });
    await ctx.close();
  }
  await b.close();
  console.log(`\n${bad} problem(s)`); process.exit(bad ? 1 : 0);
})();
