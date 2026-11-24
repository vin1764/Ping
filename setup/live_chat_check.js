// The live demo's chat, typed like a student: a source word that isn't a company, a follow-up with no company, a
// source named, the same question twice. Checks each answer: no "I don't have <source word>", never the same answer
// twice in a row, at most 3 lines unless a JD.
//   node setup/live_chat_check.js [url]     (default: the live site)
const { chromium } = require("playwright");
const BASE = process.argv[2] || "https://vin1764.github.io/ping-dashboard/";
const TURNS = ["deloitte jd", "check notices for jd", "deloitte jd on mail??", "what about ctc", "what about ctc", "pdf mein hai kya?"];

(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await p.goto(`${BASE}?demo=1#chat`); await p.waitForSelector(".msg.item", { timeout: 40000 }); await p.waitForTimeout(1500);
  let bad = 0, prev = null;
  for (const q of TURNS) {
    const n = await p.$$eval(".msg.ping", (m) => m.length);
    await p.fill("#ask-input", q);
    await p.keyboard.press("Enter");
    await p.waitForFunction((n) => document.querySelectorAll(".msg.ping").length > n &&
      !/thinking|typing/i.test(document.querySelectorAll(".msg.ping")[document.querySelectorAll(".msg.ping").length - 1].innerText), n, { timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(600);
    const a = await p.$$eval(".msg.ping", (m) => m[m.length - 1].innerText.replace(/\n\d\d:\d\d\s*$/, "").trim());
    const lines = a.split("\n").filter((l) => l.trim() && !/^\d\d:\d\d$/.test(l.trim())).length;
    const problems = [/I don't have (Notices?|Mail|Pdf|Mein|Ctc)\b/i.test(a) && "a source word read as a company",
      prev && a === prev && "the same answer twice", lines > (/jd/i.test(q) && !/mail|notices/.test(q) ? 9 : 4) && `${lines} lines`].filter(Boolean);
    if (problems.length) bad++;
    console.log(`${problems.length ? "FAIL" : "ok  "} ${q}\n     ${a.replace(/\n/g, "\n     ")}${problems.length ? `\n     -> ${problems.join(", ")}` : ""}`);
    prev = a;
  }
  await b.close();
  process.exit(bad ? 1 : 0);
})();
