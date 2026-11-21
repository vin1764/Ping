/* The Today panel, without page code (tested in tests/js/today.test.js): what's on today, in time order, with what's
 * over moved to the bottom; a one-line preview of tomorrow; the next ERP check; and the live countdown text every
 * chip in the app uses.
 *
 * build({ items, roles, notices, runs, profile, now, isMine, inChat }) ->
 *   { rows: [{ kind: "test" | "deadline" | "todo" | "notice" | "more" | "check", at, over, title, sub, names, status,
 *              due, target }], ahead, tomorrow: { tests, deadlines, text }, nextCheck, empty, emptyText }
 *   isMine(role): the role is one you'd apply to (eligible and "for you"); inChat(item): it is a chat message.
 */
(function (root) {
  "use strict";
  const TZ = "Asia/Kolkata";
  const ms = (v) => (v ? new Date(v).getTime() : NaN);
  const dayOf = (t) => new Date(t).toLocaleDateString("en-CA", { timeZone: TZ });
  const clock = (t) => new Date(t).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  // display names (dashboard/names.js): the website in brackets goes, the raw ERP name stays in the data
  const NAMES = root.PingNames || (typeof require === "function" ? require("./names.js") : null);
  const cleanName = (s) => (NAMES ? NAMES.cleanName(s) : String(s || "").trim());
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
      return { kind: "test", at: ms(it.event_at), due: it.event_at, title: `${cleanName(it.company)} test`,
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

  function todos(items, day, inChat) {
    return (items || []).filter((it) => it.category === "todo" && it.due_at && dayOf(ms(it.due_at)) === day
      && (it.level !== "hidden" || /digest/.test(it.details?.hidden_because || "")))
      .map((it) => ({ kind: "todo", at: ms(it.due_at), due: it.due_at, title: cleanName(it.company) || "To do",
                      sub: `${clock(ms(it.due_at))} · ${String(it.title || "").replace(/^[^:]*:\s*/, "")}`,
                      target: inChat(it) ? { item: it.id } : { company: it.company } }));
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
      return { kind: "notice", at: ms(n.notice_time), title: many ? (n.subject || "Notice") : cleanName(n.company),
               sub: `${clock(ms(n.notice_time))} · ${many ? "several companies" : n.subject || "Notice"}`,
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
    const rows = [...ahead, ...news, ...(next ? [{ kind: "check", at: next, over: false, due: new Date(next).toISOString(),
      title: "Next ERP check", sub: clock(next), target: { check: true } }] : [])].sort((a, b) => a.at - b.at);
    const tTests = tests(items, tomorrow, inChat).length;
    const tDead = (roles || []).filter((r) => { const t = ms(r.effective_deadline || r.apply_end);
      return t > 0 && dayOf(t) === tomorrow && !r.applied && isMine(r); }).length + todos(items, tomorrow, inChat).length;
    const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
    return {
      rows: [...rows, ...done], ahead: ahead.length, nextCheck: next,
      empty: !timed.length && !news.length,
      emptyText: `Nothing scheduled today.${next ? ` Next check ${clock(next)}.` : ""}`,
      tomorrow: { tests: tTests, deadlines: tDead,
                  text: tTests || tDead ? `Tomorrow: ${[tTests ? plural(tTests, "test") : "", tDead ? plural(tDead, "deadline") : ""]
                    .filter(Boolean).join(", ")}` : "Tomorrow: nothing scheduled yet" },
    };
  }

  const api = { build, countdown, nextCheck, clock, dayOf, cleanName };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PingToday = api;
})(typeof window !== "undefined" ? window : globalThis);
