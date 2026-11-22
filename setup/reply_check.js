// Reply to a message, in the page: phone 390x844 (swipe right, long-press) and PC 1280x800 (hover arrow, right-click,
// Esc), light and dark; the five reply cases of evals/ask_ping/multiturn.json ("replies") answered from the quoted
// message; quotes inside the bubbles; tapping a quote flashes the original. Model off: the static demo (?demo=1);
// model on: an anonymous demo session (?anon-demo=1), where the ask-ping function is reachable.
//   node setup/reply_check.js [url] [off|on]      screenshots: docs/screenshots/final/reply-*.png
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8799/";
const MODE = process.argv[3] || "off";
let bad = 0;
const ok = (c, what, note = "") => { if (!c) bad++; console.log(`${c ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };

async function open(b, w, hh, scheme, touch) {
  const ctx = await b.newContext({ viewport: { width: w, height: hh }, colorScheme: scheme, hasTouch: touch, isMobile: touch, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  if (MODE === "on") {
    await p.goto(`${BASE}?anon-demo=1`); await p.click("#view-demo");
    await p.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
    if (await p.locator(".chips .chip:has-text('Use the demo profile')").count()) await p.click(".chips .chip:has-text('Use the demo profile')");
  } else await p.goto(`${BASE}?demo=1#chat`);
  await p.waitForSelector(".msg.item[data-reply]", { timeout: 60000 });
  return { ctx, p, errs };
}
// a bubble by what it is: "digest" (an application digest with several roles), "test" (a test alert with a room),
// "form" (a bubble with a form checkbox), "company" (any single-company message)
async function pick(p, what) {
  if (what === "digest") {           // an application digest, else any message listing several roles (a new-roles listing)
    for (const sel of ['.msg[data-reply][data-key*=":digest:application:"]', '.msg[data-reply][data-key*=":listing:"]:has(.li + .li)']) {
      const all = p.locator(sel);
      for (let i = 0; i < 6 && !(await all.count()) && await p.locator(".earlier").count(); i++) await p.click(".earlier");
      if (await all.count()) return all.last();
    }
    return null;
  }
  const sel = { digest: '.msg[data-reply][data-key*=":digest:application:"]', form: '.msg[data-reply]:has(input.tick-box), .msg[data-reply][data-key*=":digest:form:"]',
                test: '.msg.item[data-reply].k-test', company: '.msg.item[data-reply][data-key*=":notice:"]' }[what];
  const all = p.locator(sel);
  for (let i = 0; i < 6 && !(await all.count()) && await p.locator(".earlier").count(); i++) await p.click(".earlier");
  return (await all.count()) ? all.last() : null;
}
async function replyVia(p, el, how) {
  if (!el) return false;
  await el.scrollIntoViewIfNeeded();
  const box = await el.boundingBox();
  if (how === "hover") { await el.hover(); await el.locator(".reply-btn").click(); }
  else if (how === "right-click") await el.click({ button: "right", position: { x: 20, y: 12 } });
  else if (how === "swipe" || how === "hold") {
    await el.evaluate((m, how) => {
      m.scrollIntoView({ block: "center" });
      const r = m.getBoundingClientRect(), x = r.left + 30, y = r.top + 16;
      const t = m.querySelector(".text") || m;
      const ev = (type, cx) => t.dispatchEvent(new PointerEvent(type, { bubbles: true, pointerType: "touch", clientX: cx, clientY: y, isPrimary: true }));
      ev("pointerdown", x);
      if (how === "swipe") { for (let d = 10; d <= 70; d += 10) ev("pointermove", x + d); ev("pointerup", x + 70); return null; }
      return new Promise((res) => setTimeout(() => { ev("pointerup", x); res(); }, 650));
    }, how);
  }
  await p.waitForSelector(".reply-preview:not([hidden])", { timeout: 3000 }).catch(() => {});
  return await p.locator(".reply-preview:not([hidden])").count() === 1;
}
async function send(p, q) {
  const n = await p.locator(".msg.ping:not(.typing):not(.r-active)").count();
  await p.fill("#ask-input", q); await p.press("#ask-input", "Enter");
  await p.waitForFunction((n) => document.querySelectorAll(".msg.ping:not(.typing):not(.r-active)").length > n, n, { timeout: 60000 });
  await p.waitForSelector(".msg.ping.r-active", { state: "detached", timeout: 60000 }).catch(() => {});
  const last = p.locator(".msg.ping[data-answered-by]").last();
  return { text: (await last.locator(".text").innerText()).replace(/\s+/g, " "), quoted: await last.locator(".quote").count(),
           by: await last.getAttribute("data-answered-by"), mineQuoted: await p.locator(".msg.me").last().locator(".quote").count() };
}

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hh, touch] of [[390, 844, true], [1280, 800, false]]) for (const scheme of ["light", "dark"]) {
    console.log(`\n${w} ${scheme} (model ${MODE})`);
    const { ctx, p, errs } = await open(b, w, hh, scheme, touch);
    const how = touch ? "swipe" : "hover";
    // 1. digest: which of these haven't I applied to?
    let el = await pick(p, "digest");
    ok(el && await replyVia(p, el, how), `${how} on a digest opens the reply preview`);
    if (scheme === "light") await p.screenshot({ path: `docs/screenshots/final/reply-preview-${w}.png` });
    let a = await send(p, "which of these haven't I applied to?");
    ok(/not applied yet|applied to all/.test(a.text) && a.quoted && a.mineQuoted, "digest: which haven't I applied to → only that message's roles, quoted both ways", a.text.slice(0, 100));
    // 2. which cv for the second one?
    el = await pick(p, "digest");
    ok(el && await replyVia(p, el, touch ? "hold" : "right-click"), `${touch ? "long-press" : "right-click"} opens the reply preview`);
    a = await send(p, "which cv for the second one?");
    ok(/apply with|none of your CVs|lists \d role/.test(a.text), `${touch ? "long-press" : "right-click"} → which cv for the second one?`, a.text.slice(0, 100));
    // 3. tap the quote in my last bubble: the original flashes
    await p.locator(".msg.me .quote").last().click();
    ok(await p.waitForSelector(".msg.flash", { timeout: 3000 }).then(() => true).catch(() => false), "tapping a quote flashes the original");
    if (scheme === "light") await p.screenshot({ path: `docs/screenshots/final/reply-thread-${w}.png` });
    if (scheme === "dark") await p.screenshot({ path: `docs/screenshots/final/reply-thread-${w}-dark.png` });
    // 4. Esc cancels (PC) / ✕ cancels
    el = await pick(p, "company");
    await replyVia(p, el, how);
    if (!touch) { await p.focus("#ask-input"); await p.keyboard.press("Escape"); } else await p.click(".reply-preview .rp-x");
    ok(await p.locator(".reply-preview:not([hidden])").count() === 0, `${touch ? "✕" : "Esc"} cancels the reply`);
    // 5. a test alert: where is it?
    el = await pick(p, "test");
    await replyVia(p, el, how);
    a = await send(p, "where is it?");
    ok(a.quoted && a.text.length > 5, "test alert: where is it? → that test's room / slot", a.text.slice(0, 100));
    // 6. a form line: done → ticked
    el = await pick(p, "form");
    if (el) {
      await replyVia(p, el, how);
      a = await send(p, "done");
      ok(/Ticked|Already ticked/.test(a.text), "form line: done → ticked, one line", a.text.slice(0, 90));
    } else ok(true, "form line: no form bubble in this view (skipped)");
    // 7. check again on a company message → a re-check of that company
    el = await pick(p, "company");
    await replyVia(p, el, how);
    a = await send(p, "check again");
    ok(a.by === "recheck" && /\(\d\d:\d\d\)|couldn't reach/.test(a.text), "check again → a re-check of that message's company", a.text.slice(0, 90));
    ok(!errs.length, "no page errors", errs.slice(0, 2).join("; "));
    await ctx.close();
  }
  await b.close();
  console.log(`\n${bad} problem(s)`); process.exit(bad ? 1 : 0);
})();
