// The installable app and push, checked in a headless browser (docs/PUSH.md): the manifest and its icons, the
// service worker, opening offline, and a push handed to the service worker (Chrome DevTools' own push delivery):
// the notification it shows, and the link it opens. A real subscription needs a push service (FCM/APNs) that a
// headless Chromium can't reach; Admin > push-check covers the encrypted request and the VAPID token, and
// docs/PUSH.md has the steps on a real phone.
//   node setup/pwa_check.js [url]          (default: the live dashboard; screenshots into docs/screenshots/)
const { chromium } = require("playwright");
const path = require("path");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const OUT = path.join(__dirname, "..", "docs", "screenshots");
let bad = 0;
const check = (ok, what) => { if (!ok) bad++; console.log(`${ok ? "ok  " : "FAIL"} ${what}`); };
const pngSize = (buf) => [buf.readUInt32BE(16), buf.readUInt32BE(20)];

(async () => {
  const b = await chromium.launch({ channel: "chromium" });   // the full Chromium, headless: notifications work
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await ctx.grantPermissions(["notifications"], { origin: new URL(BASE).origin });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector("#ask-input", { timeout: 30000 });

  // 1. the manifest: what an install needs
  const man = await p.evaluate(async () => {
    const href = document.querySelector('link[rel="manifest"]')?.href;
    return href ? { href, json: await (await fetch(href)).json() } : null;
  });
  check(!!man, `manifest linked: ${man?.href}`);
  const m = man?.json || {};
  const scope = new URL(m.scope || "", man?.href).pathname, start = new URL(m.start_url || "", man?.href).pathname;
  check(m.name && m.short_name && m.display === "standalone" && /^#[0-9a-f]{6}$/i.test(m.theme_color || "") && m.background_color,
        `name "${m.name}", short_name "${m.short_name}", display ${m.display}, theme ${m.theme_color}`);
  check(scope === "/ping-dashboard/" && start.startsWith(scope), `scope ${scope}, start_url ${m.start_url}`);
  const icons = await p.evaluate(async (list) => Promise.all(list.map(async (i) => {
    const r = await fetch(new URL(i.src, document.querySelector('link[rel="manifest"]').href));
    return { ...i, status: r.status, type: r.headers.get("content-type"), bytes: Array.from(new Uint8Array(await r.arrayBuffer()).slice(0, 24)) };
  })), m.icons || []);
  for (const i of icons) {
    const [w, h] = pngSize(Buffer.from(i.bytes));
    check(i.status === 200 && `${w}x${h}` === i.sizes, `icon ${i.src} ${i.sizes} (${i.purpose}): HTTP ${i.status}, ${w}x${h} ${i.type}`);
  }
  check(icons.some((i) => i.sizes === "192x192") && icons.some((i) => i.sizes === "512x512") && icons.some((i) => i.purpose === "maskable"),
        "192, 512 and a maskable icon");
  check(await p.evaluate(() => !!document.querySelector('link[rel="apple-touch-icon"]') && !!document.querySelector('meta[name="theme-color"]')),
        "iOS: apple-touch-icon and theme-color");

  // 2. the service worker
  const sw = await p.evaluate(async () => { const r = await navigator.serviceWorker.ready; return { scope: r.scope, state: r.active?.state }; });
  check(sw.scope === new URL("./", BASE).href && sw.state === "activated", `service worker ${sw.state}, scope ${sw.scope}`);
  await p.reload(); await p.waitForSelector("#ask-input");
  check(await p.evaluate(() => !!navigator.serviceWorker.controller), "the page is served by the service worker after a reload");
  await ctx.setOffline(true);
  await p.reload(); await p.waitForSelector("#ask-input", { timeout: 15000 }).catch(() => {});
  check(await p.locator(".msg").count() > 10, `offline: the app opens with its thread (${await p.locator(".msg").count()} messages)`);
  await ctx.setOffline(false);
  await p.reload(); await p.waitForSelector("#ask-input");

  // 3. a real subscription: needs a push service the headless browser can't reach (recorded, not failed)
  const sub = await p.evaluate(async () => {
    const k = window.PING_CONFIG?.pushKey;
    if (!k) return { ok: false, err: "no pushKey in config.js" };
    const u = Uint8Array.from(atob((k + "=".repeat((4 - k.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
    try { const s = await (await navigator.serviceWorker.ready).pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: u });
          return { ok: true, endpoint: s.endpoint.split("/").slice(0, 3).join("/") }; }
    catch (e) { return { ok: false, err: `${e.name}: ${e.message}` }; }
  });
  console.log(`note real subscription here: ${sub.ok ? `made (${sub.endpoint})` : `not possible headless (${sub.err})`}`);
  check(await p.evaluate(() => typeof window.PING_CONFIG?.pushKey === "string" && window.PING_CONFIG.pushKey.length === 87), "config.js carries the VAPID public key");

  // 4. a push delivered to the service worker: the notification it shows, and where a tap goes
  const items = await p.evaluate(async () => (await (await fetch("demo-data.json")).json()).items
    .filter((i) => i.category === "test" && i.level !== "hidden").map((i) => i.id));
  const payload = { title: "Test · today 15:00", body: "Groww test at 15:00 · room 304 (in 2 h)",
                    url: `./#m-${encodeURIComponent(items[0])}`, tag: "pwa-check", at: new Date().toISOString() };
  const cdp = await ctx.newCDPSession(p);
  const regs = [];
  cdp.on("ServiceWorker.workerRegistrationUpdated", (e) => regs.push(...e.registrations));
  await cdp.send("ServiceWorker.enable");
  await p.waitForTimeout(500);
  const reg = regs.find((r) => r.scopeURL.endsWith("/ping-dashboard/") || r.scopeURL === new URL(BASE).href);
  check(!!reg, `service worker registration ${reg?.registrationId} for ${reg?.scopeURL}`);
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: new URL(BASE).origin, registrationId: reg.registrationId, data: JSON.stringify(payload) });
  await p.waitForTimeout(800);
  const shown = await p.evaluate(async () => (await (await navigator.serviceWorker.ready).getNotifications({ tag: "pwa-check" }))
    .map((n) => ({ title: n.title, body: n.body, url: n.data?.url, icon: n.icon, badge: n.badge })));
  check(shown.length === 1 && shown[0].title === payload.title && shown[0].body === payload.body && shown[0].url === payload.url,
        `the push is shown as a notification: "${shown[0]?.title}" / "${shown[0]?.body}" -> ${shown[0]?.url}`);
  // the tap: the worker focuses this window and sends it there; the same link, opened, lands on that message
  // (the owner is signed in when they tap; here the demo stands in, so the link keeps ?demo=1)
  const link = new URL(payload.url, BASE); link.search = "?demo=1";
  await p.goto(link.href); await p.waitForSelector("#ask-input"); await p.waitForTimeout(800);
  const hl = await p.evaluate(() => document.querySelector(".msg.hl")?.dataset.key || null);
  check(hl === `item:${items[0]}`, `the link opens the thread at that message (${hl})`);
  check(!errs.length, `no page errors${errs.length ? `: ${errs.slice(0, 2).join("; ")}` : ""}`);
  console.log(`\n${bad} problem(s)`);
  await b.close();
  process.exit(bad ? 1 : 0);
})();
