// The demo's sample mails as View demo shows them: the "via email" tag and the form / test / join link on the
// message, Today, and the Ask Ping mail answer.   node setup/mail_demo_shots.js [url]
const { chromium } = require("playwright");
const path = require("path");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const OUT = path.join(__dirname, "..", "docs", "screenshots");
let bad = 0;
const check = (ok, what) => { if (!ok) bad++; console.log(`${ok ? "ok  " : "FAIL"} ${what}`); };
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input"); await p.waitForTimeout(900);
  const tags = await p.locator(".msg .pill.via").allInnerTexts();
  check(tags.filter((t) => t === "via email").length === 4, `4 messages tagged "via email" in the chat (${tags.length} tags)`);
  const links = await p.locator(".msg .mail-link a").allInnerTexts();
  check(links.includes("Open form ↗") && links.includes("Open test ↗") && links.includes("Join ↗"), `links on the messages: ${links.join(", ")}`);
  await p.locator(".msg .pill.via").first().scrollIntoViewIfNeeded();
  await p.evaluate(() => { const t = document.querySelector("#thread"); t.scrollTop = t.scrollHeight; });
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(OUT, "mail-via-email-1280.png") });
  await p.fill("#ask-input", "what's due from mail"); await p.press("#ask-input", "Enter");
  await p.waitForFunction(() => [...document.querySelectorAll(".msg.ping .text")].some((t) => /Due from your mail/.test(t.textContent)), null, { timeout: 15000 })
    .then(() => check(true, "Ask Ping: what's due from mail")).catch(() => check(false, "Ask Ping: what's due from mail"));
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(OUT, "mail-ask-ping-1280.png") });
  await p.goto(`${BASE}?demo=1#feed`); await p.waitForTimeout(900);
  check(await p.locator(".item .pill.via").count() >= 3, "the Feed tags them too");
  check(!errs.length, `no page errors${errs.length ? `: ${errs.join("; ")}` : ""}`);
  console.log(`\n${bad} problem(s)`);
  await b.close();
  process.exit(bad ? 1 : 0);
})();
