// The install message on Chromium, with and without the browser's install event (beforeinstallprompt):
//   without it: the steps for this device, no dead button; "Not now" hides it for 7 days, then it comes back;
//   with it:    an "Install" button that opens the browser's dialog; dismissed -> the steps;
//   Profile > Install Ping: the steps, always; the Help chip answers "how to install" for this device.
//   node setup/install_check.js [url]   (default: a local build on http://localhost:8765/; screenshots to docs/screenshots/)
const { chromium } = require("playwright");
const path = require("path");
const BASE = process.argv[2] || "http://localhost:8765/";
const OUT = path.join(__dirname, "..", "docs", "screenshots");
const WIN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";
let bad = 0;
const check = (ok, what) => { if (!ok) bad++; console.log(`${ok ? "ok  " : "FAIL"} ${what}`); };

async function open(b, { visits = 2, install = undefined, event = false } = {}) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 800 }, userAgent: WIN });
  await ctx.addInitScript(({ visits, install, event }) => {
    try {
      if (!sessionStorage.getItem("seeded")) {
        localStorage.setItem("ping-visits", JSON.stringify(visits - 1));        // this load makes it `visits`
        if (install !== undefined) localStorage.setItem("ping-install", JSON.stringify(install));
        sessionStorage.setItem("seeded", "1");
      }
    } catch { /* */ }
    window.__prompted = 0;
    if (event) {
      // the browser's install event, as Chrome fires it on an installable page (prompt() opens its dialog)
      window.addEventListener("load", () => setTimeout(() => {
        const e = new Event("beforeinstallprompt", { cancelable: true });
        e.prompt = () => { window.__prompted++; return Promise.resolve(); };
        e.userChoice = Promise.resolve({ outcome: window.__choice || "dismissed", platform: "web" });
        window.dispatchEvent(e);
      }, 300));
    }
  }, { visits, install, event });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input", { timeout: 30000 });
  await p.waitForTimeout(900);
  return { ctx, p, errs };
}

(async () => {
  const b = await chromium.launch();
  // 1. no install event (e.g. the engagement check hasn't passed yet): the steps for Windows, no dead button
  let { ctx, p, errs } = await open(b);
  let msg = p.locator(".msg.install");
  check(await msg.count() === 1, "without the event: the install message shows");
  const text = await msg.innerText().catch(() => "");
  check(/⋮ menu → "Install Ping…"/.test(text) && /address bar/.test(text), `  with the Windows steps: "${text.split("\n").find((l) => l.includes("⋮"))?.slice(0, 90)}…"`);
  check(await msg.locator('[data-install="prompt"]').count() === 0, "  and no Install button (it couldn't open anything)");
  await msg.scrollIntoViewIfNeeded();
  await p.screenshot({ path: path.join(OUT, "install-steps-windows-1280.png") });
  await msg.locator('[data-install="later"]').click();
  check(await p.locator(".msg.install").count() === 0, "  Not now hides it");
  const snooze = await p.evaluate(() => JSON.parse(localStorage.getItem("ping-install")));
  const days = (Date.parse(snooze?.snoozeUntil) - Date.now()) / 86400000;
  check(days > 6.9 && days <= 7, `  for 7 days (until ${snooze?.snoozeUntil})`);
  await p.reload(); await p.waitForSelector("#ask-input"); await p.waitForTimeout(500);
  check(await p.locator(".msg.install").count() === 0, "  still hidden after a reload");
  await p.evaluate(() => localStorage.setItem("ping-install", JSON.stringify({ snoozeUntil: new Date(Date.now() - 1000).toISOString() })));
  await p.reload(); await p.waitForSelector("#ask-input"); await p.waitForTimeout(500);
  check(await p.locator(".msg.install").count() === 1, "  and back once the 7 days are over");
  // Profile > Install Ping: always findable
  await p.goto(`${BASE}?demo=1#profile`); await p.waitForSelector("#pc-install", { timeout: 15000 });
  const card = await p.locator("#pc-install").innerText();
  check(/Install Ping/.test(card) && /⋮ menu/.test(card), "Profile has an Install Ping card with the steps");
  await p.locator("#pc-install").scrollIntoViewIfNeeded();
  await p.screenshot({ path: path.join(OUT, "install-profile-card-1280.png") });
  // the Help chip and "how to install" answer for this device
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input");
  await p.getByRole("button", { name: "Help", exact: true }).click();
  await p.waitForFunction(() => [...document.querySelectorAll(".msg.ping .text")].some((t) => /how do I install Ping/.test(t.textContent)), null, { timeout: 8000 });
  check(true, "the Help chip answers with the help overview");
  await p.fill("#ask-input", "how to install"); await p.press("#ask-input", "Enter");
  await p.waitForFunction(() => [...document.querySelectorAll(".msg.ping .text")].some((t) => /Install Ping…/.test(t.textContent)), null, { timeout: 8000 });
  check(true, '"how to install" answers with the Windows steps');
  check(!errs.length, `no page errors${errs.length ? `: ${errs.join("; ")}` : ""}`);
  await ctx.close();

  // 2. with the install event: a real Install button; it opens the dialog; dismissed -> the steps
  ({ ctx, p, errs } = await open(b, { event: true }));
  await p.waitForSelector('.msg.install [data-install="prompt"]', { timeout: 5000 }).catch(() => {});
  msg = p.locator(".msg.install");
  check(await msg.locator('[data-install="prompt"]').count() === 1, "with the event: the message has an Install button");
  await msg.scrollIntoViewIfNeeded();
  await p.screenshot({ path: path.join(OUT, "install-button-1280.png") });
  await msg.locator('[data-install="prompt"]').click(); await p.waitForTimeout(300);
  check(await p.evaluate(() => window.__prompted) === 1, "  Install opens the browser's install dialog (prompt() called)");
  const after = await msg.innerText().catch(() => "");
  check(/⋮ menu/.test(after) && await msg.locator('[data-install="prompt"]').count() === 0, "  dismissed in the dialog: the steps replace the button");
  check(!errs.length, `no page errors${errs.length ? `: ${errs.join("; ")}` : ""}`);
  await ctx.close();

  // 3. accepted in the dialog: never offered again
  ({ ctx, p, errs } = await open(b, { event: true }));
  await p.evaluate(() => { window.__choice = "accepted"; });
  await p.waitForSelector('.msg.install [data-install="prompt"]', { timeout: 5000 }).catch(() => {});
  // userChoice was made at dispatch time with "dismissed"; fire a fresh event that resolves "accepted"
  await p.evaluate(() => { const e = new Event("beforeinstallprompt", { cancelable: true });
    e.prompt = () => { window.__prompted++; }; e.userChoice = Promise.resolve({ outcome: "accepted" }); window.dispatchEvent(e); });
  await p.locator('.msg.install [data-install="prompt"]').click(); await p.waitForTimeout(300);
  check(await p.locator(".msg.install").count() === 0 && await p.evaluate(() => JSON.parse(localStorage.getItem("ping-install"))) === "installed",
        "accepted: the message goes, and it isn't offered again");
  await ctx.close();
  console.log(`\n${bad} problem(s)`);
  await b.close();
  process.exit(bad ? 1 : 0);
})();
