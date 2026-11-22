// Every Today row opens something useful: taps each row type on the demo (?demo=1) at 390x844 and 1280x800 and
// checks the sheet: it opens, has cards, every link has a real target (http(s) links open outside the app, never
// a dead "#"), back works on the phone (the arrow and the browser's back), Escape closes it on the desktop, focus
// stays in the sheet while it's open, and "Show in chat" lands on the message. Also the digest's "Show N more" and
// an Ask Ping answer that lists roles. Screenshots to docs/screenshots/final/sheet-*.
//   node setup/today_sheet_check.js [url]        (default: a local build on http://localhost:8799/)
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8799/";
const OUT = "docs/screenshots/final";
let bad = 0;
const ok = (cond, what, note = "") => { if (!cond) bad++; console.log(`${cond ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };

async function sheetFacts(p) {
  return p.evaluate(() => {
    const s = document.querySelector("#sheet");
    const links = [...s.querySelectorAll(".ac-links a")].map((a) => ({ href: a.getAttribute("href"), target: a.target, rel: a.rel, text: a.textContent }));
    return { open: s.open, act: s.classList.contains("act"), title: s.querySelector("#sheet-title")?.textContent || "",
             cards: s.querySelectorAll(".act-card").length, kinds: [...new Set([...s.querySelectorAll(".act-card")].map((c) => c.dataset.kind))],
             links, buttons: [...s.querySelectorAll(".ac-links button")].map((b) => b.textContent),
             disabled: s.querySelectorAll(".ac-links [disabled], .ac-links [aria-disabled=true]").length,
             chips: [...s.querySelectorAll("[data-filter]")].map((c) => c.textContent) };
  });
}

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hgt, tag] of [[390, 844, "390"], [1280, 800, "1280"]]) {
    console.log(`\n${tag}x${hgt}`);
    const ctx = await b.newContext({ viewport: { width: w, height: hgt } });
    const p = await ctx.newPage();
    const errs = []; p.on("pageerror", (e) => errs.push(e.message));
    await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 30000 });
    const phone = w < 900;
    const openToday = async () => { if (phone) { await p.evaluate(() => { location.hash = "#today"; }); await p.waitForSelector("#today-page .today-row"); } };
    await openToday();
    const scope = phone ? "#today-page" : "#today-rail";
    const kinds = await p.$$eval(`${scope} .today-row`, (rows) => rows.map((r, i) => ({ i, cls: r.className, text: r.innerText.replace(/\s+/g, " ").slice(0, 60) })));
    const seen = new Set();
    for (const row of kinds) {
      const k = (row.cls.match(/k-(\w+)/) || [])[1] + (row.cls.includes("group") ? "-group" : "");
      if (seen.has(k) || k.startsWith("more")) continue;
      seen.add(k);
      await openToday();
      await p.locator(`${scope} .today-row`).nth(row.i).click();
      await p.waitForSelector("#sheet[open]", { timeout: 5000 }).catch(() => {});
      await p.waitForTimeout(350);                 // the sheet's slide-in
      const f = await sheetFacts(p);
      const badLinks = f.links.filter((l) => !/^https?:\/\//.test(l.href || "") || l.target !== "_blank" || !/noopener/.test(l.rel));
      ok(f.open && f.act && f.cards > 0, `${k}: "${row.text}" opens the sheet`, `${f.cards} card(s) ${f.kinds.join("/")}; "${f.title}"`);
      ok(!badLinks.length && !f.disabled, `${k}: every link has a target and opens outside the app`,
        `${f.links.map((l) => l.text).join(", ")}${f.buttons.length ? " + " + f.buttons.join(", ") : ""}${badLinks.length ? " BAD " + JSON.stringify(badLinks[0]) : ""}`);
      // focus stays in the sheet
      for (let t = 0; t < 6; t++) await p.keyboard.press("Tab");
      const inside = await p.evaluate(() => document.querySelector("#sheet").contains(document.activeElement));
      ok(inside, `${k}: keyboard focus stays in the sheet`);
      await p.screenshot({ path: `${OUT}/sheet-${k}-${tag}.png` });
      if (phone) {
        await p.click("#sheet .back");
        ok(!(await p.evaluate(() => document.querySelector("#sheet").open)), `${k}: the back arrow closes it`);
        await openToday();
        await p.locator(`${scope} .today-row`).nth(row.i).click();
        await p.waitForSelector("#sheet[open]");
        await p.goBack(); await p.waitForTimeout(300);
        ok(!(await p.evaluate(() => document.querySelector("#sheet").open)) && /#today/.test(p.url()), `${k}: the phone's back closes it and stays on Today`, p.url().split("/").pop());
      } else {
        await p.keyboard.press("Escape"); await p.waitForTimeout(150);
        ok(!(await p.evaluate(() => document.querySelector("#sheet").open)), `${k}: Escape closes it`);
      }
    }
    ok(seen.size >= 3, `row types tried: ${[...seen].join(", ")}`);
    // "Show in chat" from a sheet lands on the message
    await openToday();
    const dl = p.locator(`${scope} .today-row.k-deadline`).first();
    if (await dl.count()) {
      await dl.click(); await p.waitForSelector("#sheet[open]");
      const show = p.locator("#sheet .ac-links button", { hasText: "Show in chat" }).first();
      if (await show.count()) {
        await show.click(); await p.waitForTimeout(700);
        const hl = await p.evaluate(() => !!document.querySelector(".msg.hl") && !document.querySelector("#sheet").open);
        ok(hl, "Show in chat: the sheet closes and the message flashes");
      }
    }
    // the digest's "Show N more"
    await p.evaluate(() => { location.hash = "#chat"; }); await p.waitForTimeout(300);
    const more = p.locator(".show-more").first();
    if (await more.count()) {
      await more.scrollIntoViewIfNeeded(); await more.click(); await p.waitForSelector("#sheet[open]"); await p.waitForTimeout(350);
      const f = await sheetFacts(p);
      ok(f.cards > 3 && f.chips.length === 3, `"Show N more" in a digest opens the sheet with filters`, `${f.cards} cards; "${f.title}"`);
      await p.click("[data-filter=notapplied]");
      const na = await p.evaluate(() => [...document.querySelectorAll("#sheet .act-card .pill.applied")].length);
      ok(na === 0, "the Not applied filter leaves no applied role");
      await p.screenshot({ path: `${OUT}/sheet-digest-${tag}.png` });
      if (phone) await p.click("#sheet .back"); else await p.keyboard.press("Escape");
    } else ok(false, "a digest with \"Show N more\"");
    // an Ask Ping answer that lists roles
    await p.fill("#ask-input", "what's due tonight that's relevant to me"); await p.press("#ask-input", "Enter");
    await p.waitForTimeout(1500);
    const btn = p.locator(".msg.ping .open-roles").last();
    if (await btn.count()) {
      await btn.click(); await p.waitForSelector("#sheet[open]"); await p.waitForTimeout(350);
      const f = await sheetFacts(p);
      ok(f.cards >= 2, "an Ask Ping answer that lists roles opens them in the sheet", `"${f.title}"`);
      await p.screenshot({ path: `${OUT}/sheet-askping-${tag}.png` });
    } else ok(false, "an Ask Ping answer with \"Open these N roles\"");
    ok(!errs.length, "no page errors", errs.slice(0, 2).join("; "));
    await ctx.close();
  }
  await b.close();
  console.log(`\n${bad} problem(s)`);
  process.exit(bad ? 1 : 0);
})();
