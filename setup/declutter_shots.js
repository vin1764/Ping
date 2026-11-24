// The declutter pass's before / after screenshots: Chat, Today, Forms, Companies and Profile at 390 px (iPhone), on the
// demo (?demo=1), plus checks: no collapsed card taller than 3 lines of text plus one button row, no notice
// numbers or "posted N times" on a collapsed card.
//   node setup/declutter_shots.js <before|after> [url]
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const TAG = process.argv[2] || "after";
const BASE = process.argv[3] || "http://localhost:8799/";
const OUT = path.join(__dirname, "..", "docs", "screenshots", "declutter");
fs.mkdirSync(OUT, { recursive: true });
const PAGES = [["chat", "#chat"], ["today", "#today"], ["forms", "#forms"], ["companies", "#companies"], ["profile", "#profile"], ["updates", "#feed"]];

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 40000 });
  await p.waitForTimeout(1200);
  let bad = 0;
  for (const [name, hash] of PAGES) {
    await p.evaluate((h) => { location.hash = h; }, hash);
    await p.waitForTimeout(900);
    if (name === "chat") await p.evaluate(() => { const t = document.querySelector("#thread, .thread"); if (t) t.scrollTop = t.scrollHeight; });
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(OUT, `${TAG}-${name}.png`) });
    if (TAG !== "after") continue;
    // collapsed cards: lines of text (not counting the one button row) and leftovers
    const r = await p.evaluate(() => {
      const out = [];
      for (const c of document.querySelectorAll(".card-c:not(.open)")) {
        const b = c.getBoundingClientRect(); if (!b.height) continue;
        const text = c.querySelector(".cc-text"); const lh = parseFloat(getComputedStyle(text || c).lineHeight) || 20;
        const lines = text ? Math.round(text.getBoundingClientRect().height / lh) : 0;
        const t = c.innerText;
        out.push({ lines, posted: /posted \d+ times|notice \d{3,}/i.test(t), raw: /\[URGENT\]|\bCDC \|/i.test(t), t: t.replace(/\s+/g, " ").slice(0, 70) });
      }
      return out;
    });
    // Today's rows and the Companies rows follow the same rule (3 lines of text)
    const rows = await p.evaluate(() => [...document.querySelectorAll(".today-row .t-body, .role-row")].map((e) => {
      const lh = 22, b = e.getBoundingClientRect(); const pad = e.matches(".role-row") ? 24 : 0;
      return { lines: Math.round((b.height - pad) / lh), posted: /posted \d|notice \d{3,}|per a notice/i.test(e.innerText), raw: /\[URGENT\]/i.test(e.innerText), t: e.innerText.replace(/\s+/g, " ").slice(0, 70) };
    }));
    r.push(...rows);
    for (const c of r) if (c.lines > 3 || c.posted || c.raw) { bad++; console.log(`FAIL ${name}: ${c.lines} lines${c.posted ? ", notice ids" : ""}${c.raw ? ", raw title" : ""}: ${c.t}`); }
    console.log(`${name}: ${r.length} collapsed cards / rows, tallest ${Math.max(0, ...r.map((c) => c.lines))} lines`);
  }
  if (TAG === "after") {
    // a card tapped open (the detail lives there now), and Today's sheet
    await p.evaluate(() => { location.hash = "#forms"; }); await p.waitForTimeout(700);
    await p.click(".card-c.form-row .cc-more"); await p.waitForTimeout(300);
    await p.evaluate(() => document.querySelector(".card-c.form-row.open")?.scrollIntoView({ block: "start" }));
    await p.screenshot({ path: path.join(OUT, "after-forms-card-open.png") });
    await p.evaluate(() => { location.hash = "#today"; }); await p.waitForTimeout(700);
    await p.click("#today-page .today-row.k-deadline"); await p.waitForTimeout(900);
    const s = await p.evaluate(() => [...document.querySelectorAll("#sheet .card-c:not(.open)")].map((c) => {
      const t = c.querySelector(".cc-text"); return Math.round(t.getBoundingClientRect().height / 22); }));
    console.log(`today sheet: ${s.length} cards, tallest ${Math.max(0, ...s)} lines`);
    if (s.some((n) => n > 3)) bad++;
    await p.screenshot({ path: path.join(OUT, "after-today-sheet.png") });
  }
  console.log(errs.length ? `page errors: ${errs.join(" | ")}` : "no page errors");
  await b.close();
  process.exit(bad || errs.length ? 1 : 0);
})();
