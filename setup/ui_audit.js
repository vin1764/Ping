// The UI audit: every screen and card type at 390 px, in the demo and in the signed-in view, flagged for
//   - truncated text on a line that says who / what (line 1 of a card, a Today row's title, a heading)
//   - the same thing said twice on one card (a time twice, the company again inside the title)
//   - raw notice titles ([URGENT], "CDC |"), IDs (notice numbers, sample: keys, UUIDs) on a collapsed card
//   - "Pvt Ltd" / "Private Limited" / "Limited" / "Ltd" on screen
//   - collapsed cards taller than 3 lines of text plus one button row
//   - a text card's summary (line 2) cut: ending in "…" / "...", hidden overflow, not ending as a sentence ends
//     (cut mid-word), or longer than 2 lines; a digest's list longer than 2 lines
// At 390 px (a phone) and 1280 px (desktop).
// The signed-in view: the demo is loaded once, its saved thread is marked as the owner's, and the page is opened
// offline, so it renders as the signed-in owner (no Demo badge, the owner's code paths) without anyone's login.
//   node setup/ui_audit.js [url]          (default: a local build on http://localhost:8799/)
const { chromium } = require("playwright");
const BASE = process.argv[2] || "http://localhost:8799/";
const SCREENS = ["#chat", "#today", "#forms", "#companies", "#profile", "#feed"];

const AUDIT = () => {
  const vis = (el) => { const b = el.getBoundingClientRect(); const s = getComputedStyle(el); return b.width > 0 && b.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const out = [];
  const say = (what, el) => out.push(`${what}: "${(el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 90)}"`);
  // 1. truncated who/what lines
  for (const el of document.querySelectorAll(".cc-l1, .today-row .t-title, .role-row .co, .fg-head, h1, h2, .forms-sec summary h2")) {
    if (!vis(el) || el.closest(".cc-detail, .open") || !(el.innerText || "").trim()) continue;
    if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).textOverflow === "ellipsis") say("cut off", el);
  }
  const cards = [...document.querySelectorAll(".card-c:not(.open), .today-row, .role-row")].filter((c) => vis(c) && !c.closest(".cc-detail"));
  for (const c of cards) {
    const head = c.querySelector(".cc-text, .t-body") || c;
    const text = head.innerText || "";
    // 2. the same time twice; the company again after line 1
    const times = text.match(/\b\d{2}:\d{2}\b/g) || [];
    if (new Set(times).size < times.length) say("time said twice", c);
    const co = (c.querySelector(".co")?.innerText || "").trim();
    const rest = [...head.querySelectorAll(".cc-l2, .cc-l3, .t-sub, .t-names, .rn")].map((e) => e.innerText).join(" ");
    if (co.length >= 4 && !/\+\d/.test(co) && new RegExp(`\\b${co.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(rest)) say("company said again", c);
    // 3. raw titles, IDs
    if (/\[URGENT\]|\bCDC \||\s\|\s/.test(text)) say("raw notice title", c);
    if (/\bnotice \d{3,}\b|\bsample:|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(text)) say("an ID on a card", c);
    // 5. height: 3 lines of text (a text card: line 1 and a summary of at most 2 lines)
    const sum = c.querySelector(".cc-sum");
    const lines = sum ? [...head.children].filter((e) => e !== sum).reduce((n, e) => n + Math.round(e.getBoundingClientRect().height / 22), 0)
        + Math.round(sum.getBoundingClientRect().height / 20)
      : Math.round(head.getBoundingClientRect().height / 22);
    if (c.matches(".card-c") && lines > 3) say(`${lines} lines of text`, c);
    // 6. the summary: whole, a sentence, at most 2 lines
    if (sum && vis(sum)) {
      const t = (sum.innerText || "").trim(), sl = Math.round(sum.getBoundingClientRect().height / 20);
      if (/(…|\.\.\.)$/.test(t)) say("summary ends in …", sum);
      else if (sum.scrollHeight > sum.clientHeight + 1 || sum.scrollWidth > sum.clientWidth + 1) say("summary cut (overflow)", sum);
      else if (sum.dataset.summary && !/[.!?)"”]$/.test(t)) say("summary cut mid-word", sum);
      if (sl > 2) say(`summary on ${sl} lines`, sum);
    }
    if (c.matches(".today-row") && lines > 3) say(`${lines} lines`, c);
  }
  // 4. legal suffixes anywhere on screen (outside an opened detail)
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!el || !vis(el) || el.closest(".cc-detail, .more, details:not([open]), script, style, textarea, input")) continue;
    if (/\b(pvt\.?\s*ltd|private limited|limited|ltd\.?)\b/i.test(n.textContent)) { say("legal suffix", el); }
  }
  return [...new Set(out)];
};

const WIDTHS = [390, 1280];
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  const errs = []; p.on("pageerror", (e) => errs.push(e.message));
  const flags = [];
  async function sweep(mode) {
    for (const w of WIDTHS) {
      await p.setViewportSize({ width: w, height: w > 600 ? 900 : 844 }); await p.waitForTimeout(300);
      await sweepAt(`${mode} ${w}px`);
    }
  }
  async function sweepAt(mode) {
    for (const hash of SCREENS) {
      console.error(`${mode} ${hash}`);
      await p.evaluate((h) => { location.hash = h; }, hash); await p.waitForTimeout(800);
      // the whole page: scroll the scroller through, auditing as we go
      const seen = new Set();
      for (let i = 0; i < 25; i++) {
        for (const f of await p.evaluate(AUDIT)) if (!seen.has(f)) { seen.add(f); flags.push(`${mode} ${hash}: ${f}`); }
        const more = await p.evaluate(() => { const s = document.querySelector("#thread") && location.hash === "#chat" ? document.querySelector("#thread") : document.querySelector("#app");
          if (!s) return false; const before = s.scrollTop; s.scrollTop += s.clientHeight * 0.9; return s.scrollTop > before; });
        if (!more) break;
        await p.waitForTimeout(80);
      }
    }
    // the Today sheet and a role's sheet
    await p.evaluate(() => { location.hash = "#today"; }); await p.waitForTimeout(600);
    if (await p.$("#today-page .today-row.k-deadline")) {
      await p.click("#today-page .today-row.k-deadline"); await p.waitForTimeout(700);
      for (const f of await p.evaluate(AUDIT)) flags.push(`${mode} today sheet: ${f}`);
      await p.keyboard.press("Escape"); await p.evaluate(() => document.querySelector("#sheet")?.close?.());
    }
  }
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 40000 }); await p.waitForTimeout(2500);
  await sweep("demo");
  // the signed-in view: the saved thread, marked as the owner's, opened offline
  console.error("signed-in: the saved thread, as the owner's, then offline");
  const ok = await p.evaluate(async () => {
    const data = await (await fetch("demo-data.json", { cache: "no-store" })).json();
    return new Promise((res) => {
      const r = indexedDB.open("ping", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("kv");
      r.onsuccess = () => { const t = r.result.transaction("kv", "readwrite");
        t.objectStore("kv").put({ kind: "real", demo: false, data, chat: [], savedAt: new Date().toISOString() }, "snap");
        t.oncomplete = () => res(true); t.onerror = () => res(false); };
      r.onerror = () => res(false);
    });
  });
  if (ok) {
    // "no connection": the page is told it's offline and every Supabase call fails, so it opens the saved thread
    // as the signed-in owner (the app's own offline path), with nobody's login
    await p.addInitScript(() => Object.defineProperty(Navigator.prototype, "onLine", { get: () => false }));
    await p.route(/supabase\.co/, (r) => r.abort());
    // a local build has no Supabase settings (no secrets here): a config with an address, so the app takes the
    // signed-in path (every call to it fails above, as offline)
    await p.route(/\/config\.js(\?|$)/, (r) => r.fulfill({ contentType: "application/javascript",
      body: 'window.PING_CONFIG = {"supabaseUrl": "https://offline.supabase.co", "supabaseKey": "offline"}; window.PING_BUILD = "audit";' }));
    await p.goto(`${BASE}#chat`, { waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => {});
    await p.waitForSelector(".msg.item", { timeout: 20000 }).catch(() => {});
    // the owner's path (the saved thread, offline); the badge still says Demo because the data is the demo's sample
    const owner = await p.evaluate(() => /Offline: your thread as of/.test(document.querySelector("#status")?.innerText || ""));
    if (await p.$(".msg.item")) { flags.push(...(owner ? [] : ["signed-in: didn't open as the owner's saved thread"])); await sweep("signed-in"); }
    else flags.push("signed-in: the saved thread didn't open offline (checked the demo only)");
  } else flags.push("signed-in: no saved thread to open (checked the demo only)");
  console.log(flags.length ? flags.join("\n") : "no flags");
  console.log(errs.length ? `page errors: ${errs.join(" | ")}` : "no page errors");
  await b.close();
  process.exit(flags.filter((f) => !/checked the demo only/.test(f)).length || errs.length ? 1 : 0);
})();
