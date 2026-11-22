// Performance numbers for docs/ONE_PAGER_FACTS.md, on the live site (or a given URL), with a phone's CPU (4x slower)
// and a 4G network (9 Mbps down, 1.5 Mbps up, 170 ms round trip; DevTools' "4G" preset) from a cold cache:
//   - first load: the landing page's sign-in screen, and the demo's chat with its messages
//   - Companies: every role listed ("All"), the time to draw it, and frames while scrolling it
//   - a message arriving (the demo's Check now): layout shift of what you were reading
//   - a FACT question answered in the page
//   node setup/perf_check.js [url]
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const out = {};

async function fresh(b) {
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const p = await ctx.newPage();
  const cdp = await ctx.newCDPSession(p);
  await cdp.send("Network.enable");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 170,
    downloadThroughput: 9 * 1024 * 1024 / 8, uploadThroughput: 1.5 * 1024 * 1024 / 8 });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  return { ctx, p };
}

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  // 1. the landing page (the sign-in form)
  let { ctx, p } = await fresh(b);
  let t = Date.now();
  await p.goto(BASE); await p.waitForSelector("form.login button[type=submit]", { timeout: 30000 });
  out["landing page usable (the sign-in form)"] = `${Date.now() - t} ms`;
  await ctx.close();
  // 2. the demo with its messages
  ({ ctx, p } = await fresh(b));
  t = Date.now();
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 60000 });
  out["demo chat with its messages"] = `${Date.now() - t} ms`;
  // 3. a FACT question in the page
  await p.waitForSelector("#ask-input");
  await p.fill("#ask-input", "what's due tonight?"); t = Date.now(); await p.press("#ask-input", "Enter");
  await p.waitForFunction(() => document.querySelector(".msg.ping:not(.typing):last-of-type")?.dataset.answeredBy === "page" ||
    [...document.querySelectorAll(".msg.ping[data-answered-by]")].length > 0, null, { timeout: 10000 });
  out["FACT answer on screen (phone CPU)"] = `${Date.now() - t} ms (${await p.locator(".msg.ping[data-answered-by]").last().getAttribute("data-ms")} ms of work in the page)`;
  // 4. layout shift while a message arrives (the demo's Check now brings one); you're reading higher up
  await p.evaluate(() => { window.__cls = 0; new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
    .observe({ type: "layout-shift", buffered: false }); const t = document.querySelector("#thread"); t.scrollTop = t.scrollHeight / 2; });
  await p.locator("[data-check-now]:visible").first().click();
  await p.waitForFunction(() => !document.querySelector(".msg.run.r-active"), null, { timeout: 30000 }); await p.waitForTimeout(1500);
  out["layout shift while a message arrives"] = (await p.evaluate(() => window.__cls)).toFixed(3);
  // 5. Companies, every role
  await p.evaluate(() => { location.hash = "#companies"; }); await p.waitForSelector("[data-role]");
  const all = p.locator(".chips .chip").filter({ hasText: /^All/ });
  t = Date.now();
  if (await all.count()) await all.first().click();
  await p.waitForTimeout(100);
  out[`Companies "All", first screenful drawn (${await p.locator("[data-role]").count()} rows, then "Show more")`] = `${Date.now() - t} ms`;
  t = Date.now();
  for (let i = 0; i < 5; i++) {                    // every role on the page
    const more = p.locator("#roles button", { hasText: /^Show \d+ more$/ });
    if (!(await more.count())) break;
    await more.first().click(); await p.waitForTimeout(50);
  }
  out[`Companies, every role drawn (${await p.locator("[data-role]").count()} rows)`] = `${Date.now() - t} ms`;
  const fps = await p.evaluate(async () => {
    let frames = 0, long = 0, last = performance.now(); const start = last;
    const el = document.scrollingElement; const sc = document.querySelector("main") || el;
    await new Promise((res) => { const step = () => { const now = performance.now(); frames++; if (now - last > 50) long++; last = now;
      window.scrollBy(0, 40); sc.scrollTop += 40; if (now - start < 3000) requestAnimationFrame(step); else res(); }; requestAnimationFrame(step); });
    return { fps: Math.round(frames / 3), slowFrames: long };
  });
  out["Companies scrolling (phone CPU)"] = `${fps.fps} frames/s, ${fps.slowFrames} frames over 50 ms in 3 s`;
  await ctx.close();
  await b.close();
  for (const [k, v] of Object.entries(out)) console.log(`${k}: ${v}`);
})();
