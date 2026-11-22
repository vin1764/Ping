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
  const cleanName = (s) => (NAMES ? (NAMES.displayName || NAMES.cleanName)(s) : String(s || "").trim());
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
               status: st === "yes" ? "on" : st === "no" ? "off" : null, itemIds: [it.id],
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
               mine: mine.length, roleIds: rs.map((r) => r.id), applied: applied.length, total: rs.length,
               digestId: digest ? digest.id : null,
               target: digest ? { item: digest.id } : mine.length === 1 || rs.length === 1 ? { role: (mine[0] || rs[0]).id } : { companies: true } };
    });
  }

  const todoWhat = (it) => (/fill the form/i.test(it.title || "") || it.details?.todo?.action === "fill_form" ? "form"
    : it.details?.todo?.action === "take_test" ? "test" : /submit/i.test(it.title || "") ? "submission" : "to-do");
  function todos(items, day, inChat, isFilled = () => false) {
    const one = (it) => ({ kind: "todo", at: ms(it.due_at), due: it.due_at, title: cleanName(it.company) || "To do", via: it.details?.via || null,
                           itemIds: [it.id], forms: todoWhat(it) === "form", filledAll: todoWhat(it) === "form" && isFilled(it),
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
      const filled = what === "form" ? its.filter(isFilled).length : 0;
      return { kind: "todo", group: true, at: t, due: new Date(t).toISOString(), itemIds: its.map((it) => it.id), what,
               forms: what === "form", filled, filledAll: filled > 0 && filled === its.length,
               title: `${its.length} ${what}s due ${clock(t)}${filled ? ` · ${filled} filled` : ""}`, sub: "", names: listNames(names, 4),
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

  // what a notice asks, said as what to do ("deadlines extended to 20:00", "submit CV by 20:00"), with the time it's
  // about and which list it belongs with (applications or forms), so the row reads as an action, not a subject line
  function noticeWhat(n) {
    const a = n.analysis || {}, kind = n.kind || a.kind, subj = String(n.subject || "");
    const todos = (n.todos || a.todos || []).filter((t) => t && t.action);
    const due = (act) => todos.find((t) => (!act || t.action === act) && t.due)?.due || null;
    const at = (v) => (v ? clock(ms(v)) : "");
    if (kind === "deadline_extended" || /extend|extension/i.test(subj)) {
      const d = due("apply") || due();
      return { many: d ? `Deadlines extended to ${at(d)}` : "Deadlines extended", one: d ? `deadline extended to ${at(d)}` : "deadline extended", due: d, list: "apply" };
    }
    if (/\bcv\b|resume/i.test(subj)) {
      const d = due("submit") || due("apply");
      return { many: d ? `Submit CV by ${at(d)}` : "Submit CV", one: d ? `submit CV by ${at(d)}` : "submit CV", due: d, list: "apply" };
    }
    if (due("fill_form")) return { many: `Fill a form by ${at(due("fill_form"))}`, one: `fill the form by ${at(due("fill_form"))}`, due: due("fill_form"), list: "form" };
    if (due("submit")) return { many: `Submit by ${at(due("submit"))}`, one: `submit by ${at(due("submit"))}`, due: due("submit"), list: "form" };
    if (due("accept_offer")) return { many: `Accept offers by ${at(due("accept_offer"))}`, one: `accept the offer by ${at(due("accept_offer"))}`, due: null };
    const KIND = { apply_open: ["Open for applications", "open for applications"], test: ["Tests", "test"], test_rooms: ["Test rooms out", "test rooms out"],
                   shortlist: ["Shortlists out", "shortlist out"], result: ["Results out", "results out"], ppt: ["Pre-placement talks", "pre-placement talk"],
                   schedule: ["Schedule", "schedule"] };
    if (KIND[kind]) {
      const d = kind === "apply_open" ? due("apply") : null;
      return { many: KIND[kind][0] + (d ? ` until ${at(d)}` : ""), one: KIND[kind][1] + (d ? ` until ${at(d)}` : ""), due: d, list: d ? "apply" : null };
    }
    return null;
  }

  const NOTICE_MAX = 6;
  function notices(list, day, items, inChat) {
    const today = (list || []).filter((n) => n.notice_time && dayOf(ms(n.notice_time)) === day)
      .sort((a, b) => ms(a.notice_time) - ms(b.notice_time));
    const rows = today.slice(0, NOTICE_MAX).map((n) => {
      const nid = n.notice_id ?? n.id;
      const it = (items || []).find((x) => x.notice_id === nid && inChat(x));
      const what = noticeWhat(n);
      const posted = `posted ${clock(ms(n.notice_time))}`;
      const base = { kind: "notice", at: ms(n.notice_time), noticeId: nid, itemIds: it ? [it.id] : [], target: it ? { item: it.id } : { notice: nid },
                     dueAt: what?.due ? ms(what.due) : null, list: what?.list || null };
      const many = /multiple|several|various/i.test(n.company || "");
      // one company: "ICICI Lombard · deadline extended to 20:00"
      if (!many) return { ...base, title: `${cleanName(n.company)} · ${what ? what.one : n.subject || "notice"}`, sub: posted };
      // several: "Deadlines extended to 20:00 · 18 companies", then which ones
      const names = noticeCompanies(n), asks = noticeAsks(n);
      const who = names.length ? (names.length > 3 ? `${names.slice(0, 3).join(", ")} +${names.length - 3}` : names.join(", ")) : "several companies";
      const count = names.length ? ` · ${names.length} compan${names.length === 1 ? "y" : "ies"}` : "";
      return { ...base, title: `${what ? what.many : n.subject || "Notice"}${count}`, companies: names, asks, sub: posted, names: who };
    });
    if (today.length > NOTICE_MAX) rows.push({ kind: "more", at: ms(today[NOTICE_MAX].notice_time),
      title: `+${today.length - NOTICE_MAX} more notices today`, sub: "", target: { feed: true } });
    return rows;
  }

  function build({ items = [], roles = [], notices: nlist = [], runs = [], profile = {}, now = Date.now(),
                   isMine = () => true, inChat = () => true, isFilled = () => false } = {}) {
    const day = dayOf(now), tomorrow = dayOf(now + 86400000);
    // a form row you've ticked in full is done: it stays on the list, but isn't "still ahead"
    const timed = [...tests(items, day, inChat), ...deadlines(roles, day, isMine, items, inChat), ...todos(items, day, inChat, isFilled)]
      .map((r) => ({ ...r, over: r.at <= now || !!r.filledAll }));
    // a notice about a deadline that's already a row (the 20:00 applications, the 20:00 forms) joins that row
    // instead of appearing twice: the row says the notice moved or set it
    const news = [];
    for (const r of notices(nlist, day, items, inChat)) {
      const same = r.dueAt && timed.find((t) => t.at === r.dueAt && ((r.list === "apply" && t.kind === "deadline") || (r.list === "form" && t.kind === "todo")));
      if (same) {
        same.noticeIds = [...(same.noticeIds || []), r.noticeId];
        same.sub = `${same.sub}${/notice/.test(same.sub) ? "" : ` · ${/extended/i.test(r.title) ? "extended by a notice" : "per a notice"} (${r.sub.replace("posted ", "")})`}`;
        continue;
      }
      news.push({ ...r, over: false });
    }
    const next = nextCheck(runs, profile, now);
    const ahead = timed.filter((r) => !r.over);
    const done = timed.filter((r) => r.over).sort((a, b) => a.at - b.at);
    const rows = [...ahead, ...news].sort((a, b) => a.at - b.at);
    const tTests = tests(items, tomorrow, inChat).length;
    const tDead = (roles || []).filter((r) => { const t = ms(r.effective_deadline || r.apply_end);
      return t > 0 && dayOf(t) === tomorrow && !r.applied && isMine(r); }).length
      + todos(items, tomorrow, inChat, isFilled).filter((r) => !r.filledAll).reduce((n, r) => n + (r.children ? r.children.length - (r.filled || 0) : 1), 0);
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

  // ---------------------------------------------------------------- the detail sheet behind a row (pure parts)
  const ERP = "https://erp.iitkgp.ac.in";
  // "Open on ERP": the role's own page on the ERP (where Apply is) when Ping knows the role's ids and your roll; it
  // opens in the browser and works while you're signed in to the ERP there. Otherwise the ERP's home page and what
  // to search for. A link only: Ping never opens the ERP itself.
  function erpLink(role, roll) {
    const company = cleanName(role?.company || "");
    if (role && role.jnf_id && role.com_id && role.yop && roll) {
      const q = new URLSearchParams({ jnf_id: role.jnf_id, com_id: role.com_id, yop: role.yop, user_type: "SU", rollno: roll });
      return { href: `${ERP}/TrainingPlacementSSO/TPJNFView.jsp?${q}`, direct: true, search: company };
    }
    return { href: `${ERP}/IIT_ERP3/`, direct: false, search: company };
  }
  // every form link an item carries (the notice's todo, its form links, the mail's), web links only, once each
  function formLinks(it) {
    const d = (it && it.details) || {};
    const all = [d.todo && d.todo.link, ...(d.forms || []), d.mail && d.mail.link, ...(d.mail_links || [])];
    return [...new Set(all.filter((u) => typeof u === "string" && /^https?:\/\//i.test(u)))];
  }
  // a sheet's role cards: for you and not applied first (soonest first), then applied, then the others (collapsed)
  function orderCards(cards) {
    // a card is "other" only when the marks say so (mine === false); with no marks (tests, notices, no targets) it's in view
    const rank = (c) => (c.mine === false && !c.applied ? 2 : c.applied ? 1 : 0);
    const by = (a, b) => rank(a) - rank(b) || (a.at || 0) - (b.at || 0) || String(a.company).localeCompare(String(b.company));
    const sorted = [...cards].sort(by);
    return { top: sorted.filter((c) => rank(c) < 2), others: sorted.filter((c) => rank(c) === 2) };
  }
  // which cards a filter chip keeps: "notapplied" | "foryou" | "all"
  const filterCards = (cards, f) => cards.filter((c) => f === "all" || (f === "foryou" ? c.mine !== false : !c.applied));
  // "55 applications close today 20:00 · 3 for you · 9 applied"
  function sheetTitle({ n, at, now, mine, applied, word = "application", verb = "close" }) {
    const day = dayOf(at) === dayOf(now) ? "today" : dayOf(at) === dayOf(now + 86400000) ? "tomorrow" : dayOf(at);
    const head = `${n} ${word}${n === 1 ? "" : "s"} ${verb}${n === 1 ? "s" : ""} ${day} ${clock(at)}`;
    return [head, mine ? `${mine} for you` : "", applied ? `${applied} applied` : ""].filter(Boolean).join(" · ");
  }

  const api = { build, countdown, nextCheck, clock, dayOf, cleanName, shortName, erpLink, formLinks, orderCards, filterCards, sheetTitle };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingToday = api;
})(typeof window !== "undefined" ? window : globalThis);
