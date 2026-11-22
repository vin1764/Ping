// A tick reaches your other open device at once: two browser contexts share one login (the checks' demo session,
// ?anon-demo=1, the same as two phones signed in as you), A ticks a form on the Forms tab, B shows it ticked within a
// few seconds without a reload (Realtime on form_status), then B unticks and A follows. Also: the tick is saved
// (form_status), a reload keeps it.
//   node setup/forms_sync_check.js [url]        (default: the live site)
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
let bad = 0;
const ok = (cond, what, note = "") => { if (!cond) bad++; console.log(`${cond ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  const a = await b.newContext({ viewport: { width: 390, height: 844 } });
  const pa = await a.newPage();
  const errs = []; pa.on("pageerror", (e) => errs.push(e.message));
  await pa.goto(`${BASE}?anon-demo=1`); await pa.click("#view-demo");
  await pa.waitForSelector("[data-onboarding], #ask-input", { timeout: 60000 });
  if (await pa.locator(".chips .chip:has-text('Use the demo profile')").count()) await pa.click(".chips .chip:has-text('Use the demo profile')");
  await pa.waitForSelector("#ask-input", { timeout: 30000 });
  await pa.waitForFunction(() => document.body.dataset.live === "on", null, { timeout: 30000 }).catch(() => {});
  // the second device: the same login (its saved session), opened separately
  const state = await a.storageState({ indexedDB: true });
  const c = await b.newContext({ viewport: { width: 1280, height: 800 }, storageState: state });
  const pc = await c.newPage(); pc.on("pageerror", (e) => errs.push(e.message));
  await pc.goto(`${BASE}#forms`);
  await pc.waitForFunction(() => document.body.dataset.live === "on", null, { timeout: 30000 }).catch(() => {});
  for (const p of [pa, pc]) { await p.evaluate(() => { location.hash = "#forms"; }); await p.waitForSelector("#forms-list .form-row", { timeout: 30000 }); await p.click('[data-only="all"]'); }
  ok(await pa.evaluate(() => document.body.dataset.live) === "on" && await pc.evaluate(() => document.body.dataset.live) === "on", "both devices are live (Realtime)");
  const key = await pa.locator(".forms-sec:not(#forms-filled) .form-row").first().getAttribute("data-form");
  const checked = (p) => p.evaluate((k) => document.querySelector(`input[data-form-key="${CSS.escape(k)}"]`)?.checked, key);
  ok(!(await checked(pa)) && !(await checked(pc)), "the form starts unticked on both", key);
  let t = Date.now();
  await pa.locator(`.form-row[data-form="${key}"] input.tick-box`).click();
  const seen = await pc.waitForFunction((k) => document.querySelector(`#forms-filled .form-row[data-form="${CSS.escape(k)}"]`), key, { timeout: 15000 }).then(() => true).catch(() => false);
  ok(seen, "A ticks it: B shows it in Filled without a reload", `${Date.now() - t} ms`);
  t = Date.now();
  await pc.locator(`.form-row[data-form="${key}"] input.tick-box`).click();
  const back = await pa.waitForFunction((k) => !document.querySelector(`#forms-filled .form-row[data-form="${CSS.escape(k)}"]`), key, { timeout: 15000 }).then(() => true).catch(() => false);
  ok(back, "B unticks it: A follows", `${Date.now() - t} ms`);
  await pa.locator(`.form-row[data-form="${key}"] input.tick-box`).click();
  await pa.waitForTimeout(800);
  await pa.reload(); await pa.waitForSelector("#forms-list .form-row", { timeout: 30000 }); await pa.click('[data-only="all"]');
  ok(await pa.locator(`#forms-filled .form-row[data-form="${key}"]`).count() === 1, "saved: a reload keeps the tick");
  await pa.locator(`.form-row[data-form="${key}"] input.tick-box`).click();   // leave it as it was
  await pa.waitForTimeout(800);
  ok(!errs.length, "no page errors", errs.slice(0, 2).join("; "));
  await b.close();
  console.log(`\n${bad} problem(s)`);
  process.exit(bad ? 1 : 0);
})();
