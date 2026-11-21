// node setup/today_grouped_shot.js docs/screenshots   (needs a local build served on :8765: bash dashboard/build.sh; cd _site; python3 -m http.server 8765)
// The demo snapshot plus five forms due at 20:00 and a multi-company "Additional requirement" notice (made up),
// so Today shows a grouped row; the chat as it is.
const { chromium } = require("playwright");
const fs = require("fs");
const OUT = process.argv[2];
(async () => {
  const demo = JSON.parse(fs.readFileSync("dashboard/demo-data.json", "utf8"));
  const due = "2026-11-21T20:00:00+05:30";
  const names = ["Piramal Capital & Housing Finance", "SLB", "LTM", "Auro Group(www.AuroIM.com)", "Esri India"];
  names.forEach((c, i) => demo.items.push({ id: `sample:extra:form${i}`, company: c, category: "todo", level: "show", due_at: due, event_at: null,
    title: `${c} (Analyst): fill the form by Sat 21 Nov 20:00.`, details: { todo: { action: "fill_form", due } }, role_ids: [], first_seen: "2026-11-21T11:02:00+05:30", sort_at: due }));
  demo.notices.push({ id: "sample:extra:n", notice_id: "9999", company: "Multiple Companies", subject: "Additional requirement",
    notice_time: "2026-11-21T11:02:00+05:30", preview: "", analysis: { kind: "form", targets: names.map((n) => ({ name: n, company: n })),
      todos: [{ action: "fill_form", due }] } });
  const b = await chromium.launch();
  for (const [w, hgt, name] of [[1280, 800, "today-grouped-1280.png"], [390, 844, "today-grouped-390.png"]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: hgt }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    await p.route("**/demo-data.json", (r) => r.fulfill({ contentType: "application/json", body: JSON.stringify(demo) }));
    await p.goto(`http://localhost:8765/?demo=1${w < 600 ? "#today" : "#chat"}`); await p.waitForSelector(".today-row", { timeout: 20000 });
    await p.waitForTimeout(700);
    const g = p.locator(".today-row.group").first();
    if (await g.count()) { await g.click(); await p.waitForTimeout(250); }
    await p.screenshot({ path: `${OUT}/${name}` });
    if (w > 600) console.log(await p.locator("#today-rail").innerText());
    await ctx.close();
  }
  await b.close();
})();
