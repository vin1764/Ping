/* The Today panel, without page code (tested in tests/js/today.test.js): what's on today, in time order, with what's
 * over moved to the bottom; a one-line preview of tomorrow; the next ERP check; and the live countdown text every
 * chip in the app uses.
 *
 * build({ items, roles, notices, runs, profile, now, isMine, inChat }) ->
 *   { rows: [{ kind: "test" | "deadline" | "todo" | "notice" | "more", at, over, title, sub, names, status, due, target,
 *              children, via: "email" | null }], ahead, tomorrow: { tests, deadlines, text }, nextCheck, empty, emptyText }
 *   Forms / to-dos due at the same time are one row ("5 forms due 20:00") whose children are the single ones; tests
 *   stay one row each. The next ERP check isn't a row: the header's status line says it (nextCheck is still returned).
 *   isMine(role): the role is one you'd apply to (eligible and "for you"); inChat(item): it is a chat message.
 */
(function (root) {
  "use strict";
  const TZ = "Asia/Kolkata";
  const ms = (v) => (v ? new Date(v).getTime() : NaN);
  // one formatter each, made once: toLocale*String(..., options) builds a new one per call (slow on a phone)
  const DAY = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });
  const HM = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  const dayOf = (t) => DAY.format(new Date(t));
  const clock = (t) => HM.format(new Date(t));
  // display names (dashboard/names.js): the website in brackets goes, the raw ERP name stays in the data
  const NAMES = root.PingNames || (typeof require === "function" ? require("./names.js") : null);
  const cleanName = (s) => (NAMES ? NAMES.cleanName(s) : String(s || "").trim());
  // "Piramal" for "Piramal Capital & Housing Finance Ltd", "TATA AIG" for "TATA AIG General Insurance": a list of names
  const LEGALISH = /\b(private|pvt|limited|ltd|inc|llp|llc|plc|co|company|corp|corporation|technologies|technology|services|solutions|group|global|labs|systems|software|india|general|insurance|capital|housing|finance|financial|bank|consulting|developers|energy|the|and)\b\.?/gi;
  const shortName = (s) => {
    const c = cleanName(s).replace(/\s*\(.*?\)/g, "").replace(/[.,&]/g, " ");
    const core = c.replace(LEGALISH, " ").replace(/\s+/g, " ").trim();
    const words = (core || c).split(" ").filter(Boolean);
    return words.slice(0, 2).join(" ") || c.trim();
  };
  const listNames = (names, n) => names.length > n ? `${names.slice(0, n).join(", ")}, …` : names.join(", ");
  const TEST_KINDS = ["test", "test_rooms", "interview", "gd"];

  // "in 1 h 48 m" / "in 42 m" / "in 35 s" / "in 3 days" / "over"; level: over | red (<1 h) | amber (<3 h) | plain
  function countdown(at, now) {
    const left = ms(at) - now;
    if (!(left > 0)) return { text: "over", level: "over" };
    const s = Math.floor(left / 1000), m = Math.floor(s / 60), h = Math.floor(m / 60);
    const level = left < 3600000 ? "red" : left < 3 * 3600000 ? "amber" : "plain";
    if (m < 1) return { text: `in ${s} s`, level };
    if (h < 1) return { text: `in ${m} m`, level };
    if (h < 24) return { text: m % 60 ? `in ${h} h ${m % 60} m` : `in ${h} h`, level };
    const d = Math.round(h / 24);
    return { text: d === 1 ? "in 1 day" : `in ${d} days`, level };
  }

  // the next time the ERP is checked: the last check's start plus the interval, moved past now
  function nextCheck(runs, profile, now) {
    const every = (Number(profile?.check_every_minutes) || 60) * 60000;
    const starts = (runs || []).map((r) => ms(r.started_at || r.requested_at)).filter((t) => t > 0);
    if (!starts.length) return null;
    let next = Math.max(...starts) + every;
    if (next <= now) next += Math.ceil((now - next + 1) / every) * every;
    return next;
  }

  const isTest = (it) => it.category === "test" || TEST_KINDS.includes(it.details?.kind);
  const roleOfTitle = (t) => (String(t || "").match(/\(([^)]+)\)/) || [])[1] || "";
  const pdfStatus = (it) => it.details?.pdf?.status || it.pdf_status || null;

  function tests(items, day, inChat) {
    const seen = new Map();
    for (const it of items || []) {
      if (!isTest(it) || !it.event_at || dayOf(ms(it.event_at)) !== day) continue;
      const st = pdfStatus(it);
      // a test that isn't about you (hidden with no list saying so) isn't on your day
      if (it.level === "hidden" && st !== "no" && st !== "yes") continue;
      const key = `${cleanName(it.company).toLowerCase()}|${ms(it.event_at)}`;
      const prev = seen.get(key);
      if (!prev || (!pdfStatus(prev) && st) || (prev.level === "hidden" && it.level !== "hidden")) seen.set(key, it);
    }
    return [...seen.values()].map((it) => {
      const d = it.details || {}, row = d.pdf?.details || {};
      const st = pdfStatus(it);
      const place = [row.room ? `room ${row.room}` : "", row.slot ? `slot ${row.slot}` : "", !row.room && d.venue ? d.venue : ""]
        .filter(Boolean).join(" · ");
      return { kind: "test", at: ms(it.event_at), due: it.event_at, via: d.via || null,
               title: `${cleanName(it.company)} ${d.kind === "interview" ? "interview" : "test"}`,
               sub: [roleOfTitle(it.title), clock(ms(it.event_at)), place].filter(Boolean).join(" · "),
               status: st === "yes" ? "on" : st === "no" ? "off" : null,
               target: inChat(it) ? { item: it.id } : { company: it.company } };
    });
  }

  function deadlines(roles, day, isMine, items, inChat) {
    const groups = new Map();
    for (const r of roles || []) {
      const t = ms(r.effective_deadline || r.apply_end);
      if (!(t > 0) || dayOf(t) !== day) continue;
      if (!groups.has(t)) groups.set(t, []);
      groups.get(t).push(r);
    }
    return [...groups.entries()].map(([t, rs]) => {
      const mine = rs.filter((r) => !r.applied && isMine(r)), applied = rs.filter((r) => r.applied);
      const names = [...new Set(mine.map((r) => cleanName(r.company)))].sort((a, b) => a.localeCompare(b));
      // the digest that lists this batch, so a tap opens the message that has every role
      const digest = (items || []).find((it) => inChat(it) && ["application", "deadline"].includes(it.details?.kind)
        && ms(it.due_at) === t);
      const parts = [mine.length ? `${mine.length} for you` : "", applied.length ? `${applied.length} applied` : "",
                     !mine.length && !applied.length ? `${rs.length} role${rs.length === 1 ? "" : "s"}` : ""].filter(Boolean);
      return { kind: "deadline", at: t, due: new Date(t).toISOString(),
               title: rs.length === 1 ? "1 application closes" : `${rs.length} applications close`, sub: `${clock(t)} · ${parts.join(" · ")}`,
               names: names.length > 4 ? `${names.slice(0, 4).join(", ")} +${names.length - 4}` : names.join(", "),
               mine: mine.length,
               target: digest ? { item: digest.id } : mine.length === 1 || rs.length === 1 ? { role: (mine[0] || rs[0]).id } : { companies: true } };
    });
  }

  const todoWhat = (it) => (/fill the form/i.test(it.title || "") || it.details?.todo?.action === "fill_form" ? "form"
    : it.details?.todo?.action === "take_test" ? "test" : /submit/i.test(it.title || "") ? "submission" : "to-do");
  function todos(items, day, inChat) {
    const one = (it) => ({ kind: "todo", at: ms(it.due_at), due: it.due_at, title: cleanName(it.company) || "To do", via: it.details?.via || null,
                           sub: `${clock(ms(it.due_at))} · ${String(it.title || "").replace(/^[^:]*:\s*/, "")}`,
                           target: inChat(it) ? { item: it.id } : { company: it.company } });
    const list = (items || []).filter((it) => it.category === "todo" && it.due_at && dayOf(ms(it.due_at)) === day
      && (it.level !== "hidden" || /digest/.test(it.details?.hidden_because || "")));
    const groups = new Map();
    for (const it of list) { const t = ms(it.due_at); if (!groups.has(t)) groups.set(t, []); groups.get(t).push(it); }
    return [...groups.entries()].map(([t, its]) => {
      if (its.length === 1) return one(its[0]);
      const child = (it) => ({ ...one(it), sub: [roleOfTitle(it.title), todoWhat(it) === "form" ? "fill the form" : todoWhat(it)].filter(Boolean).join(" · ") });
      // same time: one row, "5 forms due 20:00", that opens into the single ones
      const whats = new Set(its.map(todoWhat));
      const what = whats.size === 1 ? [...whats][0] : "to-do";
      const names = [...new Set(its.map((it) => shortName(it.company)).filter(Boolean))];
      const digest = (items || []).find((x) => inChat(x) && x.category === "digest" && x.details?.kind === "form" && ms(x.due_at) === t);
      return { kind: "todo", group: true, at: t, due: new Date(t).toISOString(),
               title: `${its.length} ${what}s due ${clock(t)}`, sub: "", names: listNames(names, 4),
               children: its.map(child).sort((a, b) => a.title.localeCompare(b.title)),
               target: digest ? { item: digest.id } : null };
    });
  }

  // a notice for several companies: which ones (first 3 + N) and what it asks ("fill the form by 16:00")
  const ACTION_WORDS = { fill_form: "fill a form", submit: "submit", accept_offer: "accept the offer", apply: "apply" };
  function noticeAsks(n) {
    const a = n.analysis || {};
    const todos = (n.todos || a.todos || []).filter((t) => t && t.action);
    const acts = [...new Set(todos.map((t) => t.action))];
    const main = acts.find((x) => x !== "apply") || acts[0];
    if (main) {
      const due = todos.find((t) => t.action === main && t.due)?.due;
      return `${ACTION_WORDS[main] || main.replace(/_/g, " ")}${due ? ` by ${clock(ms(due))}` : ""}`;
    }
    const kind = n.kind || a.kind;
    const KIND = { apply_open: "open for applications", deadline_extended: "deadlines extended", test: "tests", test_rooms: "test rooms",
                   shortlist: "shortlists", result: "results", ppt: "pre-placement talks", schedule: "schedule" };
    if (KIND[kind]) return KIND[kind];
    const first = String(n.preview || "").split(/(?<=[.!?])\s/)[0];
    return first ? first.slice(0, 80) : "";
  }
  function noticeCompanies(n) {
    const a = n.analysis || {};
    const names = (n.targets || a.targets || []).map((t) => shortName(t.company || String(t.name || "").replace(/^\s*\d+\s*\.\s*/, "")))
      .filter(Boolean);
    return [...new Set(names)];
  }

  const NOTICE_MAX = 6;
  function notices(list, day, items, inChat) {
    const today = (list || []).filter((n) => n.notice_time && dayOf(ms(n.notice_time)) === day)
      .sort((a, b) => ms(a.notice_time) - ms(b.notice_time));
    const rows = today.slice(0, NOTICE_MAX).map((n) => {
      const nid = n.notice_id ?? n.id;
      const it = (items || []).find((x) => x.notice_id === nid && inChat(x));
      // a notice for several companies says what it is first ("CV Submission"), then "several companies"
      const many = /multiple|several|various/i.test(n.company || "");
      if (!many) return { kind: "notice", at: ms(n.notice_time), title: cleanName(n.company),
                          sub: `${clock(ms(n.notice_time))} · ${n.subject || "Notice"}`, target: it ? { item: it.id } : { notice: nid } };
      // several companies: say which (first 3 + N) and what it asks, not "several companies"
      const names = noticeCompanies(n), asks = noticeAsks(n);
      const who = names.length ? (names.length > 3 ? `${names.slice(0, 3).join(", ")} +${names.length - 3}` : names.join(", ")) : "several companies";
      return { kind: "notice", at: ms(n.notice_time), title: n.subject || "Notice",
               sub: `${clock(ms(n.notice_time))}${asks ? ` · ${asks}` : ""}`, names: who,
               target: it ? { item: it.id } : { notice: nid } };
    });
    if (today.length > NOTICE_MAX) rows.push({ kind: "more", at: ms(today[NOTICE_MAX].notice_time),
      title: `+${today.length - NOTICE_MAX} more notices today`, sub: "", target: { feed: true } });
    return rows;
  }

  function build({ items = [], roles = [], notices: nlist = [], runs = [], profile = {}, now = Date.now(),
                   isMine = () => true, inChat = () => true } = {}) {
    const day = dayOf(now), tomorrow = dayOf(now + 86400000);
    const timed = [...tests(items, day, inChat), ...deadlines(roles, day, isMine, items, inChat), ...todos(items, day, inChat)]
      .map((r) => ({ ...r, over: r.at <= now }));
    const news = notices(nlist, day, items, inChat).map((r) => ({ ...r, over: false }));
    const next = nextCheck(runs, profile, now);
    const ahead = timed.filter((r) => !r.over);
    const done = timed.filter((r) => r.over).sort((a, b) => a.at - b.at);
    const rows = [...ahead, ...news].sort((a, b) => a.at - b.at);
    const tTests = tests(items, tomorrow, inChat).length;
    const tDead = (roles || []).filter((r) => { const t = ms(r.effective_deadline || r.apply_end);
      return t > 0 && dayOf(t) === tomorrow && !r.applied && isMine(r); }).length
      + todos(items, tomorrow, inChat).reduce((n, r) => n + (r.children ? r.children.length : 1), 0);
    const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
    return {
      rows: [...rows, ...done], ahead: ahead.length, nextCheck: next,
      empty: !timed.length && !news.length,
      emptyText: "Nothing scheduled today.",
      tomorrow: { tests: tTests, deadlines: tDead,
                  text: tTests || tDead ? `Tomorrow: ${[tTests ? plural(tTests, "test") : "", tDead ? plural(tDead, "deadline") : ""]
                    .filter(Boolean).join(", ")}` : "Tomorrow: nothing scheduled yet" },
    };
  }

  const api = { build, countdown, nextCheck, clock, dayOf, cleanName, shortName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingToday = api;
})(typeof window !== "undefined" ? window : globalThis);
