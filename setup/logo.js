// Ping's mark: three original options (docs/design/logo-{pulse,bubble,monogram}.svg), shown as an app icon, a
// favicon and the chat header's avatar on a phone home-screen mock (docs/screenshots/logo/), and the chosen one
// rendered to every icon the app ships (dashboard/icons/: manifest any + maskable, iOS, favicon, push badge).
//   node setup/logo.js            (options + mock + icons for CHOSEN)
const fs = require("fs");
const { chromium } = require("playwright");
const ACCENT = "#0d6b61", INK = "#ffffff", WARM = "#f2b24a";
const CHOSEN = "bubble";
// glyphs drawn on a 512 canvas; s = scale for the maskable safe zone
const GLYPH = {
  pulse: (c) => `<g fill="none" stroke="${c}" stroke-width="30" stroke-linecap="round"><path d="M168,344a124,124,0,0,1,0-176"/><path d="M344,168a124,124,0,0,1,0,176"/><path d="M116,396a198,198,0,0,1,0-280" opacity=".55"/><path d="M396,116a198,198,0,0,1,0,280" opacity=".55"/></g><circle cx="256" cy="256" r="46" fill="${c}"/>`,
  bubble: (c, bg) => `<path d="M140,136h232a44,44,0,0,1,44,44v136a44,44,0,0,1-44,44H238l-78,62v-62h-20a44,44,0,0,1-44-44V180a44,44,0,0,1,44-44z" fill="${c}"/><circle cx="256" cy="248" r="28" fill="${bg}"/><g fill="none" stroke="${bg}" stroke-width="20" stroke-linecap="round"><path d="M202,200a68,68,0,0,0,0,96"/><path d="M310,200a68,68,0,0,1,0,96"/></g>`,
  monogram: (c) => `<path d="M196,382V136h78a82,82,0,0,1,0,164h-78" fill="none" stroke="${c}" stroke-width="46" stroke-linecap="round" stroke-linejoin="round"/><circle cx="356" cy="364" r="32" fill="${WARM}"/>`,
};
const icon = (name, { rx = 112, bg = ACCENT, fg = INK, scale = 1, bleed = false } = {}) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,512,512">${bleed ? `<rect width="512" height="512" fill="${bg}"/>` : `<rect width="512" height="512" rx="${rx}" fill="${bg}"/>`}` +
  `<g transform="translate(256 256) scale(${scale}) translate(-256 -256)">${GLYPH[name](fg, bg)}</g></svg>`;
// the push badge: the glyph alone, white on transparent (Android tints it)
const badge = (name) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,512,512"><defs><mask id="m"><rect width="512" height="512" fill="#000"/>` +
  `<g transform="translate(256 256) scale(1.18) translate(-256 -256)">${GLYPH[name]("#fff", "#000")}</g></mask></defs>` +
  `<rect width="512" height="512" fill="#fff" mask="url(#m)"/></svg>`;

async function png(page, svg, size, path, transparent = false) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<html><body style="margin:0;background:transparent">${svg.replace("<svg ", `<svg width="${size}" height="${size}" `)}</body></html>`);
  await page.screenshot({ path, omitBackground: transparent, clip: { x: 0, y: 0, width: size, height: size } });
}

(async () => {
  const b = await chromium.launch(process.env.PING_CHROMIUM ? { executablePath: process.env.PING_CHROMIUM } : {});
  const page = await b.newPage();
  for (const n of Object.keys(GLYPH)) fs.writeFileSync(`docs/design/logo-${n}.svg`, icon(n));
  // the home-screen mock: the icon among plain placeholder apps, its favicon in a browser tab, the chat header avatar
  for (const n of Object.keys(GLYPH)) {
    const ph = (i) => `<div class="app"><div class="ico" style="background:hsl(${i * 47 % 360} 18% ${55 + i % 3 * 8}%)"></div><span>App ${i}</span></div>`;
    const html = `<html><head><style>
      body{margin:0;font-family:system-ui,sans-serif;width:780px;height:820px;display:flex;gap:28px;padding:24px;box-sizing:border-box;background:#e9e6df}
      .phone{width:360px;height:770px;border-radius:44px;padding:56px 22px;box-sizing:border-box;background:linear-gradient(160deg,#3d5a6c,#1f2c33 60%,#4a3b2f);display:grid;grid-template-columns:repeat(4,1fr);align-content:start;gap:22px 10px}
      .app{display:flex;flex-direction:column;align-items:center;gap:6px;color:#fff;font-size:12px}
      .ico{width:62px;height:62px;border-radius:15px} .ico svg{width:62px;height:62px;display:block;border-radius:15px}
      .side{display:flex;flex-direction:column;gap:22px;flex:1}
      .tab{background:#fff;border-radius:10px 10px 0 0;padding:10px 14px;display:flex;gap:10px;align-items:center;font-size:14px;width:220px;box-shadow:0 1px 2px #0002}
      .tab svg{width:16px;height:16px}
      .hdr{display:flex;align-items:center;gap:12px;background:#fff;padding:14px;border-radius:14px;box-shadow:0 1px 2px #0002}
      .av svg{width:44px;height:44px;border-radius:50%;display:block} .hdr b{font-size:18px;display:block} .hdr small{color:#666}
      .big svg{width:180px;height:180px} h3{margin:0;font-size:15px;color:#333}
    </style></head><body>
      <div class="phone">${[1, 2, 3].map(ph).join("")}<div class="app"><div class="ico">${icon(n, { rx: 0 })}</div><span>Ping</span></div>${[4, 5, 6, 7, 8, 9, 10, 11].map(ph).join("")}</div>
      <div class="side"><h3>${n}</h3><div class="big">${icon(n)}</div>
        <div class="tab">${icon(n, { rx: 96 })}<span>Ping</span></div>
        <div class="hdr"><div class="av">${icon(n, { rx: 256 })}</div><div><b>Ping</b><small>checked 14:11 · next 15:11</small></div></div>
        <div class="tab" style="width:auto;background:#222;color:#eee">${icon(n, { rx: 96 })}<span>favicon on a dark tab bar</span></div></div>
    </body></html>`;
    await page.setViewportSize({ width: 780, height: 820 });
    await page.setContent(html);
    await page.screenshot({ path: `docs/screenshots/logo/option-${n}.png` });
  }
  // the chosen mark, everywhere the app shows one
  const n = CHOSEN, D = "dashboard/icons";
  fs.writeFileSync(`${D}/ping.svg`, icon(n));
  fs.writeFileSync(`${D}/ping-maskable.svg`, icon(n, { bleed: true, scale: 0.8 }));
  fs.writeFileSync(`${D}/badge.svg`, badge(n));
  await png(page, icon(n), 512, `${D}/icon-512.png`, true);
  await png(page, icon(n), 192, `${D}/icon-192.png`, true);
  await png(page, icon(n, { bleed: true, scale: 0.8 }), 512, `${D}/maskable-512.png`);
  await png(page, icon(n, { bleed: true }), 180, `${D}/apple-touch-icon.png`);      // iOS rounds it itself; no transparency
  await png(page, icon(n, { rx: 96 }), 32, `${D}/favicon-32.png`, true);
  await png(page, badge(n), 96, `${D}/badge-96.png`, true);
  await b.close();
  console.log("options: docs/design/logo-*.svg, mocks: docs/screenshots/logo/option-*.png; icons written for", CHOSEN);
})();
