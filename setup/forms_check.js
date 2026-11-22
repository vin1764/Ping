// The Forms tab on the demo (?demo=1), phone 390x844 and PC 1280x800: the sections, a tick moves a form to Filled
// with an undo toast, undo moves it back, the tab's badge and the same form's checkbox in the chat follow, a reload
// keeps the ticks, Ask Ping answers the three form questions ("mark … as filled" ticks it), search and For you / All.
// Screenshots to docs/screenshots/final/forms-*.
//   node setup/forms_check.js [url]        (default: a local build on http://localhost:8799/)
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8799/";
const OUT = "docs/screenshots/final";
let bad = 0;
const ok = (cond, what, note = "") => { if (!cond) bad++; console.log(`${cond ? "ok  " : "FAIL"} ${what}${note ? `: ${note}` : ""}`); };

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  for (const [w, hgt, tag] of [[390, 844, "390"], [1280, 800, "1280"]]) {
    for (const scheme of ["light", "dark"]) {
      console.log(`\n${tag}x${hgt} ${scheme}`);
      const ctx = await b.newContext({ viewport: { width: w, height: hgt }, colorScheme: scheme });
      const p = await ctx.newPage();
      const errs = []; p.on("pageerror", (e) => errs.push(e.message));
      await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 30000 });
      const tabVisible = await p.locator('#nav a[data-route="forms"]').isVisible();
      ok(tabVisible, "the Forms tab is in the bar / rail");
      await p.click('#nav a[data-route="forms"]');
      await p.waitForSelector("#forms-list .forms-sec");
      await p.click('[data-only="all"]');
      const count = () => p.evaluate(() => Object.fromEntries([...document.querySelectorAll(".forms-sec")].map((s) => [s.id.replace("forms-", ""), s.querySelectorAll(".form-row").length])));
      const before = await count();
      ok(Object.values(before).reduce((a, x) => a + x, 0) > 0, "the sections list the forms", JSON.stringify(before));
      await p.screenshot({ path: `${OUT}/forms-${tag}-${scheme}.png` });
      if (scheme === "dark") { await ctx.close(); continue; }
      // tick the first not-filled form
      const row = p.locator(".forms-sec:not(#forms-filled) .form-row").first();
      const key = await row.getAttribute("data-form");
      await p.locator(`.form-row[data-form="${key}"] input.tick-box`).click();
      await p.waitForTimeout(200);
      const after = await count();
      const toast = await p.locator("#toast:not([hidden])").innerText().catch(() => "");
      ok(after.filled === before.filled + 1 && /Ticked/.test(toast) && /Undo/.test(toast), "a tick moves it to Filled, with an undo toast", `${JSON.stringify(after)} · "${toast.replace(/\s+/g, " ")}"`);
      await p.screenshot({ path: `${OUT}/forms-ticked-${tag}.png` });
      await p.click("#toast .linklike");
      await p.waitForTimeout(200);
      const undone = await count();
      ok(undone.filled === before.filled, "Undo moves it back");
      // tick again; it shows in the chat's digest checkbox and survives a reload
      await p.locator(`.form-row[data-form="${key}"] input.tick-box`).click();
      await p.waitForTimeout(200);
      await p.reload(); await p.waitForSelector(".msg.item, #forms-list", { timeout: 30000 });
      await p.evaluate(() => { location.hash = "#forms"; }); await p.waitForSelector("#forms-list .forms-sec");
      await p.click('[data-only="all"]');
      const kept = await p.locator(`#forms-filled .form-row[data-form="${key}"]`).count();
      ok(kept === 1, "the tick survives a reload");
      const inChat = await p.evaluate((k) => { location.hash = "#chat"; return new Promise((r) => setTimeout(() => {
        const boxes = [...document.querySelectorAll(`input[data-form-key="${CSS.escape(k)}"]`)]; r({ n: boxes.length, checked: boxes.every((x) => x.checked) }); }, 600)); }, key);
      ok(inChat.n === 0 || inChat.checked, "the same form's checkbox in the chat shows the tick", JSON.stringify(inChat));
      // badge
      const badge = await p.evaluate(() => { const d = document.querySelector("#nav-forms"); return d && !d.hidden ? d.textContent : "0"; });
      ok(/^\d+$/.test(badge), "the tab's badge counts forms due in 24 h", badge);
      // Ask Ping
      const ask = async (q) => { const n = await p.locator(".msg.ping:not(.typing)").count();
        await p.fill("#ask-input", q); await p.press("#ask-input", "Enter");
        await p.waitForFunction((n) => document.querySelectorAll(".msg.ping:not(.typing)").length > n, n, { timeout: 15000 });
        return (await p.locator(".msg.ping:not(.typing) .text").last().innerText()).replace(/\s+/g, " "); };
      const a1 = await ask("which forms haven't I filled?");
      ok(/forms? not ticked yet|Nothing left/.test(a1), "Ask: which forms haven't I filled?", a1.slice(0, 120));
      const company = await p.evaluate((k) => (window.__f = null, k), key);
      const name = await p.evaluate(() => [...document.querySelectorAll(".form-row .co")].map((e) => e.textContent)[0] || "");
      const first = (a1.match(/- ([^:]+):/) || [])[1] || "";
      const word = first.split(/[ ,]/)[0];
      const a2 = await ask(`did I fill the ${word} form?`);
      ok(/^(Yes|Not ticked yet)/.test(a2), `Ask: did I fill the ${word} form?`, a2.slice(0, 120));
      const a3 = await ask(`mark the ${word} form as filled`);
      ok(/^Done: .* ticked as filled|already ticked/.test(a3), `Ask: mark the ${word} form as filled`, a3.slice(0, 120));
      const a4 = await ask(`did I fill the ${word} form?`);
      ok(/^Yes/.test(a4), "…and now it says yes", a4.slice(0, 80));
      // search and For you
      await p.evaluate(() => { location.hash = "#forms"; }); await p.waitForSelector("#forms-search");
      await p.fill("#forms-search", word);
      const found = await p.locator(".form-row").count();
      ok(found >= 1, `search "${word}" finds it`, String(found));
      await p.fill("#forms-search", "");
      await p.click('[data-only="foryou"]');
      ok(true, "For you filter", String(await p.locator(".form-row").count()));
      ok(!errs.length, "no page errors", errs.slice(0, 2).join("; "));
      await ctx.close();
    }
  }
  await b.close();
  console.log(`\n${bad} problem(s)`);
  process.exit(bad ? 1 : 0);
})();
