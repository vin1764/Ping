// What a compact card says, pure (no page): the deadline in relative words ("Today 23:59 · 2 h 24 m left",
// "Tomorrow 20:00", "Mon 23 Nov · past due") and a notice / form title cleaned down to what it adds to "Company ·
// task" ("[URGENT] : CDC | NOMURA | Additonal Details" adds nothing; "Groww | APM Additional Requirement" adds "APM").
// Only what renders: the data is never changed. Node tests: tests/js/cards.test.js.
(function (root) {
  const TZ = "Asia/Kolkata";
  const ms = (v) => (v == null || v === "" ? NaN : typeof v === "number" ? v : new Date(v).getTime());
  const dayKey = (t) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date(t));
  const hm = (t) => new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(t));
  const dayMon = (t) => new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" })
    .format(new Date(t)).replace(",", "");
  const plusDays = (t, n) => dayKey(t + n * 86400000);

  // "2 h 24 m", "45 m", "under 1 m"
  function span(d) {
    const m = Math.floor(d / 60000);
    if (m < 1) return "under 1 m";
    const h = Math.floor(m / 60);
    return h ? `${h} h${m % 60 ? ` ${m % 60} m` : ""}` : `${m} m`;
  }

  // The second line of a card. event: a test / talk (it is "over", not "past due"). level: for the colour.
  function relDeadline(at, now, { event = false } = {}) {
    const t = ms(at);
    if (Number.isNaN(t)) return { text: "No deadline given", level: "none" };
    const today = dayKey(now), day = dayKey(t);
    if (t <= now) return { text: `${day === today ? `Today ${hm(t)}` : dayMon(t)} · ${event ? "over" : "past due"}`, level: "over" };
    if (day === today) return { text: `Today ${hm(t)} · ${span(t - now)} left`, level: t - now <= 3 * 3600000 ? "urgent" : "today" };
    if (day === plusDays(now, 1)) return { text: `Tomorrow ${hm(t)}`, level: "soon" };
    return { text: `${dayMon(t)} ${hm(t)}`, level: "later" };
  }

  // ---------------------------------------------------------------- titles
  const TYPOS = [[/\badditonal\b/gi, "Additional"], [/\baddtional\b/gi, "Additional"], [/\bmanagment\b/gi, "Management"],
    [/\brequirment(s?)\b/gi, "Requirement$1"], [/\brecuritment\b/gi, "Recruitment"], [/\bdetials\b/gi, "Details"],
    [/\bregisteration\b/gi, "Registration"], [/\bapplicaton\b/gi, "Application"], [/\bprefrence\b/gi, "Preference"],
    [/\bshorlist(ed)?\b/gi, "Shortlist$1"], [/\bsubmision\b/gi, "Submission"], [/\bintership\b/gi, "Internship"],
    [/\banalyist\b/gi, "Analyst"], [/\bconsultent\b/gi, "Consultant"]];
  // words that only say "a form / an application from the placement office": never worth a line of their own
  const GENERIC = new Set(("additional details detail requirement requirements form forms google application applications apply " +
    "campus recruitment recruitments registration register notice notices update updates urgent important reminder cdc ft fte " +
    "full time intern internship internships placement placements drive for the of and to a an in on regarding reg re fill " +
    "filling link links submission submit cv cvs resume resumes preference preferences process batch students student all " +
    "please kindly iit kgp kharagpur new hiring opportunity opportunities round info information pfa attached").split(" "));
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const tidy = (s) => s.replace(/\s{2,}/g, " ").replace(/^[\s·,.;-]+|[\s·,.;-]+$/g, "").trim();
  // "GOLDMAN SACHS" stays; "OPERATIONS ANALYST" -> "Operations Analyst" (a shouted phrase), short acronyms kept
  const unshout = (s) => (s === s.toUpperCase() && /[A-Z]{5,}/.test(s)
    ? s.split(" ").map((w) => (w.length <= 3 ? w : w[0] + w.slice(1).toLowerCase())).join(" ") : s);
  function companyWords(company) {
    const base = String(company || "").replace(/\s*\([^)]*\)/g, "")
      .replace(/\b(private|pvt|limited|ltd|llp|inc|india|technologies|technology|solutions|services|group)\b\.?/gi, " ").trim();
    const words = base.split(/[\s.]+/).filter((w) => w.length >= 2).map((w) => w.toLowerCase());
    // initials: "FischerJordan" -> "fj", "Axis Bank" -> "ab"
    const parts = base.replace(/([a-z])([A-Z])/g, "$1 $2").split(/[\s.]+/).filter(Boolean);
    const initials = parts.length > 1 ? parts.map((p) => p[0]).join("").toLowerCase() : "";
    return { words: new Set(words), whole: base.toLowerCase().replace(/[^a-z0-9]+/g, ""), initials };
  }
  // The title as it reads once what the first line already says is gone: "" when nothing is left.
  // drop: more words the first line says (the task, the role shown elsewhere)
  function cleanTitle(title, company, drop = []) {
    let s = String(title || "");
    if (!s.trim()) return "";
    for (const [re, to] of TYPOS) s = s.replace(re, to);
    s = s.replace(/\[[^\]]*\]|\((urgent|important|reminder)\)/gi, " ");
    const co = companyWords(company);
    const dropWords = new Set(drop.flatMap((d) => String(d || "").toLowerCase().split(/\s+/)).filter(Boolean));
    const isCompany = (w) => {
      const k = w.toLowerCase().replace(/[^a-z0-9]+/g, "");
      return !!k && (co.words.has(w.toLowerCase().replace(/[.,]+$/, "")) || k === co.whole || (co.initials.length > 1 && k === co.initials)
        || (k.length >= 4 && co.whole.startsWith(k)));
    };
    const junk = (w) => {
      const k = w.toLowerCase().replace(/[^a-z0-9.]+/g, "").replace(/\.$/, "");
      return !k || GENERIC.has(k) || /^(19|20)\d\d(-\d\d)?$/.test(k) || dropWords.has(k) || isCompany(w);
    };
    const segs = s.split(/\s*(?:\||:|–|—|\s-\s)\s*/);
    const kept = [];
    for (const seg of segs) {
      let words = seg.split(/\s+/).filter(Boolean).filter((w) => !isCompany(w));
      while (words.length && junk(words[0])) words.shift();
      while (words.length && junk(words[words.length - 1])) words.pop();
      if (!words.length || words.every(junk)) continue;
      kept.push(unshout(tidy(words.join(" "))));
    }
    const out = tidy([...new Set(kept)].join(" · "));
    return out ? out[0].toUpperCase() + out.slice(1) : "";
  }

  const api = { relDeadline, cleanTitle, span };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingCards = api;
})(typeof window !== "undefined" ? window : globalThis);
