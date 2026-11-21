/* Ping dashboard. Plain JavaScript, no build step.
 *
 * Home screen is a chat with Ping: every "for you" item is a message from
 * Ping, your questions and Ping's answers sit in the same thread, and unread
 * messages are marked. Behind the Menu: all updates (with the three level
 * filters), company pages, profile, Check now.
 *
 * Two modes:
 *  - real: log in with Supabase; data is read straight from your own Supabase
 *    project with the publishable key, and Row Level Security only lets your
 *    login see it. "Check now" and AI answers go to two small server functions
 *    that hold the GitHub token and the Gemini key, so neither is ever in here.
 *  - demo: data from demo-data.json, no login; the thread is kept in this browser.
 */
(() => {
  "use strict";
  const CFG = window.PING_CONFIG || {};
  const TZ = "Asia/Kolkata";
  const $ = (s) => document.querySelector(s);
  const LEVELS = { always: "You applied", show: "Open for you", hidden: "Hidden" };
  const PAST = /deadline gone|already happened|older than 3 days|replaced by the 24h reminder|updated by a later message/;

  // ------------------------------------------------------------ tiny DOM helper (no innerHTML: notice text is untrusted)
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === false || v == null) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "href") el.setAttribute("href", safeUrl(v));
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const companyHref = (name) => `#co-${slug(name)}`;
  const safeUrl = (u) => (/^(https?:|#|mailto:|\?)/i.test(String(u)) ? String(u) : "#");
  const mount = (...nodes) => { const app = $("#app"); app.replaceChildren(...nodes); };
  const store = {  // per-browser conveniences only; every read/write may fail (private windows)
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } },
  };

  // ------------------------------------------------------------ dates (always IST)
  const dt = (v) => (v ? new Date(v) : null);
  const istDay = (d) => d.toLocaleDateString("en-CA", { timeZone: TZ });
  function when(v) {
    const d = dt(v);
    if (!d || isNaN(d)) return "";
    const days = (d - new Date()) / 86400000;
    const time = d.toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
    const wd = d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "short" });
    if (days >= 0 && days < 6) return `${wd} ${time}`;
    return `${wd} ${d.toLocaleDateString("en-GB", { timeZone: TZ, day: "2-digit", month: "short" })} ${time}`;
  }
  const clock = (v) => dt(v).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  function dayLabel(v) {
    const d = dt(v), today = istDay(new Date()), yest = istDay(new Date(Date.now() - 86400000));
    const k = istDay(d);
    if (k === today) return "Today";
    if (k === yest) return "Yesterday";
    return d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }
  const money = (n, cur) => (n == null ? "—" : `${Number(n).toLocaleString("en-IN")} ${cur || ""}`.trim());

  // ------------------------------------------------------------ data sources
  class DemoSource {
    constructor(data) { this.d = data; this.kind = "demo"; }
    async load() { return this.d; }
    async notice(noticeId) {
      const n = this.d.notices.find((x) => x.notice_id === noticeId);
      return { notice: n, check: n && this.d.pdf_checks.find((c) => c.notice_id === n.id) };
    }
    async saveProfile(p) { Object.assign(this.d.profile, p); }
    async markItem(id, patch) { Object.assign(this.d.items.find((i) => i.id === id) || {}, patch); }
    async correct(noticeKey, fix) {
      const it = this.d.items.find((i) => i.needs_review && i.details?.notice_key === noticeKey);
      if (it) { it.level = "hidden"; it.title = fix.ignore ? "Marked not relevant." : `Noted: it's about ${fix.company}.`; }
    }
    async checkNow() { return "Demo mode: this would start a real run on GitHub. Nothing was started."; }
    async ask(q) { return answerLocally(q, this.d); }
    async chat() { return store.get("ping-demo-chat", []); }
    async addChat(m) { store.set("ping-demo-chat", [...store.get("ping-demo-chat", []), m].slice(-500)); }
    async readAt() { return store.get("ping-demo-read", null); }
    async setReadAt(t) { store.set("ping-demo-read", t); }
  }

  const READ_ONLY = "Reviewer login is read-only: changes aren't saved.";
  class SupabaseSource {
    constructor(sb, reviewer = false) {
      this.sb = sb; this.kind = reviewer ? "reviewer" : "real"; this.reviewer = reviewer; this.chatOk = !reviewer;
    }
    async q(table, fn) {
      let query = this.sb.from(table).select("*");
      if (fn) query = fn(query);
      const { data, error } = await query;
      if (error) throw new Error(`${table}: ${error.message}`);
      return data;
    }
    async load() {
      const [items, roles, profile, runs] = await Promise.all([
        this.q("items", (q) => q.order("first_seen", { ascending: true }).limit(3000)),
        this.q("roles", (q) => q.limit(2000)),
        this.q("profile"),
        this.q("runs", (q) => q.order("started_at", { ascending: false }).limit(1)),
      ]);
      return { items, roles, profile: profile[0] || {}, runs };
    }
    async notice(noticeId) {
      const [n] = await this.q("notices", (q) => q.eq("notice_id", noticeId).limit(1));
      const checks = n ? await this.q("pdf_checks", (q) => q.eq("notice_id", n.id)) : [];
      return { notice: n, check: checks[0] };
    }
    async saveProfile(p) {
      if (this.reviewer) throw new Error(READ_ONLY);
      const { error } = await this.sb.from("profile").update({ ...p, updated_at: new Date().toISOString() })
        .eq("id", state.data.profile?.id ?? 1);
      if (error) throw new Error(error.message);
    }
    async markItem(id, patch) {
      if (this.reviewer) throw new Error(READ_ONLY);
      const { error } = await this.sb.from("items").update(patch).eq("id", id);
      if (error) throw new Error(error.message);
    }
    async correct(noticeKey, fix) {
      if (this.reviewer) throw new Error(READ_ONLY);
      const { error } = await this.sb.from("corrections").upsert({ notice_id: noticeKey, ...fix });
      if (error) throw new Error(error.message);
    }
    async fn(name, body) {
      const { data: { session } } = await this.sb.auth.getSession();
      const r = await fetch(`${CFG.supabaseUrl}/functions/v1/${name}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: CFG.supabaseKey, Authorization: `Bearer ${session?.access_token}` },
        body: JSON.stringify(body || {}),
      });
      const out = await r.json().catch(() => ({}));
      if (!r.ok) throw Object.assign(new Error(out.error || `HTTP ${r.status}`), { status: r.status });
      return out;
    }
    async checkNow() {
      if (this.reviewer) return "Reviewers can't start runs: Ping only logs in to the ERP for its owner.";
      await this.fn("check-now");
      return "Started a run. New messages arrive in about 2 minutes (reload to see them).";
    }
    async ask(q) {
      try { return (await this.fn("ask-ping", { question: q })).answer; }
      catch (e) {
        const why = e.status === 404 || /fetch/i.test(e.message) ? "the ask-ping server function isn't deployed or reachable"
          : e.status === 403 ? "your login isn't on the allowed list" : e.message;
        return answerLocally(q, state.data) + `\n\n(AI not reachable: ${why}. Answered with simple rules.)`;
      }
    }
    // The thread lives in the chat_messages table; if it isn't there yet (sql/chat.sql not run), this browser keeps it.
    async chat() {
      if (this.reviewer) return store.get("ping-reviewer-chat", []);
      const { data, error } = await this.sb.from("chat_messages").select("role,text,created_at").order("created_at").limit(1000);
      if (error) { this.chatOk = false; return store.get("ping-chat", []); }
      return data;
    }
    async addChat(m) {
      if (this.reviewer) { store.set("ping-reviewer-chat", [...store.get("ping-reviewer-chat", []), m].slice(-500)); return; }
      if (this.chatOk) {
        const { error } = await this.sb.from("chat_messages").insert({ role: m.role, text: m.text, created_at: m.created_at });
        if (!error) return;
        this.chatOk = false;
      }
      store.set("ping-chat", [...store.get("ping-chat", []), m].slice(-500));
    }
    async readAt() { return (!this.reviewer && state.data.profile?.chat_read_at) || store.get(this.reviewer ? "ping-reviewer-read" : "ping-read", null); }
    async setReadAt(t) {
      store.set(this.reviewer ? "ping-reviewer-read" : "ping-read", t);
      if (this.reviewer) return;
      await this.sb.from("profile").update({ chat_read_at: t }).eq("id", 1);
    }
  }

  // ------------------------------------------------------------ state + boot
  const state = { src: null, data: null, filter: "visible", companyQuery: "", chat: [], open: new Set() };

  async function boot() {
    const params = new URLSearchParams(location.search);
    const wantDemo = params.has("demo") || location.hash === "#demo";
    const hasBackend = CFG.supabaseUrl && CFG.supabaseKey && window.supabase;
    if (wantDemo || !hasBackend) return startDemo(!hasBackend && !wantDemo);
    const sb = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseKey);
    const { data: { session } } = await sb.auth.getSession();
    if (!session) return showLogin(sb);
    return startReal(sb);
  }

  async function startDemo(noBackend) {
    const r = await fetch("demo-data.json", { cache: "no-store" });
    state.src = new DemoSource(await r.json());
    $("#mode-badge").textContent = "Demo";
    $("#mode-badge").title = "Demo data, no login";
    $("#mode-badge").hidden = false;
    if (!noBackend) {
      const out = $("#sign-out");
      out.textContent = "Exit demo";
      out.hidden = false;
      out.onclick = () => { location.href = location.pathname; };
    }
    await afterStart();
  }

  async function startReal(sb) {
    const { data: ok, error } = await sb.rpc("is_ping_owner");
    let reviewer = false;
    if (!error && !ok) {
      const r = await sb.rpc("is_ping_reviewer");
      reviewer = !r.error && r.data === true;
    }
    if (error || (!ok && !reviewer)) {
      mount(h("div", { class: "login card" },
        h("h1", {}, "Not allowed"),
        h("p", {}, "This login isn't on Ping's list of allowed users. Ping adds the MAIL_ADDRESS from your " +
          "GitHub secrets on every run; to use another email, add it to the allowed_users table in Supabase."),
        error ? h("p", { class: "muted small" }, error.message) : null,
        h("button", { class: "btn", onclick: async () => { await sb.auth.signOut(); location.reload(); } }, "Sign out")));
      return;
    }
    state.src = new SupabaseSource(sb, reviewer);
    if (reviewer) {
      $("#mode-badge").textContent = "Reviewer";
      $("#mode-badge").title = "Anonymised demo data, read-only";
      $("#mode-badge").hidden = false;
    }
    const out = $("#sign-out");
    out.hidden = false;
    out.onclick = async () => { await sb.auth.signOut(); location.reload(); };
    await afterStart();
  }

  async function afterStart() {
    try {
      state.data = await state.src.load();
      state.chat = await state.src.chat();
      state.readAt = await state.src.readAt();
    } catch (e) { mount(h("div", { class: "card" }, h("h1", {}, "Couldn't load your data"), h("p", {}, e.message))); return; }
    setupMenu();
    showLastRun();
    window.addEventListener("hashchange", route);
    route();
  }

  function setupMenu() {
    const btn = $("#menu-btn"), menu = $("#menu");
    btn.hidden = false;
    const close = () => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); };
    btn.onclick = (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; btn.setAttribute("aria-expanded", String(!menu.hidden)); };
    document.addEventListener("click", (e) => { if (!menu.contains(e.target)) close(); });
    menu.addEventListener("click", (e) => { if (e.target.closest("a")) close(); });
    const check = $("#check-now");
    check.onclick = async () => {
      close();
      check.disabled = true;
      try { status(await state.src.checkNow()); }
      catch (e) { status(e.status === 404 ? "Check now isn't set up yet (see README)." : `Couldn't start a run: ${e.message}`); }
      finally { setTimeout(() => { check.disabled = false; }, 15000); }
    };
  }

  function showLastRun() {
    const run = (state.data.runs || [])[0];
    if (!run) return;
    $("#subtitle").textContent = `last checked ${when(run.finished_at)}${run.status === "ok" ? "" : " (problem)"}`;
    if (run.status !== "ok") status(`Last run: ${run.status}${run.problems?.length ? ` (${run.problems[0]})` : ""}`);
  }

  function status(text) { const el = $("#status"); el.textContent = text; el.hidden = !text; }

  function showLogin(sb) {
    const email = h("input", { type: "email", required: true, autocomplete: "username", placeholder: "you@example.com", id: "login-email" });
    const pw = h("input", { type: "password", required: true, autocomplete: "current-password", placeholder: "Password", id: "login-pw" });
    const msg = h("p", { class: "muted small" });
    mount(h("form", { class: "login card", onsubmit: async (e) => {
      e.preventDefault();
      msg.textContent = "Signing in…";
      const { error } = await sb.auth.signInWithPassword({ email: email.value.trim(), password: pw.value });
      if (error) { msg.textContent = error.message; return; }
      startReal(sb);
    } },
      h("h1", {}, "Sign in to Ping"),
      h("label", {}, "Email", email),
      h("label", {}, "Password", pw),
      h("button", { class: "btn" }, "Sign in"),
      msg,
      h("p", { class: "or" }, "or"),
      h("a", { class: "btn ghost center", href: "?demo=1" }, "Try the demo (no login)")));
  }

  // ------------------------------------------------------------ router
  // Plain "#name" links: #chat (home), #feed, #companies, #profile, #co-<company>
  function route() {
    const hash = location.hash.slice(1) || "chat";
    const page = hash.startsWith("co-") ? "companies" : hash;
    document.body.classList.toggle("chat-on", page === "chat");
    document.querySelectorAll("#menu a").forEach((a) => a.classList.toggle("on", a.dataset.route === page));
    if (hash.startsWith("co-")) {
      const name = [...byCompany().keys()].find((c) => slug(c) === hash.slice(3));
      return viewCompany(name || "");
    }
    if (hash === "feed") return viewFeed();
    if (hash === "companies") return viewCompanies();
    if (hash === "profile") return viewProfile();
    return viewChat();
  }

  // ------------------------------------------------------------ chat (home)
  const itemTime = (it) => it.first_seen || it.details?.notice_time || it.sort_at;
  const isPast = (it) => it.level === "hidden" && PAST.test(it.details?.hidden_because || "");
  // A past item stays in the chat only if Ping posted it while it still mattered. A role whose deadline
  // had already gone when Ping first saw it was never news, so it isn't a message.
  const wasLive = (it) => {
    const seen = dt(itemTime(it)), why = it.details?.hidden_because || "";
    if (!seen) return true;
    if (/deadline gone/.test(why) && it.due_at) return seen < dt(it.due_at);
    if (/already happened/.test(why) && it.event_at) return seen < +dt(it.event_at) + 12 * 3600000;
    if (/older than 3 days/.test(why) && it.sort_at) return seen < +dt(it.sort_at) + 3 * 86400000;
    if (/reminder/.test(why) && it.due_at) return seen < +dt(it.due_at) - 86400000;  // else the reminder alone says it
    return true;
  };
  const inChat = (it) => !it.dismissed && (it.level !== "hidden" || (isPast(it) && wasLive(it)));

  function threadEntries() {
    const items = state.data.items.filter(inChat).map((it) => ({ kind: "item", at: itemTime(it), it }));
    const talk = state.chat.map((m) => ({ kind: m.role, at: m.created_at, text: m.text }));
    return [...items, ...talk].filter((e) => e.at).sort((a, b) =>
      dt(a.at) - dt(b.at) || (a.kind === "item" && b.kind === "item" ? String(a.it.sort_at || "").localeCompare(String(b.it.sort_at || "")) : 0));
  }

  function viewChat() {
    const entries = threadEntries();
    // first visit (or the demo): don't call two weeks of history "unread", only the last day
    const lastAt = entries.length ? dt(entries[entries.length - 1].at) : null;
    const readAt = state.readAt ? dt(state.readAt) : lastAt && new Date(lastAt - 86400000);
    const unread = entries.filter((e) => e.kind === "item" && (!readAt || dt(e.at) > readAt));
    const inner = h("div", { class: "thread-inner" });
    let lastDay = null, divider = null;
    if (!entries.length) inner.append(h("div", { class: "day" }, "No messages yet. Ping posts here when something is about you."));
    for (const e of entries) {
      const day = dayLabel(e.at);
      if (day !== lastDay) { inner.append(h("div", { class: "day" }, day)); lastDay = day; }
      if (!divider && unread.length && e === unread[0]) {
        divider = h("div", { class: "unread", id: "unread" }, `${unread.length} unread message${unread.length > 1 ? "s" : ""}`);
        inner.append(divider);
      }
      inner.append(e.kind === "item" ? itemBubble(e.it, e.at) : textBubble(e.kind, e.text, e.at));
    }
    const thread = h("div", { class: "thread", id: "thread" }, inner);
    const input = h("input", { id: "ask-input", autocomplete: "off", maxlength: "300", enterkeyhint: "send",
      placeholder: "Ask Ping: what's due tomorrow?", "aria-label": "Message Ping" });
    const form = h("form", { onsubmit: (ev) => { ev.preventDefault(); send(input, inner, thread); } }, input, h("button", { class: "btn" }, "Send"));
    mount(thread, h("div", { class: "composer" }, form));
    // open at the first unread message, otherwise at the bottom (the latest thing that happened)
    requestAnimationFrame(() => {
      if (divider) divider.scrollIntoView({ block: "start" });
      else thread.scrollTop = thread.scrollHeight;
    });
    const latest = entries.length ? entries[entries.length - 1].at : null;
    if (latest && (!readAt || dt(latest) > readAt)) {
      state.readAt = new Date(Math.max(dt(latest), Date.now())).toISOString();
      state.src.setReadAt(state.readAt).catch(() => {});
    }
  }

  function textBubble(role, text, at) {
    return h("div", { class: `msg ${role === "me" ? "me" : "ping"}` }, h("span", { class: "text" }, text),
      h("span", { class: "time" }, clock(at)));
  }

  function itemBubble(it, at) {
    const cls = it.needs_review ? "review" : it.level;
    const past = isPast(it);
    const why = it.details?.hidden_because || "";
    const pastLabel = /updated/.test(why) ? "Updated below" : /reminder/.test(why) ? "Replaced by reminder"
      : /deadline/.test(why) ? "Deadline passed" : "Over";
    const kicker = past ? pastLabel : it.needs_review ? "Question" : LEVELS[it.level];
    const open = state.open.has(it.id);
    const bubble = h("div", { class: `msg ping item ${cls}${past ? " past" : ""}${it.done ? " done" : ""}`, role: "button",
      tabindex: "0", "aria-expanded": String(open) },
      h("div", { class: `kicker ${past ? "hidden" : cls}` }, kicker),
      h("span", { class: "text" }, it.title),
      h("span", { class: "time" }, clock(at)));
    const toggle = (ev) => {
      if (ev.target.closest("a, button, .more")) return;
      state.open.has(it.id) ? state.open.delete(it.id) : state.open.add(it.id);
      bubble.replaceWith(itemBubble(it, at));
    };
    bubble.addEventListener("click", toggle);
    bubble.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(ev); } });
    if (open) bubble.append(itemDetails(it));
    return bubble;
  }

  function itemDetails(it) {
    const d = it.details || {};
    const due = it.due_at || it.event_at;
    const lines = [];
    if (due) lines.push(h("div", {}, h("strong", {}, it.due_at ? "Due: " : "When: "), when(due)));
    if (it.company) lines.push(h("div", {}, h("strong", {}, "Company: "), h("a", { href: companyHref(it.company) }, it.company)));
    if (d.venue) lines.push(h("div", {}, h("strong", {}, "Venue: "), d.venue));
    if (d.pdf?.status === "yes" && d.pdf.my_row) lines.push(h("div", {}, h("strong", {}, "Your row: "),
      (d.pdf.header ? d.pdf.header.map((x, i) => `${x}: ${d.pdf.my_row[i] ?? ""}`) : d.pdf.my_row).join(" · ")));
    if ((d.reasons || []).length) lines.push(h("div", {}, h("strong", {}, "Eligibility: "), [...d.reasons, ...(d.flags || [])].join("; ")));
    if (d.deadline_source && d.deadline_source !== "companies list") lines.push(h("div", { class: "muted" }, `Deadline from ${d.deadline_source}`));
    if ((d.contacts || []).length) lines.push(h("div", {}, h("strong", {}, "Contacts: "), d.contacts.map((c) => `${c.name} ${c.phone}`).join(", ")));
    if ((d.changes || []).length) lines.push(h("div", {}, h("strong", {}, "What changed: "), d.changes.join("; ")));
    if (d.previous_title) lines.push(h("div", { class: "muted" }, `Before: ${d.previous_title}`));
    if ((d.merged || []).length) lines.push(h("div", { class: "muted" },
      `Also posted ${d.merged.length} more time${d.merged.length > 1 ? "s" : ""} (merged here, not sent again)`));
    if (d.hidden_because) lines.push(h("div", { class: "muted" }, `Not shown any more: ${d.hidden_because}`));
    const links = [
      it.notice_id ? h("button", { type: "button", onclick: () => openNotice(it.notice_id) }, "Open notice") : null,
      it.notice_id && it.pdf_status ? pdfLink(it) : null,
      ...(d.todo?.link ? [h("a", { href: d.todo.link, target: "_blank", rel: "noopener" }, "Open form")] : []),
      ...mailLinks(it).map((u, k) => h("a", { href: u, target: "_blank", rel: "noopener" }, k ? "Link 2" : "Link from your mail")),
      !isPast(it) ? h("button", { type: "button", onclick: () => toggleDone(it) }, it.done ? "Undo done" : "Mark done") : null,
    ];
    const more = h("div", { class: "more" }, lines, h("div", { class: "links" }, links));
    if (it.needs_review && it.level !== "hidden") {
      more.append(h("div", { class: "links" }, "It's about:",
        (d.candidates || []).map((c) => h("button", { type: "button", onclick: () => fix(it, { company: c }) }, c)),
        h("button", { type: "button", onclick: () => fix(it, { ignore: true }) }, "none of these")));
    }
    return more;
  }

  async function send(input, inner, thread) {
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    const mine = { role: "me", text: q, created_at: new Date().toISOString() };
    state.chat.push(mine);
    inner.append(textBubble("me", q, mine.created_at));
    const wait = h("div", { class: "msg ping typing" }, "Ping is typing…");
    inner.append(wait);
    thread.scrollTop = thread.scrollHeight;
    state.src.addChat(mine).catch(() => {});
    let answer;
    try { answer = await state.src.ask(q); } catch (e) { answer = e.message; }
    const reply = { role: "ping", text: answer || "I couldn't come up with an answer.", created_at: new Date().toISOString() };
    state.chat.push(reply);
    wait.replaceWith(textBubble("ping", reply.text, reply.created_at));
    thread.scrollTop = thread.scrollHeight;
    state.src.addChat(reply).catch(() => {});
    state.readAt = reply.created_at;
    state.src.setReadAt(state.readAt).catch(() => {});
  }

  // ------------------------------------------------------------ all updates (list with the three level filters)
  const itemDue = (it) => it.due_at || it.event_at;
  function sortNewest(a, b) { return String(itemTime(b) || "").localeCompare(String(itemTime(a) || "")); }

  function viewFeed() {
    const items = state.data.items.filter((i) => !i.dismissed);
    const counts = { always: 0, show: 0, hidden: 0 };
    items.forEach((i) => { counts[i.level] = (counts[i.level] || 0) + 1; });
    const filters = [["visible", "For you", counts.always + counts.show], ["always", LEVELS.always, counts.always],
                     ["show", LEVELS.show, counts.show], ["hidden", LEVELS.hidden, counts.hidden]];
    const shown = items.filter((i) => state.filter === "visible" ? i.level !== "hidden" : i.level === state.filter).sort(sortNewest);
    mount(
      h("h1", {}, "All updates"),
      h("p", { class: "muted small" }, "Newest first. “You applied” is anything about a role you applied to; " +
        "“Open for you” is roles you can still apply to; “Hidden” is kept but not about you (or already past)."),
      h("div", { class: "filters" }, filters.map(([key, label, n]) =>
        h("button", { class: "chip" + (state.filter === key ? " on" : ""), onclick: () => { state.filter = key; viewFeed(); } },
          label, h("span", { class: "n" }, n)))),
      shown.length ? h("div", { class: "list" }, shown.map(itemCard)) : h("p", { class: "muted" }, "Nothing here right now."));
  }

  function itemCard(it) {
    const due = itemDue(it);
    const soon = due && dt(due) - new Date() < 86400000 && dt(due) > new Date();
    const cls = it.needs_review ? "review" : it.level;
    const meta = [
      h("span", { class: `tag ${cls}` }, it.needs_review ? "Question" : LEVELS[it.level]),
      due ? h("span", { class: "due" + (soon ? " soon" : "") }, (it.due_at ? "Due " : "On ") + when(due)) : null,
      it.company ? h("a", { href: companyHref(it.company) }, it.company) : null,
      it.notice_id ? h("button", { onclick: () => openNotice(it.notice_id) }, "Open notice") : null,
      it.notice_id && it.pdf_status ? pdfLink(it) : null,
      ...mailLinks(it).map((u, k) => h("a", { href: u, target: "_blank", rel: "noopener" }, k ? "Link 2" : "Link from your mail")),
      ...(it.details?.todo?.link ? [h("a", { href: it.details.todo.link, target: "_blank", rel: "noopener" }, "Open form")] : []),
      it.level !== "hidden" ? h("button", { onclick: () => toggleDone(it) }, it.done ? "Undo done" : "Done") : null,
    ];
    const card = h("div", { class: `item ${cls}${it.done ? " done" : ""}` }, h("div", { class: "title" }, it.title), h("div", { class: "meta" }, meta));
    if (it.needs_review && it.level !== "hidden") {
      card.append(h("div", { class: "meta" }, "It's about:",
        (it.details?.candidates || []).map((c) => h("button", { onclick: () => fix(it, { company: c }) }, c)),
        h("button", { onclick: () => fix(it, { ignore: true }) }, "none of these / not relevant")));
    }
    return card;
  }

  function mailLinks(it) {
    const d = it.details || {};
    const links = d.mail_links?.length ? d.mail_links : it.category === "email" ? d.links || [] : [];
    return links.slice(0, 2);
  }

  function pdfLink(it) {
    const year = it.details?.notice_year;
    const href = year ? `https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=${encodeURIComponent(year)}&id=${it.notice_id}`
                      : "https://erp.iitkgp.ac.in/";
    return h("a", { href, target: "_blank", rel: "noopener", title: "Opens on the ERP; you need to be logged in to the ERP in this browser" },
      `PDF (${it.pdf_status === "yes" ? "you're in it" : it.pdf_status === "no" ? "not in it" : "unread"})`);
  }

  async function toggleDone(it) {
    it.done = !it.done;
    try { await state.src.markItem(it.id, { done: it.done }); } catch (e) { status(e.message); }
    route();
  }

  async function fix(it, f) {
    try {
      await state.src.correct(it.details?.notice_key, f);
      status(state.src.kind === "demo" ? "Saved (demo only)." : "Saved. The next run will use your answer.");
      if (state.src.kind !== "demo") it.level = "hidden";
    } catch (e) { status(e.message); }
    route();
  }

  async function openNotice(noticeId) {
    const body = $("#modal-body");
    body.replaceChildren(h("p", { class: "muted" }, "Loading…"));
    $("#modal").showModal();
    let res;
    try { res = await state.src.notice(noticeId); } catch (e) { body.replaceChildren(h("p", {}, e.message)); return; }
    const n = res.notice;
    if (!n) { body.replaceChildren(h("p", {}, "This notice isn't stored.")); return; }
    const c = res.check;
    const a = n.analysis || {};
    body.replaceChildren(
      h("h2", {}, `${n.subject} · ${n.company}`),
      h("p", { class: "muted small" }, `Posted ${when(n.notice_time)} · notice ${n.notice_id}`),
      h("pre", { class: "notice" }, n.text || n.preview || ""),
      c ? h("div", { class: "card" },
        h("strong", {}, c.status === "yes" ? `You're in the attachment (matched by ${c.matched_by})` :
                         c.status === "no" ? "You're not in the attachment" : "The attachment couldn't be read"),
        c.my_row ? h("div", { class: "table-wrap" }, h("table", {},
          c.header ? h("tr", {}, c.header.map((x) => h("th", {}, x))) : null,
          h("tr", {}, c.my_row.map((x) => h("td", {}, x))))) : null,
        c.error ? h("p", { class: "muted small" }, c.error) : null) : null,
      n.has_attachment ? h("p", {}, h("a", { target: "_blank", rel: "noopener",
        href: `https://erp.iitkgp.ac.in/TrainingPlacementSSO/AdmFilePDF.htm?type=NOTICE&year=${encodeURIComponent(n.year)}&id=${n.notice_id}` },
        "Open the PDF on the ERP"), h("span", { class: "muted small" }, " (works when you're logged in to the ERP in this browser)")) : null,
      (a.contacts || []).length ? h("p", { class: "small" }, "Contacts: ", a.contacts.map((x) => `${x.name} ${x.phone}`).join(", ")) : null,
      (a.deadlines || []).length ? h("p", { class: "small muted" }, "Dates found: ", a.deadlines.map((d) => `${when(d.at)} (“${d.text}”)`).join("; ")) : null);
  }

  // ------------------------------------------------------------ companies
  function byCompany() {
    const map = new Map();
    for (const r of state.data.roles) {
      if (!map.has(r.company)) map.set(r.company, []);
      map.get(r.company).push(r);
    }
    return map;
  }
  const deadlineOf = (r) => r.effective_deadline || r.apply_end;

  function viewCompanies() {
    const map = byCompany();
    const input = h("input", { class: "search", id: "company-search", placeholder: "Search companies", value: state.companyQuery,
      oninput: (e) => { state.companyQuery = e.target.value; draw(); } });
    const grid = h("div", { class: "grid" });
    function draw() {
      const q = state.companyQuery.toLowerCase();
      const now = new Date();
      grid.replaceChildren(...[...map.entries()].filter(([c]) => c.toLowerCase().includes(q)).sort(([a], [b]) => a.localeCompare(b))
        .map(([c, roles]) => {
          const applied = roles.filter((r) => r.applied).length;
          const open = roles.filter((r) => !r.applied && dt(deadlineOf(r)) > now && r.eligible !== false);
          return h("a", { class: "card company-link", href: companyHref(c) }, h("strong", {}, c),
            h("div", { class: "small muted" }, `${roles.length} role${roles.length > 1 ? "s" : ""}`,
              applied ? ` · applied to ${applied}` : "", open.length ? ` · ${open.length} open for you` : ""));
        }));
    }
    draw();
    mount(h("h1", {}, "Companies"), h("p", { class: "muted small" }, `${map.size} companies, ${state.data.roles.length} roles`), input,
      h("div", { style: "height:10px" }), grid);
  }

  function viewCompany(name) {
    const roles = byCompany().get(name) || [];
    const items = state.data.items.filter((i) => i.company === name && i.level !== "hidden").sort(sortNewest);
    mount(
      h("p", {}, h("a", { href: "#companies" }, "← All companies")),
      h("h1", {}, name),
      roles.length ? h("div", { class: "table-wrap" }, h("table", {},
        h("tr", {}, ["Role", "Applied", "Deadline", "Pay (CTC)", "Eligible", "Details"].map((x) => h("th", {}, x))),
        roles.map((r) => {
          const e = r.eligibility || {};
          return h("tr", {},
            h("td", {}, r.designation),
            h("td", {}, r.applied ? h("span", { class: "yes" }, "Yes") : "No"),
            h("td", {}, when(deadlineOf(r)) || "—", r.deadline_source && r.deadline_source !== "companies list"
              ? h("div", { class: "small muted" }, `from ${r.deadline_source}`) : null),
            h("td", {}, money(r.ctc, r.currency)),
            h("td", {}, r.eligible === true ? h("span", { class: "yes" }, "Yes") : r.eligible === false ? h("span", { class: "no" }, "No") : "Not sure",
              h("div", { class: "small muted" }, [...(e.reasons || []), ...(e.flags || [])].join("; "))),
            h("td", { class: "small" },
              r.cgpa_cutoff ? `CGPA ≥ ${r.cgpa_cutoff}. ` : "No CGPA cut-off. ",
              r.backlog_rule ? `Backlogs: ${r.backlog_rule.replace(/\.+$/, "")}. ` : "",
              r.has_written_test === true ? "Written test. " : r.has_written_test === false ? "No written test. " : "",
              (r.allowed || []).length ? `${new Set(r.allowed.map((a) => a.department)).size} departments allowed.` : ""));
        }))) : h("p", { class: "muted" }, "No roles for this company in the companies list."),
      h("h2", {}, "Updates"),
      items.length ? h("div", { class: "list" }, items.map(itemCard)) : h("p", { class: "muted" }, "Nothing current."));
  }

  // ------------------------------------------------------------ profile
  function viewProfile() {
    const p = state.data.profile || {};
    const depts = new Set(), degrees = new Set();
    state.data.roles.forEach((r) => (r.allowed || []).forEach((a) => { depts.add(a.department); degrees.add(a.degree); }));
    const field = (name, label, value, attrs = {}, hint) => h("label", {}, label, hint ? h("span", { class: "hint" }, hint) : null,
      h("input", { name, id: `pf-${name}`, value: value ?? "", ...attrs }));
    const cv = p.cv_names || [];
    const lists = (v) => (v || []).join("\n");
    const form = h("form", { class: "profile card", onsubmit: save },
      h("div", { class: "row2" },
        field("roll", "Roll number", p.roll, {}, "Leave empty to use your ERP user id"),
        field("name", "Name", p.name, {}, "Only used when a PDF has names but no roll numbers")),
      h("div", { class: "row2" },
        field("department", "Department", p.department, { list: "dl-depts" }, "As the ERP writes it"),
        field("degree", "Degree", p.degree, { list: "dl-degrees" })),
      h("div", { class: "row2" },
        field("cgpa", "CGPA", p.cgpa, { type: "number", step: "0.01", min: "0", max: "10" }),
        h("label", { class: "check" }, h("input", { type: "checkbox", name: "active_backlogs", id: "pf-backlogs", checked: !!p.active_backlogs }), "I have active backlogs")),
      h("div", { class: "row3" }, [0, 1, 2].map((i) => field(`cv${i}`, `CV ${i + 1} name`, cv[i]))),
      h("div", { class: "row2" },
        h("label", {}, "Interested companies", h("span", { class: "hint" }, "One per line"),
          h("textarea", { name: "interested_companies", id: "pf-interested", rows: 5 }, lists(p.interested_companies))),
        h("label", {}, "Not interested", h("span", { class: "hint" }, "One per line. Their roles are hidden."),
          h("textarea", { name: "not_interested_companies", id: "pf-not-interested", rows: 5 }, lists(p.not_interested_companies)))),
      h("div", {}, h("button", { class: "btn" }, "Save profile"),
        h("span", { class: "muted small", id: "saved" }, "  Changes apply on the next run (or Menu > Check now).")),
      h("datalist", { id: "dl-depts" }, [...depts].sort().map((d) => h("option", { value: d }))),
      h("datalist", { id: "dl-degrees" }, [...degrees].sort().map((d) => h("option", { value: d }))));

    async function save(e) {
      e.preventDefault();
      const f = new FormData(form);
      const split = (k) => String(f.get(k) || "").split(/\n|,/).map((s) => s.trim()).filter(Boolean);
      const cgpa = String(f.get("cgpa") || "").trim();
      const patch = {
        roll: String(f.get("roll") || "").trim() || null, name: String(f.get("name") || "").trim() || null,
        department: String(f.get("department") || "").trim() || null, degree: String(f.get("degree") || "").trim() || null,
        cgpa: cgpa ? Number(cgpa) : null, active_backlogs: f.get("active_backlogs") === "on",
        cv_names: [0, 1, 2].map((i) => String(f.get(`cv${i}`) || "").trim()).filter(Boolean),
        interested_companies: split("interested_companies"), not_interested_companies: split("not_interested_companies"),
      };
      try {
        await state.src.saveProfile(patch);
        Object.assign(state.data.profile, patch);
        $("#saved").textContent = state.src.kind === "demo" ? "  Saved for this visit (demo)." : "  Saved. Applies on the next run.";
      } catch (err) { $("#saved").textContent = `  ${err.message}`; }
    }
    mount(h("h1", {}, "Profile"), h("p", { class: "muted small" },
      "Used to decide what you're eligible for. Whether you applied comes from the ERP's companies list, not from here."), form);
  }

  // ------------------------------------------------------------ answers without AI
  // Used in demo mode and whenever the AI helper isn't reachable.
  function answerLocally(question, data) {
    const q = question.toLowerCase();
    const now = new Date();
    const live = data.items.filter((i) => i.level !== "hidden" && !i.dismissed);
    const companies = [...new Set(data.roles.map((r) => r.company))];
    const words = (s) => s.toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 2);
    const STOP = new Set(["private", "limited", "india", "pvt", "ltd", "inc", "the", "and", "group", "company", "services", "technologies"]);
    const mentioned = companies.filter((c) => words(c).some((w) => !STOP.has(w) && new RegExp(`\\b${w}\\b`).test(q)));
    const rolesOf = (c) => data.roles.filter((r) => r.company === c);

    if (mentioned.length && /appl/.test(q)) {
      return mentioned.map((c) => {
        const yes = rolesOf(c).filter((r) => r.applied);
        return yes.length ? `Yes, you applied to ${c}: ${yes.map((r) => r.designation).join(", ")}.`
          : `No, you haven't applied to ${c}. Roles: ${rolesOf(c).map((r) => `${r.designation} (closes ${when(deadlineOf(r))})`).join(", ")}.`;
      }).join("\n");
    }
    if (mentioned.length && /ctc|pay|salary|package|stipend|lpa|money/.test(q)) {
      return mentioned.map((c) => rolesOf(c).map((r) => `${c} ${r.designation}: CTC ${money(r.ctc, r.currency)}`).join("\n")).join("\n");
    }
    if (mentioned.length && /eligib/.test(q)) {
      return mentioned.map((c) => rolesOf(c).map((r) =>
        `${c} ${r.designation}: ${r.eligible === true ? "yes" : r.eligible === false ? "no" : "not sure"}` +
        ` (${[...(r.eligibility?.reasons || []), ...(r.eligibility?.flags || [])].join("; ")})`).join("\n")).join("\n");
    }
    if (mentioned.length && /room|venue|where|slot/.test(q)) {
      return mentioned.map((c) => {
        const hits = data.items.filter((i) => i.company === c && ["shortlist", "test", "result"].includes(i.category));
        const mine = hits.find((i) => i.pdf_status === "yes" || i.details?.pdf?.status === "yes");
        if (mine) {
          const p = mine.details?.pdf || {};
          const row = p.my_row && p.header ? p.header.map((x, i) => `${x}: ${p.my_row[i] ?? ""}`).join(" · ") : "";
          return `${mine.title}${row ? `\nYour row: ${row}` : ""}`;
        }
        if (hits.some((i) => i.pdf_status === "no")) return `You're not on the ${c} list, so there's no room for you.`;
        return `I haven't seen a room list for ${c} yet.`;
      }).join("\n");
    }
    let from = null, to = null, label = "";
    const offset = now - new Date(now.toLocaleString("en-US", { timeZone: TZ }));
    const istMidnight = (d) => { const x = new Date(d.toLocaleString("en-US", { timeZone: TZ })); x.setHours(0, 0, 0, 0); return new Date(x.getTime() + offset); };
    if (/tomorrow/.test(q)) { from = new Date(istMidnight(now).getTime() + 86400000); to = new Date(from.getTime() + 86400000); label = "tomorrow"; }
    else if (/today|tonight/.test(q)) { from = now; to = new Date(istMidnight(now).getTime() + 86400000); label = "today"; }
    else if (/week|7 days/.test(q)) { from = now; to = new Date(now.getTime() + 7 * 86400000); label = "in the next 7 days"; }
    else if (/due|deadline|next|upcoming|soon/.test(q)) { from = now; to = new Date(now.getTime() + 3 * 86400000); label = "in the next 3 days"; }
    if (from) {
      const hits = live.filter((i) => { const d = dt(i.due_at || i.event_at); return d && d >= from && d < to; })
                       .sort((a, b) => dt(a.due_at || a.event_at) - dt(b.due_at || b.event_at));
      return hits.length ? `Due or happening ${label}:\n` + hits.map((i) => `• ${i.title}`).join("\n") : `Nothing due or scheduled ${label}.`;
    }
    if (/shortlist|test|room/.test(q)) {
      const hits = live.filter((i) => ["shortlist", "test", "result"].includes(i.category));
      return hits.length ? hits.map((i) => `• ${i.title}`).join("\n") : "No current shortlists or tests for you.";
    }
    if (mentioned.length) return mentioned.map((c) => live.filter((i) => i.company === c).map((i) => `• ${i.title}`).join("\n")
      || `Nothing current about ${c}.`).join("\n");
    const top = live.filter((i) => i.level === "always").slice(0, 3);
    return "I can answer things like “what's due tomorrow?”, “did I apply to X?”, “which room for the X test?”, " +
      "“what's the CTC at X?”." + (top.length ? "\n\nMost important right now:\n" + top.map((i) => `• ${i.title}`).join("\n") : "");
  }

  boot().catch((e) => mount(h("div", { class: "card" }, h("h1", {}, "Something went wrong"), h("p", {}, e.message))));
})();
