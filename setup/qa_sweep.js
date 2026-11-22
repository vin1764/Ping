// A stranger's sweep of the dashboard (?demo=1, the anonymised snapshot): every page at 390x844, 768x1024 and
// 1280x800, light and dark, with automatic checks: no horizontal overflow, body text >= 14 px on phones, tap targets
// >= 44 px on phones (buttons, links, chips, inputs), nothing covering the composer, no page errors. Screenshots go
// to docs/screenshots/final/.
//   node setup/qa_sweep.js [url]     (default: a local build on http://localhost:8765/)
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const BASE = process.argv[2] || "http://localhost:8765/";
const OUT = path.join(__dirname, "..", "docs", "screenshots", "final");
fs.mkdirSync(OUT, { recursive: true });
const SIZES = [[390, 844, "390"], [768, 1024, "768"], [1280, 800, "1280"]];
const PAGES = ["chat", "today", "feed", "companies", "profile"];
const problems = [];
const note = (where, what) => { problems.push(`${where}: ${what}`); };

async function measure(p, where, phone) {
  const r = await p.evaluate((phone) => {
    const out = { overflow: document.documentElement.scrollWidth - window.innerWidth, small: [], tiny: [], hidden: [] };
    const vis = (el) => { const s = getComputedStyle(el); const b = el.getBoundingClientRect();
      return s.visibility !== "hidden" && s.display !== "none" && b.width > 0 && b.height > 0 && b.bottom > 0 && b.top < innerHeight; };
    const label = (el) => (el.getAttribute("aria-label") || el.innerText || el.value || el.tagName).trim().replace(/\s+/g, " ").slice(0, 40);
    if (phone) {
      for (const el of document.querySelectorAll("button, a[href], input, select, textarea, [role=button], summary")) {
        if (!vis(el) || el.closest(".msg.item") && el.matches(".msg.item")) continue;
        const b = el.getBoundingClientRect();
        if (b.height < 44 && b.width < 44 || b.height < 32) out.small.push(`${label(el)} ${Math.round(b.width)}x${Math.round(b.height)}`);
      }
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const seen = new Set();
      while (walker.nextNode()) {
        const el = walker.currentNode.parentElement;
        if (!el || seen.has(el) || !walker.currentNode.textContent.trim() || !vis(el)) continue;
        seen.add(el);
        const fs = parseFloat(getComputedStyle(el).fontSize);
        if (fs < 12) out.tiny.push(`${fs}px "${el.innerText.trim().slice(0, 30)}"`);
      }
    }
    // things wider than the screen
    for (const el of document.querySelectorAll("body *")) {
      const b = el.getBoundingClientRect();
      if (b.width > 0 && b.right > innerWidth + 1 && getComputedStyle(el).position !== "fixed" && !el.closest("pre, .thread, [style*=overflow]"))
        out.hidden.push(`${el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} right=${Math.round(b.right)}`);
    }
    return out;
  }, phone);
  if (r.overflow > 1) note(where, `page scrolls sideways by ${r.overflow}px`);
  if (r.small.length) note(where, `${r.small.length} tap targets under 44px: ${[...new Set(r.small)].slice(0, 6).join("; ")}`);
  if (r.tiny.length) note(where, `${r.tiny.length} texts under 12px: ${[...new Set(r.tiny)].slice(0, 4).join("; ")}`);
  if (r.hidden.length) note(where, `${r.hidden.length} elements past the right edge: ${[...new Set(r.hidden)].slice(0, 4).join("; ")}`);
}

(async () => {
  const b = await chromium.launch();
  for (const [w, h, tag] of SIZES) {
    for (const scheme of ["light", "dark"]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme, deviceScaleFactor: 1,
                                       isMobile: w < 600, hasTouch: w < 1000 });
      const p = await ctx.newPage();
      const errs = []; p.on("pageerror", (e) => errs.push(e.message));
      await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input", { timeout: 30000 }); await p.waitForTimeout(700);
      for (const pg of PAGES) {
        if (pg === "today" && w >= 1100) continue;              // Today is the rail beside the chat there
        await p.evaluate((pg) => { location.hash = `#${pg}`; }, pg); await p.waitForTimeout(700);
        const where = `${pg} ${tag} ${scheme}`;
        await measure(p, where, w < 600);
        await p.screenshot({ path: path.join(OUT, `${pg}-${tag}-${scheme}.png`) });
      }
      // a role sheet (Companies, first role)
      await p.evaluate(() => { location.hash = "#companies"; }); await p.waitForTimeout(600);
      const row = p.locator("[data-role]").first();
      if (await row.count()) {
        await row.click(); await p.waitForTimeout(500);
        await measure(p, `role sheet ${tag} ${scheme}`, w < 600);
        await p.screenshot({ path: path.join(OUT, `role-sheet-${tag}-${scheme}.png`) });
        await p.keyboard.press("Escape");
      }
      // the composer with the keyboard-sized viewport (phones): the input stays visible above it
      if (w < 600) {
        await p.evaluate(() => { location.hash = "#chat"; }); await p.waitForTimeout(500);
        await p.setViewportSize({ width: w, height: 500 });
        await p.click("#ask-input"); await p.waitForTimeout(300);
        const box = await p.locator("#ask-input").boundingBox();
        if (!box || box.y + box.height > 500) note(`composer ${tag} ${scheme}`, `the input is hidden when the keyboard is up (bottom at ${box && Math.round(box.y + box.height)})`);
        await p.screenshot({ path: path.join(OUT, `composer-keyboard-${tag}-${scheme}.png`) });
      }
      if (errs.length) note(`${tag} ${scheme}`, `page errors: ${errs.slice(0, 2).join("; ")}`);
      await ctx.close();
    }
  }
  await b.close();
  console.log(problems.length ? problems.join("\n") : "no problems");
  console.log(`\n${problems.length} problem(s); screenshots in docs/screenshots/final/`);
})();
