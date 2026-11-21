/* Ping dashboard. Plain JavaScript, no build step.
 *
 * Home screen is a chat with Ping: every "for you" item is a message from
 * Ping, your questions and Ping's answers sit in the same thread, and unread
 * messages are marked. A bottom bar (phones) or a left rail (desktop) leads to
 * Companies (every role, filters, a sheet per role) and Profile (cards edited in
 * place; Account has Check now, All updates, the theme and sign out).
 * Look and feel: docs/DESIGN.md.
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
  // every page but the chat: one centred column that scrolls (the chat scrolls its own thread)
  const mountPage = (...nodes) => { mount(h("div", { class: "page" }, ...nodes)); $("#app").scrollTop = 0; };
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
    // always with the date, same as Ping's messages ("Sat 21 Nov 20:00")
    const time = d.toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
    const wd = d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "short" });
    return `${wd} ${d.toLocaleDateString("en-GB", { timeZone: TZ, day: "2-digit", month: "short" })} ${time}`;
  }
  const clock = (v) => dt(v).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  function dayLabel(v) {
    const d = dt(v), today = istDay(nowDate()), yest = istDay(new Date(nowDate() - 86400000));
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

  const READ_ONLY = "The demo is read-only: changes aren't saved.";
  const DEMO_CHIP = "Demo \u2014 sample data, read-only";
  // what a demo visitor may set for their own session (session_prefs); the demo student's details stay fixed
  const DEMO_OWN = ["targets", "reminder_hours", "list_other_roles", "feed_mode", "check_every_minutes", "check_from", "check_to"];
  // One class for both logins: the owner (real rows) and a one-click demo session (an anonymous sign-in that the
  // database only lets read the anonymised demo rows and its own chat).
  class SupabaseSource {
    constructor(sb, demo = false) {
      this.sb = sb; this.kind = demo ? "demo" : "real"; this.demo = demo; this.chatOk = true;
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
      // the demo is a snapshot: its profile row carries the time it was taken
      return { items, roles, profile: profile[0] || {}, runs,
               generated_at: this.demo ? profile[0]?.updated_at : undefined };
    }
    async notice(noticeId) {
      const [n] = await this.q("notices", (q) => q.eq("notice_id", noticeId).limit(1));
      const checks = n ? await this.q("pdf_checks", (q) => q.eq("notice_id", n.id)) : [];
      return { notice: n, check: checks[0] };
    }
    async saveProfile(p) {
      if (this.demo) {
        // a demo visitor may set what they're looking for: their own session only (session_prefs), never the
        // owner's profile; the rest of the demo profile is read-only
        const { data: { user } } = await this.sb.auth.getUser();
        const own = Object.fromEntries(Object.entries(p).filter(([k]) => DEMO_OWN.includes(k)));
        if (!Object.keys(own).length) throw new Error(READ_ONLY);
        const { error } = await this.sb.from("session_prefs").upsert({ owner_id: user.id, ...own, updated_at: new Date().toISOString() });
        if (error) throw new Error(error.message);
        state.sessionPrefs = { ...(state.sessionPrefs || {}), ...own };
        return "Saved for this demo session only.";
      }
      const { error } = await this.sb.from("profile").update({ ...p, updated_at: new Date().toISOString() })
        .eq("id", state.data.profile?.id ?? 1);
      if (error) throw new Error(error.message);
    }
    // onboarding answers: the owner's profile row, or a demo session's own row (never the owner's profile)
    async saveOnboarding(save) {
      if (!Object.keys(save).length) return;
      if (this.demo) {
        const { data: { user } } = await this.sb.auth.getUser();
        const { error } = await this.sb.from("session_prefs").upsert({ owner_id: user.id, ...save, updated_at: new Date().toISOString() });
        if (error) throw new Error(error.message);
        return;
      }
      const { error } = await this.sb.from("profile").update(save).eq("id", 1);
      if (error) throw new Error(error.message);
    }
    async sessionPrefs() {
      if (!this.demo) return null;
      const { data } = await this.sb.from("session_prefs").select("*").limit(1);
      return (data || [])[0] || {};
    }
    async latestRun() {
      const { data } = await this.sb.from("runs").select("started_at,finished_at,status").order("started_at", { ascending: false }).limit(1);
      return (data || [])[0] || null;
    }
    // "For you" marks for the current targets, from the server's cache (the page never sees the cache itself)
    async marks() {
      const out = await this.fn("ask-ping", { marks: true });
      return { prefs: out.prefs || {}, marks: new Map(Object.entries(out.marks || {})) };
    }
    async markItem(id, patch) {
      if (this.demo) throw new Error(READ_ONLY);
      const { error } = await this.sb.from("items").update(patch).eq("id", id);
      if (error) throw new Error(error.message);
    }
    async correct(noticeKey, fix) {
      if (this.demo) throw new Error(READ_ONLY);
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
      if (this.demo) return "The demo can't start a check: Ping only logs in to the ERP for its owner.";
      await this.fn("check-now");
      return "Started a run. New messages arrive in about 2 minutes (reload to see them).";
    }
    async ask(q) {
      // the demo is a snapshot: "tomorrow" is the day after it, as everywhere else on the page
      const asOf = this.demo && state.asOf ? new Date(state.asOf).toISOString() : undefined;
      try {
        const out = await this.fn("ask-ping", { question: q, as_of: asOf });
        if (out.prefs_changed) state.prefsChanged = true;
        return out.answer;
      }
      catch (e) {
        if (e.status === 429) return `${e.message}\n\nMeanwhile, with simple rules: ${answerLocally(q, state.data)}`;
        const why = e.status === 404 || /fetch/i.test(e.message) ? "the ask-ping server function isn't deployed or reachable"
          : e.status === 403 ? "your login isn't on the allowed list" : e.message;
        return answerLocally(q, state.data) + `\n\n(AI not reachable: ${why}. Answered with simple rules.)`;
      }
    }
    // The thread lives in the chat_messages table; if it isn't there yet (sql/chat.sql not run), this browser keeps it.
    async chat() {
      const { data, error } = await this.sb.from("chat_messages").select("role,text,created_at").order("created_at").limit(1000);
      if (error) { this.chatOk = false; return store.get("ping-chat", []); }
      return data;
    }
    async addChat(m) {
      if (this.chatOk) {
        // a demo session's messages are demo rows: only that session can read them back
        const row = { role: m.role, text: m.text, created_at: m.created_at, ...(this.demo ? { is_sample: true } : {}) };
        const { error } = await this.sb.from("chat_messages").insert(row);
        if (!error) return;
        this.chatOk = false;
      }
      store.set("ping-chat", [...store.get("ping-chat", []), m].slice(-500));
    }
    async readAt() { return (!this.demo && state.data.profile?.chat_read_at) || store.get(this.demo ? "ping-demo-session-read" : "ping-read", null); }
    async setReadAt(t) {
      store.set(this.demo ? "ping-demo-session-read" : "ping-read", t);
      if (this.demo) return;
      await this.sb.from("profile").update({ chat_read_at: t }).eq("id", 1);
    }
  }

  // ------------------------------------------------------------ state + boot
  const state = { src: null, data: null, filter: "visible", companyQuery: "", chat: [], open: new Set(), asOf: null };
  // The demo shows a snapshot: "now" is when it was taken, so its deadlines don't all read "passed" a week later.
  const nowDate = () => new Date(state.asOf || Date.now());

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
    $("#mode-badge").replaceChildren("Demo", h("span", { class: "long" }, DEMO_CHIP.replace(/^Demo/, "")));
    $("#mode-badge").title = "Anonymised snapshot of a real run, no login";
    $("#mode-badge").hidden = false;
    if (!noBackend) state.exit = { label: "Exit demo", run: () => { location.href = location.pathname; } };
    await afterStart();
  }

  async function startReal(sb) {
    const { data: ok, error } = await sb.rpc("is_ping_owner");
    let demo = false;
    if (!error && !ok) {
      const r = await sb.rpc("is_ping_demo");
      demo = !r.error && r.data === true;
    }
    if (error || (!ok && !demo)) {
      mountPage(h("div", { class: "login card" },
        h("h1", {}, "Not allowed"),
        h("p", {}, "This login isn't on Ping's list of allowed users. Ping adds the MAIL_ADDRESS from your " +
          "GitHub secrets on every run; to use another email, add it to the allowed_users table in Supabase."),
        error ? h("p", { class: "muted small" }, error.message) : null,
        h("button", { class: "btn", onclick: async () => { await sb.auth.signOut(); location.reload(); } }, "Sign out")));
      return;
    }
    state.src = new SupabaseSource(sb, demo);
    if (demo) {
      // "Demo — sample data, read-only"; the second part is hidden on narrow phones
      $("#mode-badge").replaceChildren("Demo", h("span", { class: "long" }, DEMO_CHIP.replace(/^Demo/, "")));
      $("#mode-badge").title = "Anonymised snapshot of a real run: real companies, a made-up student";
      $("#mode-badge").hidden = false;
    }
    state.exit = { label: demo ? "Exit demo" : "Sign out", run: async () => { await sb.auth.signOut(); location.reload(); } };
    await afterStart();
    // split the lists by the current marks once they arrive, but never while a question is waiting for its answer
    loadMarks().then(() => { if (state.marks?.size && (location.hash || "#chat") === "#chat" && !state.sending && !state.onb) route(); });
  }

  async function afterStart() {
    try {
      state.data = await state.src.load();
      state.chat = await state.src.chat();
      state.readAt = await state.src.readAt();
      if (state.src.kind !== "real") {
        const run = (state.data.runs || [])[0] || {};
        state.asOf = dt(state.data.generated_at || run.finished_at || run.started_at)?.getTime() || null;
      }
    } catch (e) { mountPage(h("div", { class: "card" }, h("h1", {}, "Couldn't load your data"), h("p", {}, e.message))); return; }
    setupNav();
    showLastRun();
    await decideOnboarding();
    window.addEventListener("hashchange", route);
    route();
  }

  // ------------------------------------------------------------ first-run onboarding (dashboard/onboarding.js)
  const OB = window.PingOnboarding;
  async function decideOnboarding() {
    state.onb = null;
    if (!OB || !state.src.saveOnboarding) return;          // the static ?demo=1 copy can't save answers
    if (state.src.demo) {
      const sp = await state.src.sessionPrefs().catch(() => ({}));
      state.sessionPrefs = sp || {};
      if (sp?.onboarding_step === "done") return;
      state.onb = { step: OB.startStep(sp || {}), ctx: { demo: true, ...(sp || {}) }, log: [], resumed: !!sp?.onboarding_step };
      return;
    }
    const prof = state.data.profile || {};
    if (OB.shouldRun(prof, state.chat.length)) state.onb = { step: OB.startStep(prof), ctx: { ...prof }, log: [], resumed: !!prof.onboarding_step };
  }

  function setupNav() {
    $("#nav").hidden = false;
    const check = $("#check-now");
    check.onclick = () => checkNow(check);
    const theme = $("#theme-btn");
    const label = () => {
      const t = themeNow();
      theme.querySelector(".theme-label").textContent = t === "system" ? "Auto" : t === "dark" ? "Dark" : "Light";
      theme.setAttribute("aria-label", `Theme: ${t === "system" ? "follows the system" : t}. Change`);
    };
    theme.onclick = () => { setTheme({ system: "light", light: "dark", dark: "system" }[themeNow()]); label(); };
    label();
    // phones: while you type, the bottom bar steps aside so the thread keeps the room above the keyboard
    const phone = window.matchMedia("(max-width: 899px)");
    document.addEventListener("focusin", (e) => {
      if (phone.matches && e.target.matches("input:not([type=checkbox]):not([type=radio]):not([type=file]), textarea")) document.body.classList.add("typing-focus");
    });
    document.addEventListener("focusout", () => document.body.classList.remove("typing-focus"));
  }

  async function checkNow(btn) {
    if (btn) btn.disabled = true;
    try { status(await state.src.checkNow()); }
    catch (e) { status(e.status === 404 ? "Check now isn't set up yet (see README)." : `Couldn't start a run: ${e.message}`); }
    finally { if (btn) setTimeout(() => { btn.disabled = false; }, 15000); }
  }

  // light / dark: follows the system unless you pick one (kept in this browser only)
  const themeNow = () => store.get("ping-theme", "system");
  function setTheme(t) {
    store.set("ping-theme", t);
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
  }

  function showLastRun() {
    const run = (state.data.runs || [])[0];
    if (!run) return;
    $("#subtitle").textContent = `last checked ${when(run.finished_at)}`;
    // No banner for a failed run: ERP hiccups are normal. Ping posts in the chat after 3 in a row, or at once if
    // the ERP refuses the login (see ping/run.py).
  }

  function status(text) { const el = $("#status"); el.textContent = text; el.hidden = !text; }

  function showLogin(sb) {
    const email = h("input", { type: "email", required: true, autocomplete: "username", placeholder: "you@example.com", id: "login-email" });
    const pw = h("input", { type: "password", required: true, autocomplete: "current-password", placeholder: "Password", id: "login-pw" });
    const msg = h("p", { class: "muted small" });
    mountPage(h("form", { class: "login card", onsubmit: async (e) => {
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
      h("button", { type: "button", class: "btn demo", id: "view-demo", onclick: async (e) => {
        e.target.disabled = true;
        msg.textContent = "Opening the demo\u2026";
        const { error } = await sb.auth.signInAnonymously();
        if (error) { msg.textContent = `The demo couldn't start: ${error.message}`; e.target.disabled = false; return; }
        msg.textContent = "";
        location.hash = "#chat";
        startReal(sb);
      } }, "View demo"),
      h("p", { class: "muted small center" }, "No account needed: a sample student's placement season, read-only.")));
  }

  // ------------------------------------------------------------ router
  // Plain "#name" links: #chat (home), #feed, #companies, #profile, #co-<company>
  function route() {
    const hash = location.hash.slice(1) || "chat";
    const page = hash.startsWith("co-") ? "companies" : hash;
    document.body.classList.toggle("chat-on", page === "chat");
    document.querySelectorAll("#nav a").forEach((a) => {
      const on = a.dataset.route === page;
      a.classList.toggle("on", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    if (page !== "chat") document.body.classList.remove("typing-focus");
    if (hash.startsWith("co-")) {
      const name = [...byCompany().keys()].find((c) => slug(c) === hash.slice(3));
      return viewCompany(name || "");
    }
    if (hash === "feed") return viewFeed();
    if (hash === "companies") return viewCompanies();
    if (hash === "profile") return viewProfile();
    if (state.onb) return viewOnboarding();
    return viewChat();
  }

  function viewOnboarding() {
    const o = state.onb;
    document.body.classList.add("chat-on");
    const q = OB.question(o.step, o.ctx);
    const inner = h("div", { class: "thread-inner onb", "data-onboarding": o.step });
    inner.append(h("div", { class: "day" }, o.resumed && !o.log.length ? "Welcome back: let's finish setting up" : "Getting started"));
    o.log.forEach((m, i) => inner.append(textBubble(m.role, m.text, m.at, i >= (o.shown || 0))));
    o.shown = o.log.length;
    if (!o.done) inner.append(h("div", { class: "msg ping onb-q" }, q.lines.map((l) => h("p", {}, l)),
      q.upload ? onbUpload() : null, h("span", { class: "time" }, clock(new Date()))));
    const input = h("input", { id: "onb-input", autocomplete: "off", maxlength: "300", enterkeyhint: "send",
      placeholder: q.free || "Tap an answer above", "aria-label": q.free || "Answer", disabled: !q.free });
    const chips = h("div", { class: "chips wrap", role: "group", "aria-label": "Quick replies" },
      q.chips.map((c) => h("button", { type: "button", class: `chip${c.primary ? " primary" : ""}`, onclick: () => {
        if (c.insert) { input.disabled = false; input.value = c.insert; input.focus(); return; }
        onbAnswer({ value: c.value }, c.label);
      } }, c.label)),
      o.step === "first_check" ? h("button", { type: "button", class: "chip primary", onclick: () => onbFinish() }, "Go to my feed") : null);
    const form = h("form", { onsubmit: (ev) => { ev.preventDefault(); const t = input.value.trim(); if (t) onbAnswer({ text: t }, t); } },
      input, sendButton(!q.free));
    const thread = h("div", { class: "thread", id: "thread", role: "log", "aria-label": "Getting started", "aria-live": "polite" }, inner);
    mount(thread, h("div", { class: "composer" }, chips, form));
    requestAnimationFrame(() => { thread.scrollTop = thread.scrollHeight; });
    if (o.step === "first_check" && !o.done) onbFirstCheck();
  }

  function onbUpload() {
    const file = h("input", { type: "file", accept: "application/pdf", id: "onb-cv", class: "visually-hidden",
      onchange: async () => {
        const f = file.files?.[0];
        if (!f) return;
        if (f.type !== "application/pdf" || f.size > 5 * 1024 * 1024) { onbSay("A PDF up to 5 MB, please."); return; }
        try {
          const { error } = await state.src.sb.storage.from("cvs").upload("cv1.pdf", f, { upsert: true, contentType: "application/pdf" });
          if (error) throw new Error(error.message);
          const cvs = [{ label: "CV 1", path: "cv1.pdf", uploaded_at: new Date().toISOString() }, ...((state.data.profile.cvs || []).slice(1))];
          await state.src.saveOnboarding({ cvs, cv_names: cvs.map((c) => c.label) });
          state.data.profile.cvs = cvs;
          onbAnswer({ value: "uploaded" }, `Uploaded ${f.name}`);
        } catch (e) { onbSay(`Couldn't upload: ${e.message}`); }
      } });
    return h("label", { class: "btn upload", for: "onb-cv" }, "Upload a CV (PDF)", file);
  }

  function onbSay(text) { state.onb.log.push({ role: "ping", text, at: new Date().toISOString() }); viewOnboarding(); }

  async function onbAnswer(input, label) {
    const o = state.onb;
    const q = OB.question(o.step, o.ctx);
    o.log.push({ role: "ping", text: q.lines.join(" "), at: new Date().toISOString() },
               { role: "me", text: label, at: new Date().toISOString() });
    const res = OB.answer(o.step, input, o.ctx);
    try {
      await state.src.saveOnboarding(res.save);
    } catch (e) { o.log.push({ role: "ping", text: `Couldn't save that: ${e.message}`, at: new Date().toISOString() }); return viewOnboarding(); }
    if (res.useDemo) { state.onb = null; location.hash = "#chat"; return route(); }
    Object.assign(o.ctx, res.ctxPatch || {}, res.save);
    if (!state.src.demo) Object.assign(state.data.profile, res.save);
    if (res.askPing) {
      try {
        const out = await state.src.fn("ask-ping", { question: res.askPing });
        o.log.push({ role: "ping", text: out.answer, at: new Date().toISOString() });
        await loadMarks();
      } catch (e) { o.log.push({ role: "ping", text: `Couldn't save that just now (${e.message}). You can tell me later.`, at: new Date().toISOString() }); }
    }
    if (res.next === o.step && !res.ctxPatch) {
      o.log.push({ role: "ping", text: "Sorry, I didn't get that. Tap one of the answers, or Skip.", at: new Date().toISOString() });
    }
    o.step = res.next;
    if (o.step === "first_check") o.since = Date.now();
    if (o.step === "done") return onbFinish();
    viewOnboarding();
  }

  // the last step: start a check (owner), wait until a run has finished, then explain the thread
  async function onbFirstCheck() {
    const o = state.onb;
    if (o.polling) return;
    o.polling = true;
    const explain = async () => {
      if (!state.onb) return;
      o.log.push({ role: "ping", text: OB.question("first_check", o.ctx).lines.join(" "), at: new Date().toISOString() });
      for (const l of OB.CLOSING) o.log.push({ role: "ping", text: l, at: new Date().toISOString() });
      await state.src.saveOnboarding({ onboarding_step: "done" }).catch(() => {});
      o.done = true;
      viewOnboarding();
    };
    if (state.src.demo) return explain();
    if (!o.started && o.since) { o.started = true; await state.src.checkNow().catch(() => {}); }
    const since = o.since || 0;
    for (let i = 0; i < 60 && state.onb === o; i++) {          // about 20 minutes
      const run = await state.src.latestRun().catch(() => null);
      if (run?.finished_at && (!since || dt(run.finished_at) > since - 60000)) {
        state.data = await state.src.load();
        return explain();
      }
      await new Promise((r) => setTimeout(r, 20000));
    }
  }

  async function onbFinish() {
    await state.src.saveOnboarding({ onboarding_step: "done" }).catch(() => {});
    state.onb = null;
    location.hash = "#chat";
    route();
  }

  // ------------------------------------------------------------ chat (home)
  // a notice's own time first: Ping's first run posts two weeks of notices at once, and they should still
  // read in the order the CDC posted them (later, notice time and first seen are within the hour anyway)
  const itemTime = (it) => it.details?.notice_time || it.first_seen || it.sort_at;
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
  // one card per role ("X opened", "Reminder: X closes") isn't a chat message any more: the new-roles message and
  // the deadline digests list them (the Feed and Companies pages still show every role)
  const inChat = (it) => !it.dismissed && it.category !== "apply" && it.category !== "reminder" &&
    (it.level !== "hidden" || (isPast(it) && wasLive(it)));

  function threadEntries() {
    const items = state.data.items.filter(inChat).map((it) => ({ kind: "item", at: itemTime(it), it }));
    const talk = state.chat.map((m) => ({ kind: m.role, at: m.created_at, text: m.text }));
    return [...items, ...talk].filter((e) => e.at).sort((a, b) =>
      dt(a.at) - dt(b.at) || (a.kind === "item" && b.kind === "item" ? String(a.it.sort_at || "").localeCompare(String(b.it.sort_at || "")) : 0));
  }

  function unreadOf(entries) {
    // first visit (or the demo): don't call two weeks of history "unread", only the last day
    const lastAt = entries.length ? dt(entries[entries.length - 1].at) : null;
    const readAt = state.readAt ? dt(state.readAt) : lastAt && new Date(lastAt - 86400000);
    // Ping's own messages (e.g. "couldn't reach the ERP") count as unread too, not your questions or its replies
    return { readAt, unread: entries.filter((e) => (e.kind === "item" || e.kind === "ping") && (!readAt || dt(e.at) > readAt)) };
  }

  const QUICK = [{ label: "What's due tonight?" }, { label: "Anything for me?" }, { label: "Which CV for …?", insert: "Which CV should I use for " },
                 { label: "My preferences", text: "What are my preferences?" }];
  const ICON_SEND = () => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", "M5 12h13M12 5l7 7-7 7");
    s.append(p); return s; };
  const sendButton = (disabled) => h("button", { class: "btn send", "aria-label": "Send", disabled }, ICON_SEND());

  function viewChat() {
    const entries = threadEntries();
    const { readAt, unread } = unreadOf(entries);
    const inner = h("div", { class: "thread-inner" });
    let group = null, lastDay = null, divider = null;
    const snapshot = state.asOf && h("p", { class: "note-line snapshot" }, "Demo: " +
      `an anonymised snapshot of a real run, shown as it was on ${when(state.asOf)}. Fake roll number, name and CGPA; ` +
      "other students and all mail removed.");
    if (!entries.length) inner.append(h("p", { class: "empty" }, "No messages yet. Ping posts here after its first check (about 10 minutes)."));
    for (const e of entries) {
      const day = dayLabel(e.at);
      // one section per day: its header sticks to the top while you scroll through that day
      if (day !== lastDay) { group = h("section", { class: "daygroup", "aria-label": day }, h("div", { class: "day" }, day)); inner.append(group); lastDay = day; }
      if (!divider && unread.length && e === unread[0]) {
        divider = h("div", { class: "unread", id: "unread" }, `${unread.length} new`);
        if (snapshot) group.append(snapshot);
        group.append(divider);
      }
      group.append(e.kind === "item" ? itemBubble(e.it, e.at) : textBubble(e.kind, e.text, e.at));
    }
    if (snapshot && !divider) (group || inner).append(snapshot);
    const thread = h("div", { class: "thread", id: "thread", role: "log", "aria-label": "Messages", "aria-live": "polite" }, inner);
    const input = h("input", { id: "ask-input", autocomplete: "off", maxlength: "300", enterkeyhint: "send",
      placeholder: "Ask Ping: what's due tomorrow?", "aria-label": "Message Ping" });
    const btn = sendButton(true);
    input.addEventListener("input", () => { if (!state.waiting) btn.disabled = !input.value.trim(); });
    const ask = (text) => { input.value = text; btn.disabled = false; form.requestSubmit(); };
    const quick = h("div", { class: "chips", role: "group", "aria-label": "Quick questions" }, QUICK.map((c) =>
      h("button", { type: "button", class: "chip", onclick: () => {
        if (c.insert) { input.value = c.insert; btn.disabled = false; input.focus(); return; }
        ask(c.text || c.label);
      } }, c.label)));
    const form = h("form", { onsubmit: (ev) => { ev.preventDefault(); send(input, inner, thread, btn); } }, input, btn);
    // "N new" when the first unread message is below you; "Latest" when you're far up the thread
    const jump = h("button", { type: "button", class: "pill-btn", id: "jump", hidden: true });
    const composer = h("div", { class: "composer" }, jump, quick, form);
    mount(thread, composer);
    const syncJump = () => {
      const tr = thread.getBoundingClientRect();
      const fromBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
      jump.style.bottom = `${composer.offsetHeight + 12}px`;
      if (divider && divider.getBoundingClientRect().top > tr.bottom - 8) {
        jump.textContent = `${unread.length} new ↓`; jump.className = "pill-btn"; jump.hidden = false;
        jump.onclick = () => divider.scrollIntoView({ block: "start", behavior: motion() });
      } else if (fromBottom > thread.clientHeight) {
        jump.textContent = "Latest ↓"; jump.className = "pill-btn ghost"; jump.hidden = false;
        jump.onclick = () => thread.scrollTo({ top: thread.scrollHeight, behavior: motion() });
      } else jump.hidden = true;
    };
    thread.addEventListener("scroll", syncJump, { passive: true });
    // open at the first unread message, otherwise at the bottom (the latest thing that happened)
    requestAnimationFrame(() => {
      if (divider) (snapshot || divider).scrollIntoView({ block: "start" });
      else thread.scrollTop = thread.scrollHeight;
      syncJump();
    });
    const latest = entries.length ? entries[entries.length - 1].at : null;
    if (latest && (!readAt || dt(latest) > readAt)) {
      state.readAt = new Date(Math.max(dt(latest), Date.now())).toISOString();
      state.src.setReadAt(state.readAt).catch(() => {});
    }
    navUnread(0);
  }
  const motion = () => (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
  function navUnread(n) { const d = $("#nav-unread"); if (!d) return; d.textContent = n > 99 ? "99+" : String(n); d.hidden = !n;
    d.parentElement.setAttribute("aria-label", n ? `Chat, ${n} new` : "Chat"); }

  function textBubble(role, text, at, enter) {
    return h("div", { class: `msg ${role === "me" ? "me" : "ping"}${enter ? " enter" : ""}` }, h("span", { class: "text" }, text),
      h("div", { class: "foot" }, h("span", { class: "time" }, clock(at))));
  }

  // what kind of message it is decides its edge colour and kicker (docs/DESIGN.md, "Message kinds")
  function msgKind(it) {
    const d = it.details || {};
    if (it.needs_review) return "review";
    if (d.kind === "application" || d.kind === "deadline" || ["digest", "reminder", "deadline"].includes(it.category)) return "soon";
    if (["test", "shortlist", "result"].includes(it.category) || ["test", "test_rooms", "shortlist", "result", "interview"].includes(d.kind)) return "test";
    if (d.kind === "listing" || it.category === "listing" || it.category === "collapse") return "new";
    return "you";
  }
  // "in 1h 56m" / "in 2 h" / "in 3 days" / "over", from the page's now (the demo's snapshot time)
  function countdown(at) {
    const ms = dt(at) - nowDate();
    if (!(ms > 0)) return "over";
    const m = Math.round(ms / 60000);
    if (m < 60) return `in ${m} min`;
    const hrs = Math.floor(m / 60), mm = m % 60;
    if (hrs < 6) return mm ? `in ${hrs}h ${mm}m` : `in ${hrs} h`;
    if (hrs < 48) return `in ${hrs} h`;
    return `in ${Math.round(hrs / 24)} days`;
  }
  const countPill = (at, kind) => { const c = countdown(at);
    return h("span", { class: `pill ${c === "over" ? "over" : kind === "test" ? "test" : "soon"}`, title: when(at) }, c); };
  const shortTime = (v) => { const d = dt(v); const k = istDay(d);
    return k === istDay(nowDate()) ? clock(v) : `${d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" })} ${clock(v)}`; };

  function itemBubble(it, at) {
    const past = isPast(it);
    const kind = msgKind(it), d = it.details || {};
    const why = it.details?.hidden_because || "";
    const pastLabel = /updated/.test(why) ? "Since updated" : /reminder/.test(why) ? "Replaced by reminder"
      : /deadline/.test(why) ? "Deadline passed" : "Over";
    const due = it.due_at || it.event_at;
    const label = past ? pastLabel : kind === "review" ? "Question"
      : kind === "soon" ? (d.role === "reminder" || it.category === "reminder" ? "Reminder" : due ? `Closing ${shortTime(due)}` : "Deadline")
      : kind === "test" ? ({ shortlist: "Shortlist", result: "Result" }[it.category] || "Test")
      : kind === "new" ? "New roles" : LEVELS[it.level] || "For you";
    const open = state.open.has(it.id);
    const bubble = h("div", { class: `msg ping item k-${kind}${past ? " past" : ""}${it.done ? " done" : ""}`, role: "button",
      tabindex: "0", "aria-expanded": String(open), "data-kind": kind },
      h("div", { class: "kicker" }, h("span", { class: "k" }, label),
        !past && due && (kind === "soon" || kind === "test") ? countPill(due, kind) : null),
      h("span", { class: "text title" }, retitle(it)),
      listBlock(it),
      h("div", { class: "foot" }, h("span", { class: "expand" }, open ? "Less ▴" : "Details ▾"), h("span", { class: "time" }, clock(at))));
    const toggle = (ev) => {
      if (ev.target.closest("a, button, .more, summary, details")) return;
      state.open.has(it.id) ? state.open.delete(it.id) : state.open.add(it.id);
      const next = itemBubble(it, at);
      bubble.replaceWith(next);
      next.focus({ preventScroll: true });
    };
    bubble.addEventListener("click", toggle);
    bubble.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(ev); } });
    if (open) bubble.append(itemDetails(it));
    return bubble;
  }

  // "... — 11 for you" in a heading follows the current marks too
  function retitle(it) {
    const marks = state.marks, d = it.details || {};
    if (!marks?.size || !state.prefs?.targets || !/ — \d+ for you$/.test(it.title || "")) return it.title;
    const ids = (d.list || []).flatMap((g) => /^Applied/.test(g.head || "") ? [] : (g.rows || []).map((r) => r.id));
    return it.title.replace(/ — \d+ for you$/, ` — ${ids.filter((id) => marks.get(id)?.relevant).length} for you`);
  }

  // A digest / "new roles" / "3 shortlists out" message: its list, grouped (for you first, others collapsed),
  // then any note and the source of the dates
  // the lists were split by the targets of the last run; if the targets changed since (said in the chat), split them
  // again by the current marks
  function resplit(d) {
    const marks = state.marks, targets = state.prefs?.targets;
    if (!marks || !marks.size || !targets || !["application", "listing"].includes(d.kind)) return d.list || [];
    const out = [];
    const sections = new Map();
    for (const g of d.list || []) {
      const [prefix] = String(g.head || "").split(" · ");
      const key = /^(For you|Others|$)/.test(prefix) ? "" : prefix;
      if (/^Applied/.test(prefix)) { out.push(g); continue; }
      sections.set(key, [...(sections.get(key) || []), ...(g.rows || [])]);
    }
    const listOthers = state.prefs?.list_other_roles !== false;
    for (const [prefix, rows] of sections) {
      const mine = rows.filter((r) => marks.get(r.id)?.relevant).map((r) => {
        const m = marks.get(r.id);
        return { ...r, note: [m.reason, m.best_cv ? `Apply with: ${m.best_cv}` : ""].filter(Boolean).join(" · ") };
      });
      const others = rows.filter((r) => !marks.get(r.id)?.relevant).map((r) => ({ ...r, note: "" }));
      const h = (s) => (prefix ? `${prefix} · ${s}` : s);
      if (mine.length) out.unshift({ head: h("For you"), rows: mine });
      if (others.length) out.push(listOthers ? { head: h(`Others (${others.length})`), collapsed: true, rows: others }
                                             : { head: h(`${others.length} other roles not shown`), rows: [] });
    }
    return out;
  }

  let roleMap = null;
  const roleById = () => (roleMap && roleMap.src === state.data.roles ? roleMap.map
    : (roleMap = { src: state.data.roles, map: new Map(state.data.roles.map((r) => [r.id, r])) }).map);

  function listBlock(it) {
    const d0 = it.details || {};
    const d = { ...d0, list: resplit(d0) };
    if (!(d.list || []).length && !d.source) return null;
    // a row: "Company — Role", a ✓ applied badge, and the reason / which CV on a second line
    const row = (r) => {
      const applied = r.tag === "done" || roleById().get(r.id)?.applied;
      return h("div", { class: `li ${r.tag || ""}` }, h("span", { class: "rt" }, r.text),
        applied ? h("span", { class: "pill applied" }, "✓ applied") : null,
        r.note ? h("span", { class: "why" }, r.note) : null);
    };
    const groups = (d.list || []).map((g) => {
      const rows = (g.rows || []).map(row);
      if (g.collapsed && rows.length) {
        return h("details", { class: "grp", onclick: (ev) => ev.stopPropagation() }, h("summary", {}, g.head), rows);
      }
      return h("div", { class: "grp" }, g.head ? h("div", { class: "gh" }, g.head) : null, rows);
    });
    return h("div", { class: "list" }, groups, d.note ? h("div", { class: "why" }, d.note) : null,
      d.source ? h("div", { class: "src" }, d.source) : null);
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

  // new bubbles go into today's section (a new one if the thread ended on an earlier day)
  function appendToday(inner, node) {
    let group = inner.lastElementChild;
    if (!group || !group.classList.contains("daygroup") || group.getAttribute("aria-label") !== "Today") {
      group = h("section", { class: "daygroup", "aria-label": "Today" }, h("div", { class: "day" }, "Today"));
      inner.querySelector(".empty")?.remove();
      inner.append(group);
    }
    group.append(node);
    return node;
  }

  async function send(input, inner, thread, btn) {
    const q = input.value.trim();
    if (!q || state.waiting) return;
    input.value = "";
    state.waiting = true;
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.replaceChildren(h("span", { class: "wait", "aria-hidden": "true" }, "…"));
    const mine = { role: "me", text: q, created_at: new Date().toISOString() };
    state.chat.push(mine);
    appendToday(inner, textBubble("me", q, mine.created_at, true));
    const wait = appendToday(inner, h("div", { class: "msg ping typing enter", role: "status", "aria-label": "Ping is typing" },
      h("span", { class: "dot" }), h("span", { class: "dot" }), h("span", { class: "dot" })));
    thread.scrollTop = thread.scrollHeight;
    // saved before asking: Ask Ping reads the thread (for follow-ups like "nothing else?") from the database
    await state.src.addChat(mine).catch(() => {});
    let answer;
    state.sending = (state.sending || 0) + 1;
    try { answer = await state.src.ask(q); } catch (e) { answer = e.message; } finally { state.sending -= 1; }
    const reply = { role: "ping", text: answer || "I couldn't come up with an answer.", created_at: new Date().toISOString() };
    state.chat.push(reply);
    state.waiting = false;
    btn.removeAttribute("aria-busy");
    btn.replaceChildren(ICON_SEND());
    btn.disabled = !input.value.trim();
    if (wait.isConnected) {
      wait.replaceWith(textBubble("ping", reply.text, reply.created_at, true));
      thread.scrollTop = thread.scrollHeight;
    } else {
      route();   // the chat was drawn again meanwhile (e.g. the "For you" marks arrived): draw it with the reply
    }
    state.src.addChat(reply).catch(() => {});
    state.readAt = reply.created_at;
    state.src.setReadAt(state.readAt).catch(() => {});
    // a preference was saved: fetch the new marks and show the lists split the new way
    if (state.prefsChanged) { state.prefsChanged = false; await loadMarks(); route(); }
  }

  async function loadMarks() {
    if (!state.src?.marks) return;
    try {
      const { prefs, marks } = await state.src.marks();
      state.marks = marks;
      state.prefs = prefs;
      Object.assign(state.data.profile, { targets: prefs.targets, reminder_hours: prefs.reminder_hours,
                                          list_other_roles: prefs.list_other_roles });
    } catch { /* keep the lists as the last run built them */ }
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
    mountPage(
      h("p", { class: "page-links" }, h("a", { href: "#profile" }, "← Profile")),
      h("h1", {}, "All updates"),
      h("p", { class: "muted small" }, "Newest first. “You applied” is anything about a role you applied to; " +
        "“Open for you” is roles you can still apply to; “Hidden” is kept but not about you (or already past)."),
      h("div", { class: "chips filters", role: "group", "aria-label": "Show" }, filters.map(([key, label, n]) =>
        h("button", { type: "button", class: "chip", "aria-pressed": String(state.filter === key), onclick: () => { state.filter = key; viewFeed(); } },
          label, h("span", { class: "n" }, n)))),
      shown.length ? h("div", { class: "list" }, shown.map(itemCard)) : h("p", { class: "muted" }, "Nothing here right now."));
  }

  function itemCard(it) {
    const due = itemDue(it);
    const soon = due && dt(due) - nowDate() < 86400000 && dt(due) > nowDate();
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

  // the "For you" mark of a role: the current marks (targets said in the chat) or the last run's
  const markOf = (r) => (state.marks?.size ? state.marks.get(r.id) : r.relevance) || null;
  const targetsOn = () => {
    const p = { ...(state.data.profile || {}), ...(state.prefs || {}) };
    return !!p.targets && p.feed_mode !== "all";
  };
  const isOpen = (r) => { const d = dt(deadlineOf(r)); return !!d && d > nowDate(); };
  const forYou = (r) => r.eligible !== false && isOpen(r) && !r.applied && (targetsOn() ? !!markOf(r)?.relevant : true);
  const closingSoon = (r) => !r.applied && r.eligible !== false && isOpen(r) && dt(deadlineOf(r)) - nowDate() < 48 * 3600000;
  const FILTERS = [["for_you", "For you", forYou], ["applied", "Applied", (r) => !!r.applied], ["soon", "Closing soon", closingSoon],
                   ["all", "All", () => true]];
  function ctcShort(r) {
    const n = Number(r.ctc);
    if (!n) return "CTC —";
    if ((r.currency || "INR") !== "INR") return money(n, r.currency);
    return n >= 1e7 ? `₹${(n / 1e7).toFixed(2).replace(/\.?0+$/, "")} Cr` : `₹${(n / 1e5).toFixed(1).replace(/\.0$/, "")} L`;
  }
  const bestCv = (r) => { const m = markOf(r); return m?.relevant && m.best_cv ? m.best_cv : null; };

  function roleRow(r) {
    const dl = deadlineOf(r), open = isOpen(r), mk = markOf(r);
    const cls = r.applied ? "applied" : targetsOn() && forYou(r) ? "you" : closingSoon(r) ? "soon" : "plain";
    const cv = bestCv(r);
    return h("button", { type: "button", class: `role-row r-${cls}`, "data-role": r.id, onclick: () => openRole(r),
      "aria-label": `${r.company}, ${r.designation}. Details` },
      h("span", {}, h("span", { class: "co" }, r.company), h("span", { class: "rn" }, r.designation)),
      h("span", { class: "ctc" }, ctcShort(r)),
      h("span", { class: "meta" },
        dl ? h("span", { class: "num" }, `${open ? "Closes" : "Closed"} ${when(dl)}`) : h("span", {}, "No deadline yet"),
        dl && open && !r.applied ? countPill(dl, "soon") : null,
        r.applied ? h("span", { class: "pill applied" }, "✓ applied") : null,
        targetsOn() && mk?.relevant && !r.applied ? h("span", { class: "pill you" }, "For you") : null,
        r.eligible === false ? h("span", { class: "pill no" }, "Not eligible") : null,
        cv ? h("span", { class: "applywith" }, "Apply with ", h("strong", {}, cv)) : null));
  }

  function sortRoles(list, key) {
    const t = (r) => +dt(deadlineOf(r)) || 0;
    if (key === "applied") return list.sort((a, b) => t(b) - t(a));
    if (key === "all") return list.sort((a, b) => (isOpen(b) - isOpen(a)) || (isOpen(a) ? t(a) - t(b) : t(b) - t(a)));
    return list.sort((a, b) => t(a) - t(b));
  }

  function viewCompanies() {
    const roles = state.data.roles;
    if (!state.roleFilter) state.roleFilter = roles.some(forYou) ? "for_you" : "all";
    const input = h("input", { class: "search", id: "company-search", type: "search", placeholder: "Search a company or role",
      "aria-label": "Search companies and roles", value: state.companyQuery, oninput: (e) => { state.companyQuery = e.target.value; state.roleLimit = 60; draw(); } });
    const chips = h("div", { class: "chips filters", role: "group", "aria-label": "Show" });
    const out = h("div", { class: "roles", id: "roles", "aria-live": "polite" });
    const count = h("p", { class: "lede", id: "roles-count" });
    function draw() {
      const q = state.companyQuery.trim().toLowerCase();
      const match = (r) => !q || `${r.company} ${r.designation}`.toLowerCase().includes(q);
      chips.replaceChildren(...FILTERS.map(([key, label, fn]) => h("button", { type: "button", class: "chip", "data-filter": key,
        "aria-pressed": String(state.roleFilter === key), onclick: () => { state.roleFilter = key; state.roleLimit = 60; draw(); } },
        label, h("span", { class: "n" }, roles.filter((r) => match(r) && fn(r)).length))));
      const fn = FILTERS.find(([k]) => k === state.roleFilter)[2];
      const shown = sortRoles(roles.filter((r) => match(r) && fn(r)), state.roleFilter);
      const limit = state.roleLimit || 60;
      count.textContent = `${shown.length} role${shown.length === 1 ? "" : "s"} · ${new Set(shown.map((r) => r.company)).size} companies`;
      out.replaceChildren(...(shown.length ? shown.slice(0, limit).map(roleRow)
        : [h("p", { class: "empty" }, q ? `No roles match “${state.companyQuery}”. Try All.` : "Nothing here right now. Try All.")]),
        shown.length > limit ? h("button", { type: "button", class: "btn ghost", onclick: () => { state.roleLimit = limit + 100; draw(); } },
          `Show ${Math.min(100, shown.length - limit)} more`) : null);
    }
    draw();
    const search = h("div", { class: "search-row" }, svgIcon("M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14zM21 21l-5-5"), input);
    mountPage(h("h1", {}, "Companies"),
      h("p", { class: "lede" }, `Every role on the ERP's companies list (${roles.length}). Tap one for pay, eligibility and deadlines.`),
      search, chips, count, out,
      h("p", { class: "page-links" }, h("a", { href: "#feed" }, "All updates, newest first")));
  }

  function svgIcon(d) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", d); s.append(p);
    return s;
  }

  // the role sheet: everything Ping knows about one role (a bottom sheet on phones, a side panel on desktop)
  function openRole(r) {
    const sheet = $("#sheet");
    const kv = (rows) => { rows = rows.filter(([, v]) => v != null && v !== "" && v !== false);
      return rows.length ? h("dl", { class: "kv" }, rows.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null; };
    const sec = (title, ...body) => { const b = body.flat().filter(Boolean); return b.length ? h("section", {}, h("h3", {}, title), b) : null; };
    const f = r.more_details?.fields || {};
    const pay = Object.entries(f).filter(([k, v]) => v && /ctc|salary|gross|base|stipend|bonus|esop|joining|relocation|bond|variable|retention/i.test(k)
      && String(v).length < 400);
    const e = r.eligibility || {}, mk = markOf(r), dl = deadlineOf(r);
    const updates = state.data.items.filter((i) => i.company === r.company && !i.dismissed).sort(sortNewest).slice(0, 8);
    const depts = new Set((r.allowed || []).map((a) => a.department));
    const close = h("button", { type: "button", class: "close", "aria-label": "Close", onclick: () => sheet.close() }, "×");
    sheet.replaceChildren(
      h("div", { class: "sheet-head" }, h("div", {}, h("div", { class: "co muted small" }, r.company),
        h("h2", { id: "sheet-title" }, r.designation)), close),
      h("div", { class: "sheet-body" },
        h("div", { class: "chips wrap", style: "padding:0" },
          r.applied ? h("span", { class: "pill applied" }, "✓ applied") : null,
          targetsOn() && mk?.relevant ? h("span", { class: "pill you" }, "For you") : null,
          dl && isOpen(r) && !r.applied ? countPill(dl, "soon") : null,
          r.eligible === true ? h("span", { class: "pill you" }, "Eligible") : r.eligible === false ? h("span", { class: "pill no" }, "Not eligible")
            : h("span", { class: "pill over" }, "Eligibility not sure")),
        sec("Why it's for you", mk?.relevant && mk.reason ? h("p", { style: "margin:0" }, mk.reason) : null,
          bestCv(r) ? h("p", { style: "margin:0" }, "Apply with ", h("strong", {}, bestCv(r))) : null),
        sec("Pay", kv([["CTC", money(r.ctc, r.currency)], ...pay.map(([k, v]) => [k, /^\d+(\.\d+)?$/.test(String(v)) ? money(v, r.currency) : String(v)])])),
        sec("Eligibility", kv([
          ["You", r.eligible === true ? "Eligible" : r.eligible === false ? "Not eligible" : "Not sure"],
          ["Why", [...(e.reasons || []), ...(e.flags || [])].join("; ")],
          ["CGPA", r.cgpa_cutoff ? `≥ ${r.cgpa_cutoff}` : "No cut-off"],
          ["Backlogs", r.backlog_rule ? r.backlog_rule.replace(/\.+$/, "") : ""],
          ["Departments", depts.size ? `${depts.size} allowed` : ""],
          ["Written test", r.has_written_test === true ? "Yes" : r.has_written_test === false ? "No" : ""]])),
        sec("Deadlines", kv([
          ["Applications open", when(r.apply_start)],
          ["Closes", when(dl) || "Not announced"],
          ["Where that date is from", r.deadline_source || "companies list"],
          ["ERP's own close time", r.effective_deadline && r.apply_end && +dt(r.effective_deadline) !== +dt(r.apply_end) ? when(r.apply_end) : ""],
          ["Interview", r.interview_date || ""]])),
        sec("Notices and lists", updates.length ? h("div", { class: "list" }, updates.map((i) =>
          h("div", { class: "small" }, h("span", { class: "muted num" }, shortTime(itemTime(i)) + " · "), i.title,
            i.pdf_status === "yes" ? h("span", { class: "pill you", style: "margin-left:6px" }, "you're on it") : null,
            i.notice_id ? [" ", h("button", { type: "button", class: "linklike", onclick: () => openNotice(i.notice_id) }, "Open notice")] : null)))
          : h("p", { class: "muted small", style: "margin:0" }, "No notices about this company yet.")),
        r.job_description ? sec("Job description", h("details", {}, h("summary", { class: "linklike" }, "Show"),
          h("pre", { class: "notice" }, r.job_description.slice(0, 4000)))) : null,
        sec("Source", h("p", { class: "muted small", style: "margin:0" },
          `The ERP's companies list${r.last_seen ? `, last read ${when(r.last_seen)}` : ""}. Ping only reads the ERP: apply there. `),
          h("a", { href: companyHref(r.company), onclick: () => sheet.close() }, `All roles at ${r.company}`))));
    if (!sheet.dataset.wired) {
      sheet.dataset.wired = "1";
      sheet.addEventListener("click", (ev) => { if (ev.target === sheet) sheet.close(); });   // a tap on the backdrop
    }
    sheet.showModal();
    sheet.scrollTop = 0;
    close.focus();
  }

  function viewCompany(name) {
    const roles = sortRoles([...(byCompany().get(name) || [])], "all");
    const items = state.data.items.filter((i) => i.company === name && i.level !== "hidden").sort(sortNewest);
    mountPage(
      h("p", { class: "page-links" }, h("a", { href: "#companies" }, "← Companies")),
      h("h1", {}, name || "Not found"),
      h("p", { class: "lede" }, `${roles.length} role${roles.length === 1 ? "" : "s"}. Tap one for pay, eligibility and deadlines.`),
      roles.length ? h("div", { class: "roles" }, roles.map(roleRow)) : h("p", { class: "empty" }, "No roles for this company in the companies list."),
      h("h2", {}, "Updates"),
      items.length ? h("div", { class: "list" }, items.map(itemCard)) : h("p", { class: "muted" }, "Nothing current."));
  }

  // ------------------------------------------------------------ profile
  // Cards (About you · What I'm looking for · CVs · Schedule & reminders · Account), each read at a glance and
  // edited in place with its own Save. The same fields the onboarding and the chat set.
  function profileValues() {
    const p = { ...(state.data.profile || {}) };
    if (state.src.demo) for (const [k, v] of Object.entries(state.sessionPrefs || {})) if (DEMO_OWN.includes(k) && v != null) p[k] = v;
    if (state.prefs) for (const k of ["targets", "reminder_hours", "list_other_roles"]) if (state.prefs[k] !== undefined) p[k] = state.prefs[k];
    return p;
  }
  const everyText = (m) => (Number(m) === 30 ? "Every 30 minutes" : Number(m) === 120 ? "Every 2 hours" : "Every hour");

  function viewProfile() {
    const p = profileValues();
    const demo = !!state.src.demo || state.src.kind === "demo";
    const depts = new Set(), degrees = new Set();
    state.data.roles.forEach((r) => (r.allowed || []).forEach((a) => { depts.add(a.department); degrees.add(a.degree); }));
    const field = (name, label, value, attrs = {}, hint) => h("label", {}, label, hint ? h("span", { class: "hint" }, hint) : null,
      h("input", { name, id: `pf-${name}`, value: value ?? "", ...attrs }));
    const lists = (v) => (v || []).join("\n");
    const kv = (rows) => h("dl", { class: "kv summary" }, rows.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v == null || v === "" ? "—" : v)]));

    // one card: summary, or (after Edit) its form; Save writes only this card's fields
    function card(key, title, summary, formKids, toPatch, opts = {}) {
      const editing = state.editCard === key;
      const msg = h("span", { class: "saved", role: "status" }, state.cardMsg?.[key] || "");
      const head = h("div", { class: "pcard-head" }, h("h2", { id: `pc-${key}-h` }, title),
        !editing && formKids && !opts.locked ? h("button", { type: "button", class: "btn ghost small", id: `edit-${key}`,
          "aria-label": `Edit ${title}`, onclick: () => { state.editCard = key; viewProfile(); $(`#pc-${key} input, #pc-${key} textarea, #pc-${key} select`)?.focus(); } }, "Edit") : null);
      let body;
      if (editing) {
        const form = h("form", { onsubmit: async (ev) => {
          ev.preventDefault();
          const patch = toPatch(new FormData(form));
          msg.textContent = "Saving…";
          try {
            const before = profileValues().targets || "";
            const note = await state.src.saveProfile(patch);
            if (!state.src.demo) Object.assign(state.data.profile, patch);
            let said = note || (state.src.kind === "demo" ? "Saved for this visit (demo)." : "Saved. Applies on the next check.");
            // new targets: have the roles marked now (the same path as saying it in the chat), then split the lists
            if ("targets" in patch && state.src.fn && (patch.targets || "") !== before && patch.targets) {
              msg.textContent = "Saved. Marking roles…";
              const out = await state.src.fn("ask-ping", { question: `my targets are ${patch.targets}` }).catch((e) => ({ answer: e.message }));
              said = out.answer || said;
            }
            if (state.src.fn) await loadMarks();
            state.cardMsg = { [key]: said };
            state.editCard = null;
            viewProfile();
            $(`#edit-${key}`)?.focus();
          } catch (err) { msg.textContent = err.message; }
        } }, formKids, h("div", { class: "actions" }, h("button", { class: "btn" }, "Save"),
          h("button", { type: "button", class: "btn ghost", onclick: () => { state.editCard = null; viewProfile(); } }, "Cancel"), msg));
        body = form;
      } else body = [summary, msg.textContent ? msg : null];
      return h("section", { class: "card pcard", id: `pc-${key}`, "aria-labelledby": `pc-${key}-h` }, head, opts.note ? h("p", { class: "hint", style: "margin:0" }, opts.note) : null, body);
    }

    const about = card("about", "About you",
      kv([["Roll number", p.roll || "Your ERP user id"], ["Name", p.name], ["Degree", p.degree], ["Department", p.department],
          ["CGPA", p.cgpa], ["Active backlogs", p.active_backlogs ? "Yes" : "No"]]),
      [h("div", { class: "row2" },
        field("roll", "Roll number", p.roll, {}, "Leave empty to use your ERP user id"),
        field("name", "Name", p.name, { autocomplete: "name" }, "Only used when a PDF has names but no roll numbers")),
       h("div", { class: "row2" },
        field("degree", "Degree", p.degree, { list: "dl-degrees" }),
        field("department", "Department", p.department, { list: "dl-depts" }, "As the ERP writes it")),
       h("div", { class: "row2" },
        field("cgpa", "CGPA", p.cgpa, { type: "number", step: "0.01", min: "0", max: "10", inputmode: "decimal" }),
        h("label", { class: "check" }, h("input", { type: "checkbox", name: "active_backlogs", id: "pf-backlogs", checked: !!p.active_backlogs }), "I have active backlogs")),
       h("datalist", { id: "dl-depts" }, [...depts].sort().map((d) => h("option", { value: d }))),
       h("datalist", { id: "dl-degrees" }, [...degrees].sort().map((d) => h("option", { value: d })))],
      (f) => { const cgpa = String(f.get("cgpa") || "").trim(); const t = (k) => String(f.get(k) || "").trim() || null;
        return { roll: t("roll"), name: t("name"), department: t("department"), degree: t("degree"), cgpa: cgpa ? Number(cgpa) : null,
                 active_backlogs: f.get("active_backlogs") === "on" }; },
      { locked: demo, note: demo ? "The demo student's details are made up and fixed." : "Used to decide what you're eligible for." });

    const split = (f, k) => String(f.get(k) || "").split(/\n|,/).map((s) => s.trim()).filter(Boolean);
    const looking = card("looking", "What I'm looking for",
      kv([["Feed", p.feed_mode === "all" ? "Everything from the ERP" : "Only what fits me first"],
          ["Targets", p.targets || "Not set: every role is listed the same way"],
          ["Other roles", p.list_other_roles === false ? "Not listed" : "Listed separately, collapsed"],
          ...(demo ? [] : [["Interested", (p.interested_companies || []).join(", ")], ["Not interested", (p.not_interested_companies || []).join(", ")]])]),
      [h("fieldset", { class: "seg" }, h("legend", {}, "Feed"),
        h("label", { class: "check" }, h("input", { type: "radio", name: "feed_mode", value: "personal", checked: p.feed_mode !== "all" }), "Only what fits me first"),
        h("label", { class: "check" }, h("input", { type: "radio", name: "feed_mode", value: "all", checked: p.feed_mode === "all" }), "Everything from the ERP")),
       h("label", {}, "Targets", h("span", { class: "hint" }, "In your own words. Ping marks each role \"For you\" or not and lists those first."),
        h("textarea", { name: "targets", id: "pf-targets", rows: 3, placeholder: "The kinds of roles you want, and any you don't" }, p.targets || "")),
       h("label", { class: "check" }, h("input", { type: "checkbox", name: "list_other_roles", id: "pf-list-others", checked: p.list_other_roles !== false }),
        "List the other roles separately so I don't miss anything"),
       demo ? null : h("div", { class: "row2" },
        h("label", {}, "Interested companies", h("span", { class: "hint" }, "One per line"),
          h("textarea", { name: "interested_companies", id: "pf-interested", rows: 4 }, lists(p.interested_companies))),
        h("label", {}, "Not interested", h("span", { class: "hint" }, "One per line. Their roles are hidden."),
          h("textarea", { name: "not_interested_companies", id: "pf-not-interested", rows: 4 }, lists(p.not_interested_companies))))],
      (f) => ({ feed_mode: f.get("feed_mode") === "all" ? "all" : "personal", targets: String(f.get("targets") || "").trim() || null,
                list_other_roles: f.get("list_other_roles") === "on",
                ...(demo ? {} : { interested_companies: split(f, "interested_companies"), not_interested_companies: split(f, "not_interested_companies") }) }),
      { note: "You can also just tell Ping in the chat: \"only show me finance roles\", \"also include data roles\"." });

    const cvs = h("section", { class: "card pcard", id: "pc-cvs", "aria-labelledby": "pc-cvs-h" },
      h("div", { class: "pcard-head" }, h("h2", { id: "pc-cvs-h" }, "CVs")), cvBlock(p));

    const sched = card("schedule", "Schedule & reminders",
      kv([["Checks the ERP", everyText(p.check_every_minutes)], ["Between", `${p.check_from || "06:00"} and ${p.check_to || "01:00"} IST`],
          ["Reminders", Number(p.reminder_hours ?? 2) === 24 ? "The day before" : `${p.reminder_hours ?? 2} h before a deadline`]]),
      [h("label", {}, "How often", h("select", { name: "check_every_minutes", id: "pf-every" },
          [[30, "Every 30 minutes"], [60, "Every hour"], [120, "Every 2 hours"]].map(([v, t]) =>
            h("option", { value: v, selected: Number(p.check_every_minutes ?? 60) === v }, t)))),
       h("div", { class: "row2" },
        field("check_from", "From (IST)", p.check_from || "06:00", { type: "time" }),
        field("check_to", "To (IST)", p.check_to || "01:00", { type: "time" }, "Past midnight is fine, e.g. 06:00 to 01:00")),
       field("reminder_hours", "Remind me before a deadline (hours)", p.reminder_hours ?? 2,
         { type: "number", step: "0.5", min: "0.5", max: "48", inputmode: "decimal" }, "One reminder per deadline, listing what you haven't applied to")],
      (f) => ({ check_every_minutes: Number(f.get("check_every_minutes")) || 60, check_from: String(f.get("check_from") || "06:00").slice(0, 5),
                check_to: String(f.get("check_to") || "01:00").slice(0, 5),
                reminder_hours: Number(f.get("reminder_hours")) > 0 ? Number(f.get("reminder_hours")) : 2 }),
      { note: demo ? "In the demo these are saved for your session only; nothing runs on a schedule for it." : "Or say it in the chat: \"check every 30 minutes\"." });

    const run = (state.data.runs || [])[0];
    const themeChips = h("div", { class: "chips wrap", role: "group", "aria-label": "Theme", style: "padding:0" },
      [["system", "Auto"], ["light", "Light"], ["dark", "Dark"]].map(([t, l]) => h("button", { type: "button", class: "chip", "data-theme-choice": t,
        "aria-pressed": String(themeNow() === t), onclick: () => { setTheme(t); viewProfile(); } }, l)));
    const checkBtn = h("button", { type: "button", class: "btn ghost", id: "account-check" }, "Check now");
    checkBtn.onclick = () => checkNow(checkBtn);
    const account = h("section", { class: "card pcard", id: "pc-account", "aria-labelledby": "pc-account-h" },
      h("div", { class: "pcard-head" }, h("h2", { id: "pc-account-h" }, "Account")),
      kv([["Signed in as", demo ? "Demo visitor (anonymous, read-only)" : "The owner"], ["Last check", run ? when(run.finished_at || run.started_at) : "Not yet"]]),
      h("div", { class: "actions" }, checkBtn, h("a", { class: "btn ghost", href: "#feed" }, "All updates"),
        state.exit ? h("button", { type: "button", class: "btn ghost", id: "sign-out", onclick: () => state.exit.run() }, state.exit.label) : null),
      h("div", {}, h("div", { class: "hint", style: "margin-bottom:4px" }, "Theme"), themeChips));

    mountPage(h("h1", {}, "Profile"), h("p", { class: "lede" },
      "Whether you applied comes from the ERP's companies list, not from here. Ping only reads the ERP."),
      h("div", { class: "pcards" }, about, looking, cvs, sched, account));
  }

  // "My CVs": up to 3 PDFs with labels, in the private "cvs" bucket (owner only; never in git; demo sessions can't
  // reach it). The hourly run summarises a new or replaced file once; only the summary is kept in the profile.
  function cvBlock(p) {
    const cvs = (p.cvs || []).slice(0, 3);
    const demo = !!state.src?.demo || state.src?.kind === "demo";
    const status = h("span", { class: "muted small", id: "cv-status" });
    const slot = (i) => {
      const c = cvs[i] || {};
      const label = h("input", { id: `cv-label-${i}`, value: c.label || "", placeholder: `CV ${i + 1} label`, "aria-label": `CV ${i + 1} label`, disabled: demo });
      const file = h("input", { type: "file", accept: "application/pdf", id: `cv-file-${i}`, "aria-label": `CV ${i + 1} PDF`, disabled: demo });
      const upload = h("button", { type: "button", class: "btn small", disabled: demo, onclick: async () => {
        const f = file.files?.[0];
        const name = label.value.trim();
        if (!name) { status.textContent = " Give the CV a label first."; return; }
        try {
          const next = [...cvs];
          if (f) {
            if (f.type !== "application/pdf" || f.size > 5 * 1024 * 1024) { status.textContent = " A PDF up to 5 MB, please."; return; }
            const path = `cv${i + 1}.pdf`;
            const { error } = await state.src.sb.storage.from("cvs").upload(path, f, { upsert: true, contentType: "application/pdf" });
            if (error) throw new Error(error.message);
            next[i] = { label: name, path, uploaded_at: new Date().toISOString() };      // a new file: summarised again
          } else if (c.path) {
            next[i] = { ...c, label: name };                                            // only the label changed
          } else { status.textContent = " Choose a PDF."; return; }
          await state.src.saveProfile({ cvs: next.filter(Boolean), cv_names: next.filter(Boolean).map((x) => x.label) });
          p.cvs = next.filter(Boolean);
          status.textContent = " Saved. Ping reads it on the next check (Account > Check now) and then says which CV to apply with.";
        } catch (e) { status.textContent = ` ${e.message}`; }
      } }, c.path ? "Replace" : "Upload");
      return h("div", { class: "cv-slot" }, label, demo ? null : file, demo ? null : upload,
        c.summary ? h("div", { class: "small muted" }, c.summary) : c.path ? h("div", { class: "small muted" }, "Not read yet") : null);
    };
    return h("div", { class: "cvs" },
      h("p", { class: "hint", style: "margin:0" }, demo ? " Made-up CVs of the demo student (summaries only; the demo can't upload)."
        : " Up to 3 PDFs. Private: only your login can read them; Ping keeps a short summary to pick the CV for each role."),
      [0, 1, 2].map(slot), status);
  }

  // ------------------------------------------------------------ answers without AI
  // Used in demo mode and whenever the AI helper isn't reachable.
  function answerLocally(question, data) {
    const q = question.toLowerCase();
    const now = nowDate();
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
    if (/room|venue|where/.test(q)) {
      const hits = live.filter((i) => ["shortlist", "test", "result"].includes(i.category));
      if (!hits.length) return "No current tests for you.";
      return hits.map((i) => {
        const room = i.details?.pdf?.details?.room;
        const where = room ? `room ${room}` : i.pdf_status === "no" ? "you're not on its list"
          : "no room list yet (I'll post when it's out)";
        return `• ${i.title.replace(/\.$/, "")}: ${where}.`;
      }).join("\n");
    }
    if (/shortlist|test/.test(q)) {
      const hits = live.filter((i) => ["shortlist", "test", "result"].includes(i.category));
      return hits.length ? hits.map((i) => `• ${i.title}`).join("\n") : "No current shortlists or tests for you.";
    }
    if (mentioned.length) return mentioned.map((c) => live.filter((i) => i.company === c).map((i) => `• ${i.title}`).join("\n")
      || `Nothing current about ${c}.`).join("\n");
    const top = live.filter((i) => i.level === "always").slice(0, 3);
    return "I can answer things like “what's due tomorrow?”, “did I apply to X?”, “which room for the X test?”, " +
      "“what's the CTC at X?”." + (top.length ? "\n\nMost important right now:\n" + top.map((i) => `• ${i.title}`).join("\n") : "");
  }

  boot().catch((e) => mountPage(h("div", { class: "card" }, h("h1", {}, "Something went wrong"), h("p", {}, e.message))));
})();
