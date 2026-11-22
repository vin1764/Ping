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
  // company names for display only ("Auro Group(www.AuroIM.com)" -> "Auro Group"): dashboard/names.js
  const { cleanName, cleanRowText } = window.PingNames || { cleanName: (x) => String(x || ""), cleanRowText: (x) => String(x || "") };
  // web links, in-page links, and this site's own pages (setup.html); never javascript: or data:
  const safeUrl = (u) => (/^(https?:|#|mailto:|\?)/i.test(String(u)) || /^[a-z0-9-]+\.html$/i.test(String(u)) ? String(u) : "#");
  const mount = (...nodes) => { const app = $("#app"); app.replaceChildren(...nodes); };
  // every page but the chat: one centred column that scrolls (the chat scrolls its own thread)
  const mountPage = (...nodes) => { mount(h("div", { class: "page" }, ...nodes)); $("#app").scrollTop = 0; };
  const store = {  // per-browser conveniences only; every read/write may fail (private windows)
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } },
  };

  // ------------------------------------------------------------ dates (always IST)
  const dt = (v) => (v ? new Date(v) : null);
  // formatters made once (toLocale*String with options builds a new one on every call: slow on a phone)
  const F_DAY = new Intl.DateTimeFormat("en-CA", { timeZone: TZ });
  const F_HM = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
  const F_WD = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short" });
  const F_DM = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short" });
  const istDay = (d) => F_DAY.format(d);
  function when(v) {
    const d = dt(v);
    if (!d || isNaN(d)) return "";
    // always with the date, same as Ping's messages ("Sat 21 Nov 20:00")
    return `${F_WD.format(d)} ${F_DM.format(d)} ${F_HM.format(d)}`;
  }
  const clock = (v) => F_HM.format(dt(v));
  function dayLabel(v) {
    const d = dt(v), today = istDay(nowDate()), yest = istDay(new Date(nowDate() - 86400000));
    const k = istDay(d);
    if (k === today) return "Today";
    if (k === yest) return "Yesterday";
    return d.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }
  const money = (n, cur) => (n == null ? "—" : `${Number(n).toLocaleString("en-IN")} ${cur || ""}`.trim());

  // ------------------------------------------------------------ the installable app: an IndexedDB copy of the last
  // thread (read offline) and the messages sent while offline (asked when back online)
  const kv = (() => {
    let db = null;
    const open = () => db || (db = new Promise((ok, no) => {
      const r = indexedDB.open("ping", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("kv");
      r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error);
    }));
    const tx = async (mode, fn) => { const d = await open(); return new Promise((ok, no) => {
      const t = d.transaction("kv", mode), req = fn(t.objectStore("kv")); t.oncomplete = () => ok(req?.result); t.onerror = () => no(t.error); }); };
    return { get: (k) => tx("readonly", (s) => s.get(k)).catch(() => null), set: (k, v) => tx("readwrite", (s) => s.put(v, k)).catch(() => null) };
  })();
  // offline: the thread as it was when last loaded; reading works, sending queues
  class OfflineSource {
    constructor(snap) { this.s = snap; this.kind = snap.kind || "real"; this.demo = !!snap.demo; this.offline = true; }
    async load() { return this.s.data; }
    async chat() { return this.s.chat || []; }
    async readAt() { return this.s.readAt || null; }
    async setReadAt() {}
    async addChat() {}
    async ask() { const e = new TypeError("offline"); e.offline = true; throw e; }
    async notice() { return { notice: null }; }
    async checkNow() { throw new Error("You're offline: Check now works once you're back online."); }
  }
  const isNetErr = (e) => e && (e.offline || e instanceof TypeError || /Failed to fetch|NetworkError|Load failed/i.test(e.message || ""));
  // an error in plain words for the person reading it (DESIGN.md, Tone); the raw one goes to the console
  function plainly(e) {
    const m = String(e?.message || "");
    if (e) console.warn(e);
    if (isNetErr(e) || !navigator.onLine) return "No connection. Try again when you're back online.";
    if (e?.status === 401 || /jwt|expired|not authenticated|invalid claim/i.test(m)) return "Your sign-in has expired. Sign in again, then try once more.";
    if (/exceed|too large|payload/i.test(m)) return "That file is too big (5 MB at most).";
    if (/mime|content.?type/i.test(m)) return "Only PDF files can be uploaded.";
    if (e?.status === 429) return m;                     // the demo's question limit: already in plain words
    return "Something went wrong on Ping's side. Try again in a minute.";
  }

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
    async ask(q) { if (state.details) { state.startDetails?.(); await state.details; } return answerLocally(q, this.d); }
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
      const [items, roles, profile, runs, notices] = await Promise.all([
        this.q("items", (q) => q.order("first_seen", { ascending: true }).limit(3000)),
        this.q("roles", (q) => q.limit(2000)),
        this.q("profile"),
        this.q("runs", (q) => q.order("id", { ascending: false }).limit(30)),
        // the latest notices, one line each on Today (the full text is read when one is opened)
        this.sb.from("notices").select("notice_id,company,subject,notice_time,preview,kind:analysis->>kind,targets:analysis->targets,todos:analysis->todos").order("notice_time", { ascending: false }).limit(1000)
          .then((r) => r.data || [], () => []),
      ]);
      // the demo is a snapshot: its profile row carries the time it was taken
      return { items, roles, profile: profile[0] || {}, runs, notices,
               generated_at: this.demo ? profile[0]?.updated_at : undefined };
    }
    // live updates (see startLive): the latest runs, and the items again once a run has finished
    async liveRuns() { return this.q("runs", (q) => q.order("id", { ascending: false }).limit(30)); }
    async items() { return this.q("items", (q) => q.order("first_seen", { ascending: true }).limit(3000)); }
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
    // starts the Ping workflow; the function creates the run's row ("queued") and returns its id
    async checkNow() { return this.fn("check-now"); }
    async ask(q) {
      // the demo is a snapshot: "tomorrow" is the day after it, as everywhere else on the page
      const asOf = this.demo && state.asOf ? new Date(state.asOf).toISOString() : undefined;
      try {
        const out = await this.fn("ask-ping", { question: q, as_of: asOf });
        if (out.prefs_changed) state.prefsChanged = true;
        return out.answer;
      }
      catch (e) {
        if (e.status === 429) return `${e.message}\n\nMeanwhile, from the ERP data: ${answerLocally(q, state.data)}`;
        // short and plain: what happened, and that the answer below is still from the ERP data
        const why = e.status === 403 ? "this login can't ask Ping's assistant" : "Ping's assistant couldn't be reached";
        return answerLocally(q, state.data) + `\n\n(${why}, so this answer comes straight from the ERP data.)`;
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
  const state = { src: null, data: null, filter: "visible", companyQuery: "", chat: [], open: new Set(), asOf: null,
                  openedAt: Date.now(), held: [] };
  // The demo shows a snapshot: "now" starts when it was taken (so its deadlines don't all read "passed" a week later)
  // and moves on from there in real time, so its countdowns tick like the real ones.
  const nowDate = () => new Date(state.asOf ? state.asOf + (Date.now() - state.openedAt) : Date.now());
  const liveNow = () => nowDate().getTime();      // the clock runs are judged by (the demo's own, or the real one)
  window.PingNow = liveNow;                       // read-only, for the page checks (setup/live_page_test.py)

  async function boot() {
    if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
      navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(() => {});
      // a tapped notification: the worker asks this window to open the message
      navigator.serviceWorker.addEventListener("message", (e) => { if (e.data?.type === "open" && e.data.url) location.href = e.data.url; });
    }
    const params = new URLSearchParams(location.search);
    const wantDemo = params.has("demo") || location.hash === "#demo";
    const hasBackend = CFG.supabaseUrl && CFG.supabaseKey && window.supabase;
    if (wantDemo || !hasBackend) return startDemo(!hasBackend && !wantDemo);
    // no connection (or the library didn't load): the last-loaded thread, if there is one
    const snap = await kv.get("snap");
    if ((!navigator.onLine || !window.supabase) && snap) return startOffline(snap);
    migrateSession();
    const sb = authClient(AUTH_KEY);
    const owner = await restoreSession(sb, AUTH_KEY);
    if (owner === "ok") { keepSessionFresh(sb); return startReal(sb); }
    if (owner === "unreachable") return waitForServer(snap);
    // no owner session on this device: an anonymous demo session from before (the runners'), if it's still good
    if (await hasStored(DEMO_AUTH_KEY)) {
      const demo = authClient(DEMO_AUTH_KEY);
      if (await restoreSession(demo, DEMO_AUTH_KEY) === "ok") { keepSessionFresh(demo); return startReal(demo); }
    }
    return showLogin(sb);
  }

  // ------------------------------------------------------------ staying signed in
  // Sign in once and stay signed in, like a chat app: Supabase keeps a session (a short-lived access token and a
  // refresh token; never the password) in this device's localStorage under a fixed key, refreshes it before it
  // runs out, and again whenever the app comes back to the screen (phones suspend installed apps). An anonymous demo
  // session has its own key and its own client, so it can never replace or sign out the owner's session. Sign-outs
  // are for this device only.
  const AUTH_KEY = "ping-auth";
  const DEMO_AUTH_KEY = "ping-demo-auth";
  // Where the session lives: localStorage, and a second copy in IndexedDB. Refresh tokens are single-use, so a
  // refreshed session must reach storage: iPhone writes localStorage to disk lazily, and an installed app closed
  // right after a refresh can lose that write and wake up next time with a token the server has already replaced
  // (the auth log of 22 Nov: "Invalid Refresh Token: Refresh Token Not Found", then a password sign-in). IndexedDB
  // commits each write; reading takes whichever copy is newer.
  const sessionStore = (() => {
    let dbp = null;
    const db = () => dbp || (dbp = new Promise((res, rej) => {
      const r = indexedDB.open("ping-session", 1);
      r.onupgradeneeded = () => r.result.createObjectStore("kv");
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    }));
    const idb = async (mode, op) => {
      const d = await db();
      return new Promise((res, rej) => {
        const t = d.transaction("kv", mode);
        const req = op(t.objectStore("kv"));
        t.oncomplete = () => res(req?.result ?? null);
        t.onerror = t.onabort = () => rej(t.error);
      });
    };
    const newer = (a, b) => { const e = (v) => { try { return JSON.parse(v)?.expires_at || 0; } catch { return 0; } }; return e(b) > e(a) ? b : a; };
    return {
      async getItem(k) {
        let a = null, b = null;
        try { a = localStorage.getItem(k); } catch { /* blocked */ }
        try { b = await idb("readonly", (st) => st.get(k)); } catch { /* no IndexedDB */ }
        return a && b ? newer(a, b) : a || b || null;
      },
      async setItem(k, v) {
        try { localStorage.setItem(k, v); } catch { /* blocked */ }
        try { await idb("readwrite", (st) => st.put(v, k)); } catch { /* no IndexedDB */ }
      },
      async removeItem(k) {
        try { localStorage.removeItem(k); } catch { /* blocked */ }
        try { await idb("readwrite", (st) => st.delete(k)); } catch { /* no IndexedDB */ }
      },
    };
  })();
  const hasStored = async (key) => !!(await sessionStore.getItem(key));
  const clients = {};
  function authClient(key) {
    if (!clients[key]) clients[key] = window.supabase.createClient(CFG.supabaseUrl, CFG.supabaseKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: false, storage: sessionStore, storageKey: key },
    });
    return clients[key];
  }
  // sessions saved under supabase-js's default key by earlier versions: moved once, so the update signs nobody out
  function migrateSession() {
    try {
      const old = `sb-${new URL(CFG.supabaseUrl).hostname.split(".")[0]}-auth-token`;
      const v = localStorage.getItem(old);
      if (!v) return;
      const target = JSON.parse(v)?.user?.is_anonymous ? DEMO_AUTH_KEY : AUTH_KEY;
      if (!localStorage.getItem(target)) sessionStore.setItem(target, v);
      localStorage.removeItem(old);
    } catch { /* storage blocked: nothing to move */ }
  }
  const pause = (ms) => new Promise((r) => setTimeout(r, ms));
  // "ok": a usable session (refreshed if it had run out); "none": nothing stored, or the server refused it (only
  // then the sign-in screen); "unreachable": a session is stored but the server can't be reached yet (a phone
  // waking up): never the sign-in screen for that
  async function restoreSession(sb, key) {
    if (!(await hasStored(key))) return "none";
    for (let i = 0; i < 3; i++) {
      // supabase-js retries a refresh that can't reach the server for up to 30 s: after 6 s, say so instead
      let res;
      try { res = await Promise.race([sb.auth.getSession(), pause(6000).then(() => ({ slow: true }))]); }
      catch (e) { res = { error: e }; }
      if (res.data?.session && res.data.session.expires_at * 1000 > Date.now()) return "ok";
      if (!(await hasStored(key))) return "none";    // supabase-js drops a session the server refused
      if (res.slow) return "unreachable";
      await pause(700 * (i + 1));                    // a quick network error: the phone may still be waking up
    }
    return (await hasStored(key)) ? "unreachable" : "none";
  }
  // back on screen (unlocked, switched back to, restored from the back-forward cache) or back online: refresh now
  function keepSessionFresh(sb) {
    const wake = () => {
      if (document.visibilityState !== "visible") { sb.auth.stopAutoRefresh?.(); return; }
      sb.auth.startAutoRefresh?.();
      sb.auth.getSession().catch(() => {});        // refreshes a token that ran out while the app was away
    };
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("pageshow", (e) => { if (e.persisted) wake(); });
    window.addEventListener("online", wake);
  }
  // signed in, but the server can't be reached: the last-loaded thread if there is one, else a plain note that
  // tries again by itself; never the sign-in form
  function waitForServer(snap) {
    if (snap) return startOffline(snap);
    mountPage(h("div", { class: "login card", id: "reconnecting" },
      h("h1", {}, "Ping"),
      h("p", {}, "You're signed in, but Ping's server can't be reached right now. Trying again\u2026"),
      h("button", { type: "button", class: "btn", onclick: () => location.reload() }, "Try now")));
    const again = () => location.reload();
    window.addEventListener("online", again, { once: true });
    // the refresh supabase-js keeps trying: once it gets through, carry on
    authClient(AUTH_KEY).auth.onAuthStateChange((ev, session) => { if (session && (ev === "TOKEN_REFRESHED" || ev === "SIGNED_IN")) again(); });
    setTimeout(again, 20000);
  }

  // the published demo-data.json keeps each distinct "allowed departments" list once (dashboard/build.sh)
  function unpackDemo(d) {
    if (Array.isArray(d.allowed_lists)) for (const r of d.roles || []) if (typeof r.allowed === "number") r.allowed = d.allowed_lists[r.allowed];
    return d;
  }
  async function startDemo(noBackend) {
    const early = window.PING_DEMO_DATA && await window.PING_DEMO_DATA;      // started in the page's head
    window.PING_DEMO_DATA = null;
    const data = early || await (await fetch("demo-data.json", { cache: "no-store" })).json();
    state.src = new DemoSource(unpackDemo(data));
    // the roles' JD text, pay details and JD summaries: fetched once the chat is on screen, merged into the same role
    // objects; the role sheet and local answers wait for them (demoDetails)
    if (data.details_file) {
      let go; const started = new Promise((r) => { go = r; });
      state.details = started.then(() => fetch(data.details_file, { cache: "no-store" })).then((r) => r.json()).then((det) => {
        for (const r of data.roles || []) if (det[r.id]) Object.assign(r, det[r.id]);
      }).catch(() => {});
      state.startDetails = go;
    }
    $("#mode-badge").replaceChildren("Demo", h("span", { class: "long" }, DEMO_CHIP.replace(/^Demo/, "")));
    $("#mode-badge").title = "Anonymised snapshot of a real run, no login";
    $("#mode-badge").hidden = false;
    if (!noBackend) state.exit = { label: "Exit demo", run: () => { location.href = location.pathname; } };
    await afterStart();
    if (state.startDetails) requestAnimationFrame(() => setTimeout(state.startDetails, 0));   // after the first paint
  }

  async function startOffline(snap) {
    state.src = new OfflineSource(snap);
    state.offline = true;
    if (snap.demo) { $("#mode-badge").replaceChildren("Demo"); $("#mode-badge").hidden = false; }
    await afterStart();
    status(`Offline: your thread as of ${when(snap.savedAt)}. Messages you send wait until you're back online.`);
    window.addEventListener("online", () => location.reload(), { once: true });
  }

  async function startReal(sb) {
    let rpc;
    try { rpc = await sb.rpc("is_ping_owner"); } catch (e) { rpc = { error: e }; }
    if (rpc.error && isNetErr(rpc.error)) { const snap = await kv.get("snap"); if (snap) return startOffline(snap); }
    const { data: ok, error } = rpc;
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
        error ? h("p", { class: "muted small" }, plainly(error)) : null,
        h("button", { class: "btn", onclick: async () => { await sb.auth.signOut({ scope: "local" }); location.reload(); } }, "Sign out")));
      return;
    }
    state.src = new SupabaseSource(sb, demo);
    if (demo) {
      // "Demo — sample data, read-only"; the second part is hidden on narrow phones
      $("#mode-badge").replaceChildren("Demo", h("span", { class: "long" }, DEMO_CHIP.replace(/^Demo/, "")));
      $("#mode-badge").title = "Anonymised snapshot of a real run: real companies, a made-up student";
      $("#mode-badge").hidden = false;
    }
    // this device only: signing out on a laptop never signs the phone out (and a demo session is its own client)
    state.exit = { label: demo ? "Exit demo" : "Sign out", run: async () => { await sb.auth.signOut({ scope: "local" }); location.replace(location.pathname); } };
    await afterStart();
    // split the lists by the current marks once they arrive, but never while a question is waiting for its answer
    // drawn in place (live), never a full redraw: that would move the chat under someone reading it
    loadMarks().then(() => { if (state.marks?.size && !state.sending) applyLive(); });
  }

  async function afterStart() {
    try {
      state.data = await state.src.load();
      stampItems();
      state.chat = await state.src.chat();
      state.readAt = await state.src.readAt();
      if (state.src.kind !== "real") {
        const run = (state.data.runs || [])[0] || {};
        const snap = dt(state.data.generated_at || run.finished_at || run.started_at)?.getTime() || null;
        // the snapshot's minute, 48 s in: the demo's clock turns a minute a few seconds after it opens
        state.asOf = snap ? Math.floor(snap / 60000) * 60000 + 48000 : null;
        state.openedAt = Date.now();
        holdBackLastCheck(snap);
      }
    } catch (e) { mountPage(h("div", { class: "card" }, h("h1", {}, "Couldn't load your data"), h("p", {}, plainly(e)))); return; }
    if (!state.offline) store.set("ping-visits", Number(store.get("ping-visits", 0)) + 1);   // the install offer comes on the 2nd
    setupNav();
    showLastRun();
    await decideOnboarding();
    window.addEventListener("hashchange", route);
    route();
    if (state.offline) return;
    startLive();
    saveSnapshot();
    flushQueue();
    window.addEventListener("online", () => { status(""); flushQueue(); });
    window.addEventListener("offline", () => status("Offline: you can read your thread; messages you send wait until you're back online."));
  }

  // the copy of the thread the app opens offline (owner or demo session; the static ?demo=1 copy doesn't need one)
  let snapTimer = null;
  function saveSnapshot() {
    if (!state.data || state.offline || !state.src?.sb) return;
    clearTimeout(snapTimer);
    snapTimer = setTimeout(() => kv.set("snap", { kind: state.src.kind, demo: !!state.src.demo, data: state.data, chat: state.chat,
      readAt: state.readAt, asOf: state.asOf, savedAt: new Date().toISOString() }), 1500);
  }
  // messages written while offline, asked in order once the connection is back
  async function flushQueue() {
    const q = (await kv.get("queue")) || [];
    if (!q.length || state.offline || !navigator.onLine) return;
    await kv.set("queue", []);
    document.querySelectorAll(".msg.queued, .msg.offline-note").forEach((n) => n.remove());
    for (const m of q) {
      const input = $("#ask-input"), thread = $("#thread");
      if (!input || !thread) { await kv.set("queue", q.slice(q.indexOf(m))); return; }
      input.value = m.text;
      await send(input, thread.querySelector(".thread-inner"), thread, document.querySelector(".composer .send"));
    }
  }

  // The demo: the messages its snapshot's last check brought (first seen at the snapshot time) are held back, and the
  // demo's first Check now finds them, as that check did. Every later Check now finds nothing new.
  function holdBackLastCheck(snap) {
    if (!snap) return;
    const fresh = (it) => inChat(it) && Math.abs(dt(it.first_seen) - snap) < 120000;
    state.held = state.data.items.filter(fresh);
    state.data.items = withoutHeld(state.data.items);
  }
  const withoutHeld = (items) => (state.held.length ? items.filter((it) => !state.held.some((x) => x.id === it.id)) : items);

  // ------------------------------------------------------------ live updates (no reloads)
  // Supabase Realtime pushes new chat_messages and every change to runs. Row rules hold on the channel: a demo
  // session receives only its own chat rows and the demo's runs. Items change only when a run writes them, so they
  // are read again when a run finishes. On tab focus everything is read again (Realtime can drop while a laptop
  // sleeps); if the socket fails, the page polls: every 15 s while a run is going, every 60 s otherwise.
  const live = { ok: false, timer: null, syncing: false, newCount: 0, firstNew: null, syncJump: null, local: new Set(), channel: null };

  function startLive() {
    document.addEventListener("visibilitychange", () => { if (!document.hidden) sync(); });
    window.addEventListener("focus", () => sync());
    const sb = state.src.sb;
    if (!sb || !state.src.liveRuns) return;                      // the offline ?demo=1 copy: nothing to listen to
    live.channel = sb.channel("ping-live")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "chat_messages" }, (p) => onChat(p.new))
      .on("postgres_changes", { event: "*", schema: "public", table: "runs" }, (p) => onRun(p.new))
      .subscribe((st) => {
        const was = live.ok;
        live.ok = st === "SUBSCRIBED";
        document.body.dataset.live = live.ok ? "on" : "off";      // the live page test waits for this
        if (live.ok && !was) sync();                             // (re)connected: catch up on anything missed
        schedulePoll();
      });
    schedulePoll();
  }

  function schedulePoll() {
    clearTimeout(live.timer);
    if (live.ok || !state.src?.liveRuns) return;
    live.timer = setTimeout(sync, LIVE.pollEvery(!!LIVE.current(state.data.runs, liveNow())));
  }

  async function sync() {
    if (!state.src?.liveRuns || live.syncing || !state.data) return;
    live.syncing = true;
    try {
      const before = LIVE.lastFinished(state.data.runs)?.id;
      mergeRuns(await state.src.liveRuns(), true);
      const chat = await state.src.chat();
      for (const m of chat || []) addChatRow(m);
      if (LIVE.lastFinished(state.data.runs)?.id !== before) { state.data.items = withoutHeld(await state.src.items()); stampItems(); }
      applyLive();
    } catch { /* offline for a moment: the next poll or focus tries again */ }
    finally { live.syncing = false; schedulePoll(); }
  }

  function addChatRow(m) {
    if (!m?.role || !m.text || !m.created_at) return false;
    const k = msgKey(m.role, m.created_at);
    if (state.chat.some((x) => msgKey(x.role, x.created_at) === k && x.text === m.text)) return false;
    state.chat.push({ role: m.role, text: m.text, created_at: m.created_at });
    return true;
  }
  function onChat(row) { if (addChatRow(row)) applyLive(); }

  async function onRun(row) {
    if (!row?.id) return;
    const was = (state.data.runs || []).find((r) => r.id === row.id);
    const ended = ["done", "failed"].includes(row.stage) && (!was || !["done", "failed"].includes(was.stage));
    mergeRuns([row]);
    // a run that just finished: read its new messages first, so they arrive right after its "Done" line
    if (ended && row.stage === "done") { state.data.items = withoutHeld(await state.src.items().catch(() => state.data.items)); stampItems(); }
    if (ended && row.stage === "done" && Number(row.new_items) > 0) flash(`found ${row.new_items} new`);
    applyLive();
  }

  // runs, newest first; full=true replaces the list (keeping the demo's played-out checks)
  function mergeRuns(rows, full) {
    const byId = new Map((full ? (state.data.runs || []).filter((r) => live.local.has(r.id)) : state.data.runs || []).map((r) => [r.id, r]));
    for (const r of rows || []) byId.set(r.id, { ...(byId.get(r.id) || {}), ...r });
    const at = (r) => Math.max(Date.parse(r.requested_at || 0) || 0, Date.parse(r.started_at || 0) || 0, Date.parse(r.shown_at || 0) || 0);
    state.data.runs = [...byId.values()].sort((a, b) => at(b) - at(a) || String(b.id).localeCompare(String(a.id)));
    applyLive();
  }

  function markRead() {
    state.readAt = new Date().toISOString();
    state.src.setReadAt(state.readAt).catch(() => {});
  }

  // what changed, onto the page: the header, the buttons, and in the chat new bubbles at the bottom and changed
  // ones redrawn in place, never moving what you're reading
  function applyLive() {
    if (!state.data) return;
    saveSnapshot();
    showLastRun();
    renderToday();
    const page = location.hash.slice(1) || "chat";
    if (page === "chat" && !state.onb) liveRender();
    else navUnread(unreadOf(threadEntries()).unread.length);
  }

  function liveRender() {
    const thread = $("#thread"), inner = thread?.querySelector(".thread-inner");
    if (!inner || inner.classList.contains("onb")) return;
    const atBottom = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 80;
    const have = new Map([...inner.querySelectorAll("[data-key]")].map((n) => [n.dataset.key, n]));
    const added = [];
    keepPlace(thread, atBottom, () => {
      // only what the thread draws: older messages that aren't shown (Show earlier) stay out
      const entries = threadEntries().filter((e) => !state.threadFrom || dt(e.at) >= dt(state.threadFrom));
      // a check that joined a line of "nothing new" checks: its own bubble goes, the line above it updates
      const keys = new Set(entries.map(entryKey));
      for (const [k, n] of have) if (k.startsWith("run:") && !keys.has(k)) { n.remove(); have.delete(k); }
      for (const e of entries) {
        const k = entryKey(e), old = have.get(k);
        if (old) {
          if (old.dataset.sig !== entrySig(e)) old.replaceWith(renderEntry(e));
          continue;
        }
        const node = renderEntry(e);
        node.classList.add("enter");
        appendToday(inner, node);
        added.push(node);
      }
    });
    if (!added.length) return live.syncJump?.();
    if (atBottom) {                                   // at the bottom: follow along
      thread.scrollTop = thread.scrollHeight;
      markRead();
    } else {                                          // reading further up: say so, don't move
      if (!live.newCount) live.firstNew = added[0];
      live.newCount += added.filter((n) => !n.classList.contains("me")).length || 0;
    }
    live.syncJump?.();
  }

  // redraw without moving what's on screen: the first bubble you can see stays exactly where it is
  function keepPlace(thread, atBottom, fn) {
    if (atBottom) return fn();
    const top = thread.getBoundingClientRect().top;
    const anchor = [...thread.querySelectorAll("[data-key]")].find((n) => n.getBoundingClientRect().bottom > top);
    const key = anchor?.dataset.key, before = anchor?.getBoundingClientRect().top;
    fn();
    const now = key && thread.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (now) thread.scrollTop += now.getBoundingClientRect().top - before;
  }

  // ------------------------------------------------------------ first-run onboarding (dashboard/onboarding.js)
  const OB = window.PingOnboarding;
  const LIVE = window.PingLive;
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
    $("#check-now-top").hidden = false;
    document.querySelectorAll("[data-check-now]").forEach((b) => { b.onclick = () => checkNow(); });
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

  // Check now, as a process in the chat: a Ping message whose steps update in place (from the run's own row, live),
  // ending in "Done at 12:17 — 2 new items" or the reason it couldn't finish. The demo plays the same steps on its
  // sample snapshot.
  async function checkNow() {
    if (LIVE.current(state.data.runs, liveNow()) || state.starting) return;
    if ((location.hash || "#chat") !== "#chat") location.hash = "#chat";
    if (state.src.kind === "demo") return demoCheck();
    state.starting = true;
    updateCheckButtons();
    try {
      const out = await state.src.checkNow();
      if (out?.run_row && !state.data.runs.some((r) => r.id === out.run_row)) {
        mergeRuns([{ id: out.run_row, trigger: "manual", mode: "run", status: "queued", stage: "queued",
                     requested_at: new Date().toISOString() }]);
      } else if (!out?.run_row) status("Started a check. Its messages appear here as it goes.");
    } catch (e) {
      status(e.status === 404 ? "Check now isn't set up yet (see README)." : `Couldn't start a check. ${plainly(e)}`);
    } finally {
      state.starting = false;
      applyLive();
    }
  }

  function demoCheck() {
    const run = { id: `demo-${Date.now()}`, demo: true, trigger: "manual", mode: "run", status: "queued", stage: "queued",
                  requested_at: nowDate().toISOString(), shown_at: new Date(nowDate().getTime() + 1000).toISOString() };
    live.local.add(run.id);
    mergeRuns([run]);
    let i = 0;
    const step = () => {
      if (i < LIVE.DEMO_STAGES.length) {
        const [stage, ms] = LIVE.DEMO_STAGES[i++];
        Object.assign(run, { stage, status: stage === "queued" ? "queued" : "running" });
        if (stage !== "queued" && !run.started_at) run.started_at = nowDate().toISOString();
        mergeRuns([{ ...run }]);
        setTimeout(step, ms);
      } else {
        // what the snapshot's last check brought arrives now, after the "Done" line (later checks: nothing new)
        const found = state.held.splice(0);
        for (const it of found) it.first_seen = new Date(nowDate().getTime() + 2000).toISOString();
        if (found.length) state.data.items = [...state.data.items, ...found];
        Object.assign(run, { stage: "done", status: "ok", finished_at: nowDate().toISOString(), new_items: found.length });
        mergeRuns([{ ...run }]);
        stampItems();               // the demo's messages are current after its check: FACT answers stay in the page
        if (found.length) flash(`found ${found.length} new`);
      }
    };
    step();
  }

  // light / dark: follows the system unless you pick one (kept in this browser only)
  const themeNow = () => store.get("ping-theme", "system");
  function setTheme(t) {
    store.set("ping-theme", t);
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    else delete document.documentElement.dataset.theme;
  }

  // the header: "checking the ERP now…" while a run is going, else the last finished check. No banner for a failed
  // run: ERP hiccups are normal (Ping posts in the chat after 3 in a row, or at once if the ERP refuses the login).
  // Ping's presence, like a contact's: "checked 4 min ago" → "checking the ERP…" (dots, the avatar pulses) →
  // "found 2 new" (2 s, the avatar flashes) → back. From the runs table, live.
  function flash(text) { state.flash = { text, until: Date.now() + 2000 }; showLastRun(); setTimeout(showLastRun, 2050); }
  function agoText(t) {
    const m = Math.floor((liveNow() - t) / 60000);
    if (m < 1) return "checked just now";
    if (m < 60) return `checked ${m} min ago`;
    return istDay(new Date(t)) === istDay(nowDate()) ? `checked ${clock(t)}` : `checked ${when(t)}`;   // short: it fits a phone
  }
  function showLastRun() {
    const cur = LIVE.current(state.data.runs, liveNow());
    const last = LIVE.lastFinished(state.data.runs || []);
    const sub = $("#subtitle"), top = $("#presence");
    const fl = state.flash && state.flash.until > Date.now() ? state.flash.text : null;
    const mode = cur ? "checking" : fl ? "found" : "idle";
    // the next check lives here (not on Today): "checked 4 min ago · next 14:11"
    const next = !cur && !fl && TODAY ? TODAY.nextCheck(state.data.runs, state.data.profile, liveNow()) : null;
    const text = cur ? "checking the ERP" : fl || ((last ? agoText(dt(last.finished_at).getTime())
      : state.asOf ? `snapshot of ${clock(state.asOf)}` : "placement updates") + (next ? ` · next ${clock(new Date(next).toISOString())}` : ""));
    if (sub.textContent !== text) sub.textContent = text;
    sub.classList.toggle("dots", mode === "checking");
    if (top && top.dataset.state !== mode) top.dataset.state = mode;
    updateCheckButtons(cur);
  }

  // every Check now button (rail, header, Profile > Account): off while a run is going, with its step on it
  function updateCheckButtons(cur = LIVE.current(state.data.runs, liveNow())) {
    document.querySelectorAll("[data-check-now]").forEach((b) => {
      b.disabled = !!cur || !!state.starting;
      b.setAttribute("aria-busy", String(!!cur || !!state.starting));
      const label = b.querySelector(".check-label") || b;
      // the header's button (phones) is short; the rail and Profile > Account show the step too
      label.textContent = state.starting ? "Starting…" : b.id === "check-now-top" ? (cur ? "Checking…" : "Check now")
        : LIVE.buttonLabel(cur, liveNow());
    });
  }

  function status(text) { const el = $("#status"); el.textContent = text; el.hidden = !text; }

  const ANON_DEMO = new URLSearchParams(location.search).get("anon-demo") === "1";
  function showLogin(sb) {
    // a real form with the fields password managers know (iCloud Keychain, Google Password Manager): they offer to
    // save it once and fill it with Face ID or a fingerprint after that. Ping itself never stores the password.
    const email = h("input", { type: "email", name: "email", required: true, autocomplete: "username", inputmode: "email",
                               autocapitalize: "none", spellcheck: "false", placeholder: "you@example.com", id: "login-email" });
    const pw = h("input", { type: "password", name: "password", required: true, autocomplete: "current-password",
                            placeholder: "Password", id: "login-pw" });
    const msg = h("p", { class: "muted small", id: "login-msg", role: "status" });
    mountPage(h("form", { class: "login card", method: "post", action: "#chat", autocomplete: "on", onsubmit: async (e) => {
      e.preventDefault();
      msg.textContent = "Signing in…";
      const { error } = await sb.auth.signInWithPassword({ email: email.value.trim(), password: pw.value });
      if (error) { msg.textContent = /invalid login/i.test(error.message) ? "That email and password don't match. Try again." : plainly(error); return; }
      // Chrome (Android, desktop): ask its password manager to save the login now, so the next sign-in is one tap
      if (window.PasswordCredential && navigator.credentials?.store) {
        try { await navigator.credentials.store(new PasswordCredential({ id: email.value.trim(), password: pw.value, name: email.value.trim() })); } catch { /* declined or unsupported */ }
      }
      pw.value = "";
      keepSessionFresh(sb);
      startReal(sb);
    } },
      h("h1", {}, "Ping"),
      h("p", { class: "promise" }, "Your ERP, filtered for you, every hour."),
      h("p", { class: "who" }, "Sign in (the student this copy belongs to)"),
      h("label", {}, "Email", email),
      h("label", {}, "Password", pw),
      h("button", { class: "btn", type: "submit" }, "Sign in"),
      h("p", { class: "muted small center stay" }, "You'll stay signed in on this device."),
      msg,
      // the anonymous demo session: only for the checks and eval runners (Admin > live-page, ask-ping-page, evals),
      // which open the page with ?anon-demo=1; it's linked from nowhere, and reviewers sign in like the owner
      ANON_DEMO ? h("p", { class: "or" }, "or") : null,
      ANON_DEMO ? h("button", { type: "button", class: "btn demo", id: "view-demo", onclick: async (e) => {
        e.target.disabled = true;
        msg.textContent = "Opening the demo\u2026";
        const demo = authClient(DEMO_AUTH_KEY);          // its own session: never the owner's
        const { error } = await demo.auth.signInAnonymously();
        if (error) {
          // too many demo sign-ins this hour (or the sign-in service is down): the same snapshot, from this site's own
          // copy; only Ask Ping's open questions need the server there
          msg.textContent = "The live demo is busy right now, so opening the same snapshot from this page instead\u2026";
          setTimeout(() => { location.href = `${location.pathname}?demo=1#chat`; }, 1200);
          return;
        }
        msg.textContent = "";
        location.hash = "#chat";
        keepSessionFresh(demo);
        startReal(demo);
      } }, "Open the demo session") : null,
      h("p", { class: "center", style: "margin:0" }, h("a", { class: "own", href: "setup.html", id: "setup-link" }, "Set up Ping for yourself \u2192"))));
  }

  // ------------------------------------------------------------ router
  // Plain "#name" links: #chat (home), #feed, #companies, #profile, #co-<company>
  function route() {
    if (location.hash.startsWith("#m-")) {
      state.jumpItem = decodeURIComponent(location.hash.slice(3));
      history.replaceState(null, "", "#chat");
    }
    const hash = location.hash.slice(1) || "chat";
    const page = hash.startsWith("co-") ? "companies" : hash;
    document.body.classList.toggle("chat-on", page === "chat");
    document.body.classList.toggle("today-on", page === "today");
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
    renderToday();
    if (hash === "feed") return viewFeed();
    if (hash === "today") return viewToday();
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
        } catch (e) { onbSay(`Couldn't upload it. ${plainly(e)}`); }
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
    } catch (e) { o.log.push({ role: "ping", text: isNetErr(e) ? "Couldn't save that: no connection. Tap it again when you're back online." : "Couldn't save that. Tap it again, or Skip and tell me later.", at: new Date().toISOString() }); return viewOnboarding(); }
    if (res.useDemo) { state.onb = null; location.hash = "#chat"; return route(); }
    Object.assign(o.ctx, res.ctxPatch || {}, res.save);
    if (!state.src.demo) Object.assign(state.data.profile, res.save);
    if (res.askPing) {
      try {
        const out = await state.src.fn("ask-ping", { question: res.askPing });
        o.log.push({ role: "ping", text: out.answer, at: new Date().toISOString() });
        await loadMarks();
      } catch (e) { o.log.push({ role: "ping", text: "Couldn't save that just now. You can tell me later, any time.", at: new Date().toISOString() }); }
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
        stampItems();
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
    // a Check now (with its progress) and an hourly check that brought something new
    const runs = (state.data.runs || []).filter((r) => LIVE.inThread(r, liveNow()))
      .map((r) => ({ kind: "run", at: r.shown_at || r.requested_at || r.started_at, run: r }));
    const sorted = [...items, ...talk, ...runs].filter((e) => e.at).sort((a, b) =>
      dt(a.at) - dt(b.at) || (a.kind === "item" && b.kind === "item" ? String(a.it.sort_at || "").localeCompare(String(b.it.sort_at || "")) : 0));
    // checks in a row that found nothing: one thin line that updates in place, not a bubble each
    return LIVE.collapseQuiet(sorted, state.data.runs, liveNow());
  }

  function unreadOf(entries) {
    // first visit (or the demo): don't call two weeks of history "unread", only the last day
    const lastAt = entries.length ? dt(entries[entries.length - 1].at) : null;
    const readAt = state.readAt ? dt(state.readAt) : lastAt && new Date(lastAt - 86400000);
    // Ping's own messages (e.g. "couldn't reach the ERP") count as unread too, not your questions or its replies
    return { readAt, unread: entries.filter((e) => (e.kind === "item" || e.kind === "ping") && (!readAt || dt(e.at) > readAt)) };
  }

  const QUICK = [{ label: "What's due tonight?" }, { label: "Anything for me?" }, { label: "Which CV for …?", insert: "Which CV should I use for " },
                 { label: "My preferences", text: "What are my preferences?" }, { label: "Help", text: "help" }];
  const ICON_SEND = () => { const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path"); p.setAttribute("d", "M5 12h13M12 5l7 7-7 7");
    s.append(p); return s; };
  const sendButton = (disabled) => h("button", { class: "btn send", "aria-label": "Send", disabled }, ICON_SEND());

  // the thread draws its latest 60 messages (from the first unread one if that is earlier) and the rest on demand:
  // a phone shouldn't lay out 300 bubbles to show the last screenful
  const THREAD_WINDOW = 60;
  function viewChat() {
    const all = threadEntries();
    const { readAt, unread } = unreadOf(all);
    let cut = state.showAll ? 0 : Math.max(0, all.length - THREAD_WINDOW);
    if (unread.length) cut = Math.min(cut, all.indexOf(unread[0]));
    if (state.jumpItem) { const j = all.findIndex((e) => e.kind === "item" && e.it.id === state.jumpItem); if (j >= 0) cut = Math.min(cut, j); }
    const entries = all.slice(Math.max(0, cut));
    state.threadFrom = cut > 0 ? entries[0]?.at || null : null;
    const inner = h("div", { class: "thread-inner" });
    let group = null, lastDay = null, divider = null;
    const snapshot = state.asOf && h("p", { class: "note-line snapshot" }, "Demo: " +
      `an anonymised snapshot of a real run, shown as it was on ${when(state.asOf)}. Fake roll number, name and CGPA; ` +
      "other students and all real mail removed (the 4 mails marked \u201cvia email\u201d are made-up samples).");
    if (!all.length) inner.append(h("p", { class: "empty" }, "No messages yet. Ping posts here after its first check (about 10 minutes)."));
    if (cut > 0) inner.append(h("button", { type: "button", class: "pill-btn ghost earlier", onclick: () => {
      const first = entries[0] && entryKey(entries[0]);
      state.showAll = true;
      route();
      requestAnimationFrame(() => document.querySelector(`[data-key="${CSS.escape(first)}"]`)?.scrollIntoView({ block: "start" }));
    } }, `Show ${cut} earlier message${cut === 1 ? "" : "s"}`));
    for (const e of entries) {
      const day = dayLabel(e.at);
      // one section per day: its header sticks to the top while you scroll through that day
      if (day !== lastDay) { group = h("section", { class: "daygroup", "aria-label": day }, h("div", { class: "day" }, day)); inner.append(group); lastDay = day; }
      if (!divider && unread.length && e === unread[0]) {
        divider = h("div", { class: "unread", id: "unread" }, `${unread.length} new`);
        if (snapshot) group.append(snapshot);
        group.append(divider);
      }
      group.append(renderEntry(e));
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
      if (live.newCount && fromBottom < 80) {           // you've scrolled down to what arrived: it's read
        live.newCount = 0;
        live.firstNew = null;
        markRead();
      }
      if (live.newCount && live.firstNew?.isConnected) {
        jump.textContent = `↓ ${live.newCount} new`; jump.className = "pill-btn"; jump.hidden = false;
        const first = live.firstNew;
        jump.onclick = () => jumpTo(thread, first);
      } else if (divider && divider.getBoundingClientRect().top > tr.bottom - 8) {
        jump.textContent = `${unread.length} new ↓`; jump.className = "pill-btn"; jump.hidden = false;
        jump.onclick = () => jumpTo(thread, divider);
      } else if (fromBottom > thread.clientHeight) {
        jump.textContent = "Latest ↓"; jump.className = "pill-btn ghost"; jump.hidden = false;
        jump.onclick = () => jumpTo(thread, null);
      } else jump.hidden = true;
    };
    thread.addEventListener("scroll", syncJump, { passive: true });
    live.newCount = 0;
    live.firstNew = null;
    live.syncJump = syncJump;
    // open at the first unread message, otherwise at the bottom (the latest thing that happened)
    requestAnimationFrame(() => {
      const target = state.jumpItem && inner.querySelector(`[data-key="${CSS.escape(`item:${state.jumpItem}`)}"]`);
      state.jumpItem = null;
      if (target) { target.scrollIntoView({ block: "center" }); target.classList.add("hl"); }
      else if (divider) (snapshot || divider).scrollIntoView({ block: "start" });
      else thread.scrollTop = thread.scrollHeight;
      syncJump();
    });
    if (!offerInstall(inner)) offerPush(inner);
    const latest = entries.length ? entries[entries.length - 1].at : null;
    if (latest && (!readAt || dt(latest) > readAt)) {
      state.readAt = new Date(Math.max(dt(latest), Date.now())).toISOString();
      state.src.setReadAt(state.readAt).catch(() => {});
    }
    navUnread(0);
  }
  // "Install Ping": a Ping message from the second visit on. The button says "Install" only when the browser has
  // handed over its install dialog (beforeinstallprompt: Chrome/Edge on Android, Windows, Mac); otherwise the message
  // shows the steps for this device (docs/HELP.md, help.js). "Not now" hides it for 7 days; an install, for good.
  // Profile > Install Ping always has the same steps.
  const standalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const INSTALL_SNOOZE_DAYS = 7;
  const installHidden = () => {
    const v = store.get("ping-install", "");
    if (v === "installed") return true;
    return !!(v && v.snoozeUntil && Date.parse(v.snoozeUntil) > Date.now());
  };
  const snoozeInstall = () => store.set("ping-install", { snoozeUntil: new Date(Date.now() + INSTALL_SNOOZE_DAYS * 86400000).toISOString() });
  // a browser that can install sites at all: the dialog is here, or it's iPhone/iPad Safari, or Chrome/Edge/Samsung
  // on a desktop or Android (where the menu has "Install"); Firefox can't, so it isn't offered there
  const installable = () => !!state.installEvent || isIOS() ||
    (/android|windows|macintosh|cros|linux/i.test(navigator.userAgent) && /chrome|crios|edg|samsungbrowser/i.test(navigator.userAgent) && !/firefox|fxios/i.test(navigator.userAgent));
  const installSteps = () => {
    const help = window.PingHelp?.install;
    const plat = thisPlatform();
    return (help?.platforms?.[plat] || help?.platforms?.other || "Use your browser's menu: Install Ping.");
  };
  // the body of the install message and of Profile > Install Ping: the real button, or the steps for this device
  function installBody(onGone, { profile = false } = {}) {
    const box = h("div", { class: "install-body" });
    const draw = () => {
      if (standalone() || store.get("ping-install", "") === "installed") {
        box.replaceChildren(h("p", { class: "summary" }, "Installed: Ping opens like an app from your home screen, dock or Start menu."));
        return;
      }
      const ev = state.installEvent;
      const text = ev ? "Install me? I'll open like an app, straight to this chat, and work offline for what you've already seen."
        : `${profile ? "" : "Install me as an app: "}${installSteps()}`;
      const chips = h("div", { class: "chips wrap" },
        ev ? h("button", { type: "button", class: "chip primary", "data-install": "prompt", onclick: async () => {
          state.installEvent = null;                       // the dialog can be opened once per event
          try { ev.prompt(); } catch { draw(); return; }
          const { outcome } = await ev.userChoice.catch(() => ({}));
          if (outcome === "accepted") { store.set("ping-install", "installed"); if (onGone) onGone(); else draw(); }
          else draw();                                     // dismissed: the steps, since the button can't work again
        } }, "Install") : null,
        !profile ? h("button", { type: "button", class: "chip", "data-install": "later", onclick: () => { snoozeInstall(); onGone?.(); } }, "Not now") : null);
      box.replaceChildren(...[
        h(profile ? "p" : "span", { class: profile ? "summary" : "text" }, text),
        !ev && isIOS() ? h("img", { class: "ios-steps", src: "icons/ios-install.svg", alt: "Tap Share, then Add to Home Screen", width: 340, height: 150 }) : null,
        chips.children.length ? chips : null].filter(Boolean));
    };
    box.redraw = draw;
    draw();
    return box;
  }
  function offerInstall(inner) {
    if (standalone() || state.offline || Number(store.get("ping-visits", 0)) < 2 || installHidden() ||
        inner.querySelector(".install") || !installable()) return false;
    const at = new Date().toISOString();
    const bubble = h("div", { class: "msg ping sys install enter", role: "group", "aria-label": "Install Ping" },
      h("div", { class: "kicker" }, h("span", { class: "k" }, "Ping")),
      installBody(() => bubble.remove()),
      h("div", { class: "foot" }, h("span", { class: "time" }, clock(at))));
    appendToday(inner, bubble);
    return true;
  }
  // Profile > Install Ping: always there (until installed), so the steps are always findable
  function installCard() {
    return h("section", { class: "card pcard", id: "pc-install", "aria-labelledby": "pc-install-h" },
      h("div", { class: "pcard-head" }, h("h2", { id: "pc-install-h" }, "Install Ping")), installBody(null, { profile: true }));
  }

  // ------------------------------------------------------------ push notifications (docs/PUSH.md): the owner's own
  // devices only (a demo session can't subscribe; the database refuses it). On iPhone/iPad only once installed.
  const urlB64 = (b) => Uint8Array.from(atob((b + "=".repeat((4 - b.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
  const pushSupported = () => !!(CFG.pushKey && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window);
  const pushPossible = () => state.src?.kind === "real" && !state.offline && pushSupported() && (!isIOS() || standalone());
  async function pushSubscription() {
    try { return await (await navigator.serviceWorker.ready).pushManager.getSubscription(); } catch { return null; }
  }
  async function enablePush() {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return { ok: false, why: perm === "denied" ? "blocked" : "not now" };
    const reg = await navigator.serviceWorker.ready;
    const sub = (await reg.pushManager.getSubscription()) ||
      await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64(CFG.pushKey) });
    const j = sub.toJSON();
    const { error } = await state.src.sb.from("push_subscriptions").upsert({ endpoint: j.endpoint, p256dh: j.keys.p256dh,
      auth: j.keys.auth, user_agent: navigator.userAgent.slice(0, 200) });
    if (error) { await sub.unsubscribe().catch(() => {}); return { ok: false, why: plainly(error) }; }
    return { ok: true };
  }
  async function disablePush() {
    const sub = await pushSubscription();
    if (sub) { await state.src.sb.from("push_subscriptions").delete().eq("endpoint", sub.endpoint); await sub.unsubscribe().catch(() => {}); }
  }
  const quietText = () => { const p = state.data.profile || {}; return `${p.check_to || "01:00"}–${p.check_from || "06:00"}`; };
  // "Want me to notify you when something's for you?" once per device, never in the same visit as the install offer
  async function offerPush(inner) {
    if (!pushPossible() || Notification.permission !== "default" || store.get("ping-push-ask", "") || inner.querySelector(".push-ask")) return;
    if (await pushSubscription()) return;
    const at = new Date().toISOString();
    const text = h("span", { class: "text" }, `Want me to notify you when something's for you? At most one notification per check, never in your quiet hours (${quietText()}).`);
    const chips = h("div", { class: "chips wrap" },
      h("button", { type: "button", class: "chip primary", onclick: async () => {
        store.set("ping-push-ask", "yes");
        chips.replaceChildren();
        const r = await enablePush().catch((e) => ({ ok: false, why: plainly(e) }));
        text.textContent = r.ok ? "Done: this phone gets a notification when something's for you. Profile > Notifications to send a test or turn it off."
          : r.why === "blocked" ? "Your browser blocked notifications for Ping. You can allow them in its site settings, then turn them on in Profile."
          : r.why === "not now" ? "Notifications stay off for now. You can turn them on any time in Profile > Notifications."
          : `Notifications didn't turn on. ${r.why} You can try again in Profile > Notifications.`;
      } }, "Yes"),
      h("button", { type: "button", class: "chip", onclick: () => { store.set("ping-push-ask", "not now"); bubble.remove(); } }, "Not now"));
    const bubble = h("div", { class: "msg ping sys push-ask enter", role: "group", "aria-label": "Notifications" },
      h("div", { class: "kicker" }, h("span", { class: "k" }, "Ping")), text, chips,
      h("div", { class: "foot" }, h("span", { class: "time" }, clock(at))));
    appendToday(inner, bubble);
  }
  // Profile > Notifications: this device on or off, a test, and the optional email
  function pushCard(demo) {
    const p = state.data.profile || {};
    const line = h("p", { class: "summary" }, "…");
    const actions = h("div", { class: "actions" });
    const draw = async () => {
      if (demo) { line.textContent = "Notifications go to the owner's own phone: the demo can't turn them on."; return; }
      if (!pushSupported()) { line.textContent = CFG.pushKey ? "This browser can't receive notifications." : "Notifications aren't set up for this copy of Ping yet (Actions > Admin > push-setup)."; return; }
      if (isIOS() && !standalone()) { line.textContent = "On iPhone and iPad, add Ping to your Home Screen first (Share → Add to Home Screen), then open it from there."; return; }
      const sub = await pushSubscription();
      const perm = Notification.permission;
      line.textContent = sub ? `On for this device. At most one per check, plus test-day reminders; quiet ${quietText()}.`
        : perm === "denied" ? "Blocked for Ping in this browser's site settings." : "Off for this device.";
      actions.replaceChildren(
        sub ? h("button", { type: "button", class: "btn ghost", onclick: async () => { await disablePush(); draw(); } }, "Turn off")
            : perm !== "denied" ? h("button", { type: "button", class: "btn", onclick: async () => { await enablePush().catch(() => {}); draw(); } }, "Turn on") : null,
        sub ? h("button", { type: "button", class: "btn ghost", onclick: async (ev) => {
          ev.target.disabled = true;
          const r = await state.src.fn("send-push", { mode: "test" }).catch((e) => ({ error: plainly(e) }));
          line.textContent = r?.error ? `The test didn't go out. ${r.error}` : `Test sent to ${r.ok} of ${r.devices} device${r.devices === 1 ? "" : "s"}.`;
          ev.target.disabled = false;
        } }, "Send a test") : null);
    };
    draw();
    const mail = h("input", { type: "checkbox", id: "pf-email-digests", checked: !!p.email_digests, disabled: demo, onchange: async (ev) => {
      try { await state.src.saveProfile({ email_digests: ev.target.checked }); state.data.profile.email_digests = ev.target.checked; }
      catch (e) { ev.target.checked = !ev.target.checked; line.textContent = `Couldn't save. ${plainly(e)}`; }
    } });
    return h("section", { class: "card pcard", id: "pc-push", "aria-labelledby": "pc-push-h" },
      h("div", { class: "pcard-head" }, h("h2", { id: "pc-push-h" }, "Notifications")), line, actions,
      h("label", { class: "check" }, mail, "Also email me what's for you (off by default; the alert after 3 failed checks is emailed either way)"));
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.installEvent = e;
    // an install message or Profile card already showing the steps gets the real button now
    document.querySelectorAll(".install-body").forEach((b) => b.redraw?.());
    const inner = document.querySelector("#thread .thread-inner");
    if (inner) offerInstall(inner);
  });
  window.addEventListener("appinstalled", () => {
    store.set("ping-install", "installed");
    document.querySelector(".msg.install")?.remove();
    document.querySelectorAll(".install-body").forEach((b) => b.redraw?.());
  });

  const motion = () => (window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
  // to a message (or the bottom): smooth for a short way, at once for a long one (a long smooth scroll is slow)
  function jumpTo(thread, el) {
    const top = el ? thread.scrollTop + el.getBoundingClientRect().top - thread.getBoundingClientRect().top - 8 : thread.scrollHeight;
    const far = Math.abs(top - thread.scrollTop) > 3 * thread.clientHeight;
    thread.scrollTo({ top, behavior: far ? "auto" : motion() });
  }
  function navUnread(n) { const d = $("#nav-unread"); if (!d) return; d.textContent = n > 99 ? "99+" : String(n); d.hidden = !n;
    d.parentElement.setAttribute("aria-label", n ? `Chat, ${n} new` : "Chat"); }

  function textBubble(role, text, at, enter) {
    return h("div", { class: `msg ${role === "me" ? "me" : "ping"}${enter ? " enter" : ""}`, "data-key": msgKey(role, at), "data-sig": "1" },
      h("span", { class: "text" }, text), role === "me" ? null : rolesButton(text),
      h("div", { class: "foot" }, h("span", { class: "time" }, clock(at))));
  }

  // every bubble has a key (what it is) and a signature (what it shows), so live updates add what's new and
  // redraw only what changed, in place
  const msgKey = (role, at) => `msg:${role === "me" ? "me" : "ping"}:${Date.parse(at)}`;
  const itemSig = (it) => [retitle(it), it.level, it.done ? 1 : 0, it.details?.hidden_because || "", (it.details?.list || []).length,
                            (it.details?.list || []).length ? state.marksVersion || 0 : 0].join("|");
  const runSig = (r) => [r.stage, r.status, r.new_items, r.note, r.finished_at].join("|");
  function entryKey(e) { return e.kind === "item" ? `item:${e.it.id}` : e.kind === "run" ? `run:${e.run.id}` : e.kind === "quiet" ? e.key : msgKey(e.kind, e.at); }
  function entrySig(e) { return e.kind === "item" ? itemSig(e.it) : e.kind === "run" ? runSig(e.run) : e.kind === "quiet" ? `quiet|${e.line}` : "1"; }
  function renderEntry(e) {
    return e.kind === "item" ? itemBubble(e.it, e.at) : e.kind === "run" ? runBubble(e.run, e.at)
      : e.kind === "quiet" ? h("p", { class: "note-line sysline", role: "status", "data-key": e.key, "data-sig": entrySig(e) }, e.line)
      : textBubble(e.kind, e.text, e.at);
  }

  function runBubble(run, at) {
    const d = LIVE.describe(run, state.data.runs, liveNow());
    return h("div", { class: `msg ping run r-${d.state}`, "data-key": `run:${run.id}`, "data-sig": runSig(run),
                      role: d.state === "active" ? "status" : null },
      h("div", { class: "kicker" }, h("span", { class: "k" }, "Ping"), h("span", { class: "k2" }, d.kicker),
        d.state === "active" ? h("span", { class: "spin", "aria-hidden": "true" }) : null),
      h("span", { class: "text title" }, d.line),
      d.steps ? h("ol", { class: "steps", "aria-label": "Progress" },
        d.steps.map((st) => h("li", { class: `s-${st.state}`, "aria-current": st.state === "now" ? "step" : null }, st.label))) : null,
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
  // "in 1 h 48 m" / "in 42 m" / "over": amber under 3 h, red under 1 h; every chip ticks (tick() below)
  const TODAY = window.PingToday;
  const countdown = (at) => TODAY.countdown(at, liveNow()).text;
  const countPill = (at) => { const c = TODAY.countdown(at, liveNow());
    return h("span", { class: `pill cd c-${c.level}`, "data-due": dt(at).toISOString(), title: when(at) }, c.text); };
  function tick() {
    if (!state.data) return;
    const now = liveNow();
    for (const el of document.querySelectorAll("[data-due]")) {
      const c = TODAY.countdown(el.dataset.due, now);
      if (el.textContent !== c.text) el.textContent = c.text;
      const cls = `pill cd c-${c.level}`;
      if (el.className !== cls) el.className = cls;
    }
    showLastRun();
    const minute = Math.floor(now / 60000);
    if (minute !== state.tickMinute) { state.tickMinute = minute; renderToday(); }
  }
  setInterval(tick, 1000);
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
      : kind === "soon" ? (d.role === "reminder" || it.category === "reminder" || it.category === "digest" ? "Reminder" : "Deadline")
      : kind === "test" ? ({ shortlist: "Shortlist", result: "Result" }[it.category] || "Test")
      : kind === "new" ? "New" : d.todo?.action === "fill_form" ? "Form" : d.todo?.action === "take_test" ? "Test"
      : it.category === "offer" ? "Offer" : it.category === "ppt" ? "Talk" : "Update";
    const open = state.open.has(it.id);
    // placement mail: "via email" on a message only the mail has; "also mailed" on an ERP message the mail repeated;
    // a form / test / meeting link from the mail right on the message
    const viaMail = d.via === "email", mailed = !viaMail && d.mail?.note;
    const mlink = viaMail ? d.mail?.link || d.todo?.link : mailed ? d.mail?.link : null;
    const linkText = (u) => /forms\.gle|docs\.google\.com\/forms|forms\.office|typeform|jotform|\/forms\//i.test(u) ? "Open form ↗"
      : /meet\.google|zoom\.us|teams\.microsoft|webex|\/interview\//i.test(u) ? "Join ↗" : /hackerrank|hackerearth|mettl|codility|test|assess/i.test(u) ? "Open test ↗" : "Open link ↗";
    const bubble = h("div", { class: `msg ping item k-${kind}${past ? " past" : ""}${it.done ? " done" : ""}`, role: "button",
      tabindex: "0", "aria-expanded": String(open), "data-kind": kind, "data-key": `item:${it.id}`, "data-sig": itemSig(it) },
      h("div", { class: "kicker" }, h("span", { class: "k" }, label),
        !past && due && (kind === "soon" || kind === "test" || d.todo) ? countPill(due) : null,
        viaMail ? h("span", { class: "pill via", title: `From your mail: ${d.mail?.from || ""}` }, "via email") : null,
        mailed ? h("span", { class: "pill via", title: d.mail.subject || "" }, "also mailed to you") : null),
      h("span", { class: "text title" }, retitle(it)),
      listBlock(it),
      mlink && !past ? h("div", { class: "mail-link" }, h("a", { href: mlink, target: "_blank", rel: "noopener",
        onclick: (ev) => ev.stopPropagation() }, linkText(mlink))) : null,
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
      return h("div", { class: `li ${r.tag || ""}` }, h("span", { class: "rt" }, cleanRowText(r.text)),
        applied ? h("span", { class: "pill applied" }, "✓ applied") : null,
        r.note ? h("span", { class: "why" }, r.note) : null);
    };
    const groups = (d.list || []).map((g) => {
      const rows = (g.rows || []).map(row);
      if (g.collapsed && rows.length) {
        // "Show 33 more": the sheet with every role in this message (one place to act from)
        return h("div", { class: "grp more-rows" }, h("button", { type: "button", class: "linklike show-more", "aria-haspopup": "dialog",
          onclick: (ev) => { ev.stopPropagation(); openDigestSheet(it, d); } }, `Show ${rows.length} more ›`));
      }
      return h("div", { class: "grp" }, g.head ? h("div", { class: "gh" }, g.head) : null, rows);
    });
    return h("div", { class: "list" }, groups, d.note ? h("div", { class: "why" }, d.note) : null,
      d.source ? h("div", { class: "src" }, d.source) : null);
  }

  function openDigestSheet(it, d) {
    const ids = (d.list || []).flatMap((g) => (g.rows || []).map((r) => r.id)).filter(Boolean);
    const roles = [...new Set(ids)].map((id) => roleById().get(id)).filter(Boolean);
    const due = it.due_at ? +dt(it.due_at) : 0;
    const mine = roles.filter((r) => !r.applied && targetsOn() && markOf(r)?.relevant).length, applied = roles.filter((r) => r.applied).length;
    const title = due && roles.every((r) => +dt(deadlineOf(r)) === due)
      ? TODAY.sheetTitle({ n: roles.length, at: due, now: liveNow(), mine, applied })
      : [`${roles.length} roles`, mine ? `${mine} for you` : "", applied ? `${applied} applied` : ""].filter(Boolean).join(" · ");
    openActSheet({ title, sub: retitle(it), cards: roles.map((r) => roleCard(r, { chat: it.id })), filters: true });
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
    if (d.mail) lines.push(h("div", {}, h("strong", {}, d.via === "email" ? "From your mail: " : "Also mailed to you: "),
      [d.mail.subject, d.mail.from ? `from ${String(d.mail.from).replace(/<[^>]*>/g, "").trim()}` : "", d.mail.received_at ? when(d.mail.received_at) : ""]
        .filter(Boolean).join(" · ")));
    if (d.when_text && d.via === "email") lines.push(h("div", { class: "muted" }, `The mail says: ${d.when_text}`));
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
    if (state.offline || !navigator.onLine) return queueSend(q, input, inner, thread);
    input.value = "";
    state.waiting = true;
    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    btn.replaceChildren(h("span", { class: "wait", "aria-hidden": "true" }, "…"));
    const t0 = performance.now();
    const mine = { role: "me", text: q, created_at: new Date().toISOString() };
    // a FACT question: answered at once from the page's own data, no typing bubble (in the demo, once the roles'
    // details are in: they arrive within a second of opening)
    if (state.details) { state.startDetails?.(); await state.details; }
    const local = localFact(q);
    if (local.text) {
      state.chat.push(mine);
      appendToday(inner, textBubble("me", q, mine.created_at, true));
      const reply = { role: "ping", text: local.text, created_at: new Date(Math.max(Date.now(), Date.parse(mine.created_at) + 1)).toISOString() };
      state.chat.push(reply);
      const b = textBubble("ping", reply.text, reply.created_at, true);
      b.dataset.answeredBy = "page";
      b.dataset.ms = String(Math.round(performance.now() - t0));
      appendToday(inner, b);
      thread.scrollTop = thread.scrollHeight;
      state.waiting = false;
      btn.removeAttribute("aria-busy");
      btn.replaceChildren(ICON_SEND());
      btn.disabled = !input.value.trim();
      // saved the same way as an answer from the function: the question, then the reply
      state.src.addChat(mine).then(() => state.src.addChat(reply)).catch(() => {});
      return;
    }
    state.chat.push(mine);
    appendToday(inner, textBubble("me", q, mine.created_at, true));
    const wait = appendToday(inner, h("div", { class: "msg ping typing enter", role: "status", "aria-label": "Ping is typing" },
      h("span", { class: "dot" }), h("span", { class: "dot" }), h("span", { class: "dot" })));
    // a long answer never looks frozen: after 4 s the dots say so
    const slow = setTimeout(() => {
      if (!wait.isConnected) return;
      wait.setAttribute("aria-label", "Ping is still thinking");
      wait.append(h("span", { class: "thinking" }, "still thinking…"));
    }, 4000);
    thread.scrollTop = thread.scrollHeight;
    // saved before asking: Ask Ping reads the thread (for follow-ups like "nothing else?") from the database
    await state.src.addChat(mine).catch(() => {});
    let answer;
    state.sending = (state.sending || 0) + 1;
    // the typing bubble shows at least briefly, even for an answer that comes back at once
    const typing = new Promise((r) => setTimeout(r, 600));
    let lost = false, answeredBy = "page";
    try { answer = helpHere(q) ?? await state.src.ask(q); answeredBy = "server"; } catch (e) { if (isNetErr(e)) lost = true; answer = plainly(e); } finally { state.sending -= 1; }
    if (lost) {                                   // the connection went while asking: this one waits too
      clearTimeout(slow); wait.remove(); state.waiting = false; btn.removeAttribute("aria-busy"); btn.replaceChildren(ICON_SEND());
      state.chat = state.chat.filter((m) => m !== mine);
      inner.querySelector(`[data-key="${CSS.escape(msgKey("me", mine.created_at))}"]`)?.remove();
      return queueSend(q, input, inner, thread);
    }
    await typing;
    clearTimeout(slow);
    const reply = { role: "ping", text: answer || "I couldn't come up with an answer.", created_at: new Date().toISOString() };
    state.chat.push(reply);
    state.waiting = false;
    btn.removeAttribute("aria-busy");
    btn.replaceChildren(ICON_SEND());
    btn.disabled = !input.value.trim();
    if (wait.isConnected) {
      const b = textBubble("ping", reply.text, reply.created_at, true);
      b.dataset.answeredBy = answeredBy;
      b.dataset.ms = String(Math.round(performance.now() - t0));
      wait.replaceWith(b);
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

  async function queueSend(q, input, inner, thread) {
    input.value = "";
    const queue = (await kv.get("queue")) || [];
    queue.push({ text: q, at: new Date().toISOString() });
    await kv.set("queue", queue);
    const at = new Date().toISOString();
    appendToday(inner, h("div", { class: "msg me queued enter" }, h("span", { class: "text" }, q),
      h("div", { class: "foot" }, h("span", { class: "time" }, "waiting for a connection"))));
    if (!inner.querySelector(".offline-note")) {
      appendToday(inner, h("div", { class: "msg ping offline-note enter" }, h("div", { class: "kicker" }, h("span", { class: "k" }, "Ping")),
        h("span", { class: "text" }, "You're offline. I'll ask this as soon as you're back."), h("div", { class: "foot" }, h("span", { class: "time" }, clock(at)))));
    }
    thread.scrollTop = thread.scrollHeight;
  }

  async function loadMarks() {
    if (!state.src?.marks) return;
    try {
      const { prefs, marks } = await state.src.marks();
      state.marks = marks;
      state.marksVersion = (state.marksVersion || 0) + 1;     // the lists split differently: redraw them in place
      state.prefs = prefs;
      Object.assign(state.data.profile, { targets: prefs.targets, reminder_hours: prefs.reminder_hours,
                                          list_other_roles: prefs.list_other_roles });
    } catch { /* keep the lists as the last run built them */ }
  }

  // ------------------------------------------------------------ Today (dashboard/today.js builds it)
  const isMine = (r) => r.eligible !== false && (targetsOn() ? !!markOf(r)?.relevant : true);
  function todayModel() {
    return TODAY.build({ items: state.data.items.filter((it) => !it.dismissed), roles: state.data.roles,
      notices: state.data.notices || [], runs: state.data.runs, profile: state.data.profile, now: liveNow(), isMine, inChat });
  }
  function todayPanel(m) {
    const now = nowDate();
    const head = h("div", { class: "today-head" }, h("h2", {}, "Today"),
      h("span", { class: "muted small" }, now.toLocaleDateString("en-GB", { timeZone: TZ, weekday: "long", day: "numeric", month: "short" })));
    if (m.empty) return h("div", { class: "today" }, head, h("p", { class: "today-empty" }, m.emptyText), h("p", { class: "tomorrow" }, m.tomorrow.text));
    const row = (r) => {
      const status = [r.status === "on" ? h("span", { class: "pill you" }, "you're on the list")
        : r.status === "off" ? h("span", { class: "pill over" }, "not on the list") : null,
        r.via === "email" ? h("span", { class: "pill via" }, "via email") : null].filter(Boolean);
      const right = r.kind === "notice" || r.kind === "more" ? null : r.over ? h("span", { class: "pill cd c-over" }, "over")
        : r.due ? countPill(r.due) : null;
      const body = [h("span", { class: "t-title" }, r.title, status), r.sub ? h("span", { class: "t-sub" }, r.sub) : null,
                    r.names ? h("span", { class: "t-names" }, r.names) : null];
      // every row opens the sheet with everything in it ("5 forms due 20:00": one card per form)
      return h("button", { type: "button", class: `today-row k-${r.kind}${r.group ? " group" : ""}${r.over ? " over" : ""}`,
        "aria-haspopup": r.kind === "more" ? null : "dialog", onclick: () => openRowSheet(r) },
        h("span", { class: "t-ico", "aria-hidden": "true" }), h("span", { class: "t-body" }, body), right,
        r.kind === "more" ? null : h("span", { class: "t-caret", "aria-hidden": "true" }, "›"));
    };
    return h("div", { class: "today" }, head, h("div", { class: "today-list" }, m.rows.map(row)), h("p", { class: "tomorrow" }, m.tomorrow.text));
  }
  // a tap on Today: the chat message it came from, else the role, the notice or the company
  function goTo(t) {
    if (!t) return;
    if (t.item) {
      const show = () => {
        let n = document.querySelector(`[data-key="${CSS.escape(`item:${t.item}`)}"]`);
        if (!n && !state.showAll && $("#thread")) { state.showAll = true; route(); n = document.querySelector(`[data-key="${CSS.escape(`item:${t.item}`)}"]`); }
        const thread = $("#thread");
        if (!n || !thread) return;
        jumpTo(thread, n);
        n.classList.remove("hl"); void n.offsetWidth; n.classList.add("hl");
      };
      if ((location.hash || "#chat") !== "#chat") { location.hash = "#chat"; setTimeout(show, 80); } else show();
      return;
    }
    if (t.role) { const r = state.data.roles.find((x) => x.id === t.role); if (r) openRole(r); return; }
    if (t.notice) return openNotice(t.notice);
    if (t.company) { location.hash = companyHref(t.company); return; }
    if (t.feed) { location.hash = "#feed"; return; }
    if (t.companies) location.hash = "#companies";
  }
  function renderToday() {
    if (!state.data || !TODAY) return;
    const m = todayModel();
    const badge = $("#nav-today");
    if (badge) { badge.textContent = String(m.ahead); badge.hidden = !m.ahead;
      badge.parentElement.setAttribute("aria-label", m.ahead ? `Today, ${m.ahead} still ahead` : "Today"); }
    const rail = $("#today-rail");
    if (rail) rail.replaceChildren(todayPanel(m));
    const page = $("#today-page");
    if (page) page.replaceChildren(todayPanel(m));
  }
  function viewToday() {
    mountPage(h("div", { id: "today-page" }));
    renderToday();
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
      it.details?.via === "email" ? h("span", { class: "pill via" }, "via email") : it.details?.mail?.note ? h("span", { class: "pill via" }, "also mailed to you") : null,
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
    const links = d.mail_links?.length ? d.mail_links : it.category === "email" || d.via === "email" ? d.links || [] : [];
    return links.filter((u) => u !== d.todo?.link).slice(0, 2);
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
    try { await state.src.markItem(it.id, { done: it.done }); } catch (e) { status(`Couldn't save that. ${plainly(e)}`); }
    route();
  }

  async function fix(it, f) {
    try {
      await state.src.correct(it.details?.notice_key, f);
      status(state.src.kind === "demo" ? "Saved (demo only)." : "Saved. The next run will use your answer.");
      if (state.src.kind !== "demo") it.level = "hidden";
    } catch (e) { status(`Couldn't save that. ${plainly(e)}`); }
    route();
  }

  async function openNotice(noticeId) {
    const body = $("#modal-body");
    body.replaceChildren(h("p", { class: "muted" }, "Loading…"));
    $("#modal").showModal();
    let res;
    try { res = await state.src.notice(noticeId); } catch (e) { body.replaceChildren(h("p", {}, `Couldn't open the notice. ${plainly(e)}`)); return; }
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
      "aria-label": `${cleanName(r.company)}, ${r.designation}. Details` },
      h("span", { class: "co" }, cleanName(r.company)),
      h("span", { class: "ctc" }, ctcShort(r)),
      h("span", { class: "rn" }, r.designation),
      h("span", { class: "meta" },
        dl ? h("span", { class: "num" }, `${open ? "Closes" : "Closed"} ${when(dl)}`) : h("span", {}, "No deadline yet"),
        dl && open && !r.applied ? countPill(dl) : null,
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
      const match = (r) => !q || `${r.company} ${cleanName(r.company)} ${r.designation}`.toLowerCase().includes(q);
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

  // ------------------------------------------------------------ the detail sheet behind Today rows and lists
  // One place to act from: a Today row, a digest's "Show N more" and an Ask Ping answer that lists roles all open
  // this sheet, one card per company/role with what it is, when, where you stand, and links. Links only (Ping stays
  // read-only); the ERP and forms open in the browser, never inside the app; a link Ping doesn't know isn't shown.
  // Phones: full screen with a back arrow (the phone's own back closes it too); desktop: a side panel.
  const EXT = { target: "_blank", rel: "noopener noreferrer" };
  const myRoll = () => (state.src?.kind === "demo" || state.data?.profile?.is_sample ? null : state.data?.profile?.roll || null);
  const KIND_WORD = { application: "Application", form: "Form", submission: "CV submission", test: "Test", interview: "Interview",
                      shortlist: "Shortlist", notice: "Notice", "to-do": "To do" };
  const roleIn = (t) => (String(t || "").match(/\(([^)]+)\)/) || [])[1] || "";
  function roleCard(r, extra = {}) {
    const m = markOf(r), due = deadlineOf(r);
    return { role: r, company: cleanName(r.company), roleName: r.designation, due, at: due ? +dt(due) : 0, kind: "application",
             applied: !!r.applied, mine: targetsOn() ? !!m?.relevant : null, reason: m?.relevant ? m.reason || "" : "",
             cv: m?.relevant ? m.best_cv || "" : "", forms: [], noticeId: null, pdf: null, chat: null, ...extra };
  }
  function itemCardOf(it) {
    const d = it.details || {};
    const role = (it.role_ids || []).map((id) => roleById().get(id)).find(Boolean) || null;
    const st = d.pdf?.status || it.pdf_status || null;
    const kind = it.category === "test" || ["test", "test_rooms", "interview"].includes(d.kind) ? (d.kind === "interview" ? "interview" : "test")
      : it.category === "shortlist" || d.kind === "shortlist" ? "shortlist"
      : /fill the form/i.test(it.title || "") || d.todo?.action === "fill_form" ? "form"
      : /submi/i.test(`${it.title} ${d.subject || ""}`) ? "submission" : it.category === "todo" ? "to-do" : "notice";
    const row = d.pdf?.details || {}, m = role ? markOf(role) : null, due = it.due_at || it.event_at;
    return { item: it, role, company: cleanName(it.company), roleName: role?.designation || roleIn(it.title), due, at: due ? +dt(due) : 0, kind,
             applied: role ? !!role.applied : null, list: st === "yes" ? "on" : st === "no" ? "off" : null, done: !!it.done,
             mine: role && targetsOn() ? !!m?.relevant : null, reason: m?.relevant ? m.reason || "" : "", cv: m?.relevant ? m.best_cv || "" : "",
             place: [row.room ? `Room ${row.room}` : "", row.slot ? `Slot ${row.slot}` : "", !row.room && d.venue ? d.venue : ""].filter(Boolean).join(" · "),
             myRow: d.pdf?.my_row ? (d.pdf.header ? d.pdf.header.map((x, i) => `${x}: ${d.pdf.my_row[i] ?? ""}`) : d.pdf.my_row).join(" · ") : "",
             forms: TODAY.formLinks(it), noticeId: it.notice_id || null, pdf: it.notice_id && st ? it : null, chat: inChat(it) ? it.id : null };
  }
  function sheetCard(c) {
    const status = c.list === "on" ? h("span", { class: "pill you" }, "on the list") : c.list === "off" ? h("span", { class: "pill over" }, "not on the list")
      : c.applied === true ? h("span", { class: "pill applied" }, "✓ applied") : c.applied === false ? h("span", { class: "pill plain" }, "not applied") : null;
    const fit = c.mine === true ? h("span", { class: "pill you" }, "For you") : c.mine === false ? h("span", { class: "pill plain" }, "Other") : null;
    const erp = c.role || c.kind === "application" ? TODAY.erpLink(c.role || { company: c.company }, myRoll()) : null;
    const pastDue = c.due && c.at <= liveNow();
    const links = [
      erp ? h("a", { class: "act-btn", href: erp.href, ...EXT, "data-link": "erp",
        title: erp.direct ? "The role's page on the ERP, in your browser" : `On the ERP: CDC › Application of Placement/Internship, search “${erp.search}”` }, "Open on ERP") : null,
      ...c.forms.map((u, k) => h("a", { class: "act-btn", href: u, ...EXT, "data-link": "form" }, c.forms.length > 1 ? `Form link ${k + 1}` : "Form link")),
      c.pdf ? Object.assign(pdfLink(c.pdf), { className: "act-btn" }) : null,
      c.noticeId ? h("button", { type: "button", class: "act-btn", "data-link": "notice", onclick: () => openNotice(c.noticeId) }, "Notice") : null,
      c.chat ? h("button", { type: "button", class: "act-btn", "data-link": "chat", onclick: () => { closeSheet(); goTo({ item: c.chat }); } }, "Show in chat") : null,
    ].filter(Boolean);
    return h("article", { class: `act-card${c.mine === false && !c.applied ? " other" : ""}`, "data-kind": c.kind },
      h("div", { class: "ac-head" }, h("strong", { class: "co" }, c.company || "Notice"), c.roleName ? h("span", { class: "rn" }, c.roleName) : null),
      h("div", { class: "ac-meta" }, h("span", { class: "kind" }, KIND_WORD[c.kind] || c.kind),
        c.due ? h("span", { class: "num" }, when(c.due)) : null,
        c.due ? (pastDue ? h("span", { class: "pill cd c-over" }, "over") : countPill(c.due)) : null, status, fit,
        c.done ? h("span", { class: "pill applied" }, "✓ done") : null),
      c.place ? h("div", { class: "ac-line" }, c.place) : null,
      c.myRow ? h("div", { class: "ac-line" }, h("strong", {}, "Your row: "), c.myRow) : null,
      c.text ? h("div", { class: "ac-line" }, c.text) : null,
      c.reason ? h("div", { class: "ac-why" }, c.reason) : null,
      c.cv ? h("div", { class: "ac-line" }, "Apply with: ", h("strong", {}, c.cv)) : null,
      links.length ? h("div", { class: "ac-links" }, links) : null);
  }
  // open and close: the phone's back gesture closes the sheet (a history entry while it's open)
  function showSheet(sheet) {
    if (!sheet.dataset.wired) {
      sheet.dataset.wired = "1";
      sheet.addEventListener("click", (ev) => { if (ev.target === sheet) sheet.close(); });   // a tap on the backdrop
      sheet.addEventListener("close", () => { if (history.state?.pingSheet) { state.sheetPopping = true; history.back(); } });
      window.addEventListener("popstate", () => {
        if (state.sheetPopping) { state.sheetPopping = false; return; }
        if (sheet.open) { history.replaceState(null, ""); sheet.close(); }
      });
    }
    if (!sheet.open) { if (!history.state?.pingSheet) history.pushState({ pingSheet: 1 }, ""); sheet.showModal(); }
    sheet.scrollTop = 0;
  }
  const closeSheet = () => { const s = $("#sheet"); if (s?.open) s.close(); };
  function openActSheet({ title, sub = "", cards, filters = false, note = "" }) {
    if (state.details && !state.detailsIn) {           // the demo's JD and pay details: fetched after the first paint
      state.startDetails?.();
      state.details.then(() => { state.detailsIn = true; openActSheet({ title, sub, cards, filters, note }); });
      return;
    }
    const sheet = $("#sheet");
    let filter = "all";
    const body = h("div", { class: "sheet-body act-body" });
    const chip = (key, label) => h("button", { type: "button", class: "chip", "aria-pressed": String(filter === key), "data-filter": key,
      onclick: () => { filter = key; draw(); } }, label, h("span", { class: "n" }, TODAY.filterCards(cards, key).length));
    const draw = () => {
      const { top, others } = TODAY.orderCards(filters ? TODAY.filterCards(cards, filter) : cards);
      body.replaceChildren(...[
        filters ? h("div", { class: "chips filters", role: "group", "aria-label": "Show" },
          chip("notapplied", "Not applied"), chip("foryou", "For you"), chip("all", "All")) : null,
        top.length ? h("div", { class: "act-list" }, top.map(sheetCard)) : null,
        others.length ? h("details", { class: "act-others" }, h("summary", {}, `Others (${others.length})`),
          h("div", { class: "act-list" }, others.map(sheetCard))) : null,
        !top.length && !others.length ? h("p", { class: "muted" }, "Nothing here with this filter.") : null,
        h("p", { class: "muted small act-note" }, note || (myRoll()
          ? "“Open on ERP” opens the role's page in your browser; sign in to the ERP there if it asks. Ping only reads the ERP: you apply there."
          : "“Open on ERP” opens the ERP in your browser: CDC › Application of Placement/Internship, then search for the company. Ping only reads the ERP: you apply there.")),
      ].filter(Boolean));
    };
    const close = h("button", { type: "button", class: "close", "aria-label": "Close", onclick: () => sheet.close() }, "×");
    const back = h("button", { type: "button", class: "back", "aria-label": "Back", onclick: () => sheet.close() }, "←");
    sheet.classList.add("act");
    sheet.replaceChildren(
      h("div", { class: "sheet-head" }, back, h("div", { class: "act-titles" }, h("h2", { id: "sheet-title", class: "co" }, title),
        sub ? h("div", { class: "rn small" }, sub) : null), close), body);
    draw();
    showSheet(sheet);
    (matchMedia("(max-width: 899px)").matches ? back : close).focus();
  }
  // what each Today row opens
  function openRowSheet(r) {
    const items = (r.itemIds || []).map((id) => state.data.items.find((i) => i.id === id)).filter(Boolean);
    if (r.kind === "deadline") {
      const roles = (r.roleIds || []).map((id) => roleById().get(id)).filter(Boolean);
      return openActSheet({ title: TODAY.sheetTitle({ n: roles.length, at: r.at, now: liveNow(), mine: r.mine, applied: r.applied }),
        cards: roles.map((x) => roleCard(x, { chat: r.digestId })), filters: true });
    }
    if (r.kind === "todo" || r.kind === "test") {
      const cards = items.map(itemCardOf);
      const done = cards.filter((c) => c.done).length;
      return openActSheet({ title: r.title, sub: [r.group ? clock(r.due) : r.sub, done ? `${done} done` : ""].filter(Boolean).join(" · "), cards,
        filters: cards.length > 3 });
    }
    if (r.kind === "notice") {
      const n = (state.data.notices || []).find((x) => (x.notice_id ?? x.id) === r.noticeId) || {};
      const it = items[0] || null;
      const base = it ? itemCardOf(it) : { company: cleanName(n.company), kind: "notice", forms: [], noticeId: r.noticeId };
      const names = r.companies || [];
      const roles = names.length ? state.data.roles.filter((x) => names.some((nm) => cleanName(x.company).toLowerCase().startsWith(nm.toLowerCase())
        || nm.toLowerCase().startsWith(cleanName(x.company).toLowerCase())) && (x.applied || isOpen(x))) : [];
      const cards = roles.length ? roles.map((x) => roleCard(x, { kind: "application", forms: base.forms, noticeId: r.noticeId, chat: base.chat || null }))
        : [{ ...base, text: base.kind === "notice" ? (n.preview || "").slice(0, 220) : "", noticeId: r.noticeId }];
      return openActSheet({ title: r.title, sub: [r.sub, r.names].filter(Boolean).join(" · "), cards, filters: roles.length > 3 });
    }
    return goTo(r.target);
  }
  // the roles an Ask Ping answer lists ("- Company — Role (apply with …)"), to open them in the sheet
  const norm = (s) => cleanName(s).toLowerCase().replace(/[^a-z0-9]+/g, "");
  function rolesIn(text) {
    if (!state.data?.roles?.length) return [];
    const out = [];
    for (const line of String(text || "").split("\n")) {
      const m = line.match(/^\s*[-•]\s*(.+?)\s+—\s+(.+?)(?:\s+\(apply with[^)]*\)|\s+✓ applied)?\s*$/);
      if (!m) continue;
      const co = norm(m[1]), rn = m[2].trim().toLowerCase();
      const r = state.data.roles.find((x) => String(x.designation || "").trim().toLowerCase() === rn
        && (norm(x.company).startsWith(co) || co.startsWith(norm(x.company))));
      if (r && !out.includes(r)) out.push(r);
    }
    return out;
  }
  function rolesButton(text) {
    const roles = rolesIn(text);
    if (roles.length < 2) return null;
    return h("button", { type: "button", class: "linklike open-roles", onclick: (ev) => { ev.stopPropagation();
      openActSheet({ title: `${roles.length} roles from this answer`, sub: [`${roles.filter((x) => !x.applied && targetsOn() && markOf(x)?.relevant).length} for you`,
        `${roles.filter((x) => x.applied).length} applied`].join(" · "), cards: roles.map((x) => roleCard(x)), filters: true }); } },
      `Open these ${roles.length} roles`);
  }

  // the role sheet: everything Ping knows about one role (a bottom sheet on phones, a side panel on desktop)
  function openRole(r) {
    if (state.details && !state.detailsIn) {           // the demo's JD and pay details: fetched after the first paint
      state.startDetails?.();
      state.details.then(() => { state.detailsIn = true; openRole(r); });
      return;
    }
    const sheet = $("#sheet");
    const kv = (rows) => { rows = rows.filter(([, v]) => v != null && v !== "" && v !== false);
      return rows.length ? h("dl", { class: "kv" }, rows.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)])) : null; };
    const sec = (title, ...body) => { const b = body.flat().filter(Boolean); return b.length ? h("section", {}, h("h3", {}, title), b) : null; };
    const f = Object.fromEntries(Object.entries(r.more_details?.fields || {}).map(([k, v]) => [k, typeof v === "string" ? tidyText(v) : v]));
    const pay = Object.entries(f).filter(([k, v]) => v && /ctc|salary|gross|base|stipend|bonus|esop|joining|relocation|bond|variable|retention/i.test(k)
      && String(v).length < 400);
    const e = r.eligibility || {}, mk = markOf(r), dl = deadlineOf(r);
    const updates = state.data.items.filter((i) => i.company === r.company && !i.dismissed).sort(sortNewest).slice(0, 8);
    const depts = new Set((r.allowed || []).map((a) => a.department));
    const close = h("button", { type: "button", class: "close", "aria-label": "Close", onclick: () => sheet.close() }, "×");
    sheet.replaceChildren(
      h("div", { class: "sheet-head" }, h("div", {}, h("h2", { id: "sheet-title", class: "co" }, cleanName(r.company)),
        h("div", { class: "rn" }, r.designation)), close),
      h("div", { class: "sheet-body" },
        h("div", { class: "chips wrap", style: "padding:0" },
          r.applied ? h("span", { class: "pill applied" }, "✓ applied") : null,
          targetsOn() && mk?.relevant ? h("span", { class: "pill you" }, "For you") : null,
          dl && isOpen(r) && !r.applied ? countPill(dl, "soon") : null,
          r.eligible === true ? h("span", { class: "pill you" }, "Eligible") : r.eligible === false ? h("span", { class: "pill no" }, "Not eligible")
            : h("span", { class: "pill over" }, "Eligibility not sure")),
        sec("Why it's for you", mk?.relevant && mk.reason ? h("p", { style: "margin:0" }, mk.reason) : null,
          bestCv(r) ? h("p", { style: "margin:0" }, "Apply with ", h("strong", {}, bestCv(r))) : null),
        jdSection(r, kv, sec),
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
        null,
        sec("Source", h("p", { class: "muted small", style: "margin:0" },
          `The ERP's companies list${r.last_seen ? `, last read ${when(r.last_seen)}` : ""}. Ping only reads the ERP: apply there. `),
          h("a", { href: companyHref(r.company), onclick: () => sheet.close() }, `All roles at ${cleanName(r.company)}`))));
    sheet.classList.remove("act");
    showSheet(sheet);
    close.focus();
  }

  // ERP / PDF text as fonts can draw it: Windows-1252 bullets and quotes, Symbol/Wingdings bullets (U+F0B7...), boxes
  // and arrows used as bullets become "•"; zero-width marks go (the same as ping/jd.py glyphs(), for text stored
  // before that clean-up and for the role's other fields)
  const C1 = { "\x95": "•", "\x96": "–", "\x97": "—", "\x91": "'", "\x92": "'", "\x93": '"', "\x94": '"', "\x85": "…" };
  const BULLETISH = "[\\ue000-\\uf8ff\\u25a0-\\u25ff\\u2794-\\u27bf\\u2219\\u2023\\u2043\\u2b9a-\\u2b9f\\u2713\\u2714\\u2756]";
  function tidyText(t) {
    return String(t || "").replace(/[\x80-\x9f]/g, (c) => C1[c] || "").replace(/[\u200b-\u200f\u2060-\u2064\ufeff\u00ad]/g, "")
      .replace(/\u00a0/g, " ").replace(new RegExp(`(^|\\n)[ \\t]*${BULLETISH}+[ \\t]*`, "g"), "$1• ")
      .replace(new RegExp(`[ \\t]*${BULLETISH}+[ \\t]*(?=\\S)`, "g"), " • ").replace(new RegExp(BULLETISH, "g"), "").replace(/\ufffd/g, "");
  }
  // the JD: Ping's short summary of it (roles.jd_summary), the full text behind "Full JD", and where it came from
  function jdSection(r, kv, sec) {
    const s = r.jd_summary, text = tidyText(r.jd_text || r.job_description || "");
    const one = (v) => (Array.isArray(v) ? v.filter(Boolean).join("; ") : v ? String(v) : "");
    const linkShut = r.jd_source === "link-unreadable" || (r.jd_source === "detail" && r.jd_url);
    const from = { attachment: "the JD file on the ERP", link: "the JD link", detail: "the ERP's role details", inline: "the ERP's job description" }[r.jd_source];
    const srcLink = r.jd_url ? h("a", { href: r.jd_url, target: "_blank", rel: "noopener",
      title: r.jd_source === "attachment" ? "Opens on the ERP; you need to be logged in to the ERP in this browser" : null },
      r.jd_source === "attachment" ? "Open the JD file on the ERP" : linkShut ? "The full JD link (Ping couldn't open it)" : "Open the JD link") : null;
    const body = [];
    if (r.jd_source === "link-unreadable") {
      body.push(h("p", { style: "margin:0" }, "The JD is a link Ping can't open (private or gone). "), srcLink);
    } else if (s) {
      const team = one(s.role_team);
      if (team && team.toLowerCase() !== String(r.designation || "").toLowerCase()) body.push(h("p", { style: "margin:0", class: "jd-role" }, team));
      if ((s.do || []).length) body.push(h("ul", { class: "jd-list" }, s.do.map((x) => h("li", {}, x))));
      body.push(kv([["Must-have", (s.must_have || []).join("; ")], ["Location", one(s.location)],
                    ["Eligibility", one(s.eligibility) || (r.cgpa_cutoff ? `CG cut-off ${r.cgpa_cutoff} (ERP)` : "")],
                    ["Unusual", (s.unusual || []).join("; ")]]));
    } else if (!text.trim() || r.jd_source === "none") {
      body.push(h("p", { class: "muted small", style: "margin:0" }, `No JD on the ERP${r.jd_note ? ` (${r.jd_note})` : ""}.`));
    }
    if (text.trim() && r.jd_source !== "link-unreadable") {
      body.push(h("details", { class: "jd-full" }, h("summary", { class: "linklike" }, "Full JD"),
        h("pre", { class: "notice" }, text.slice(0, 20000))));
    }
    if (from || srcLink) body.push(h("p", { class: "muted small", style: "margin:0" }, from ? `From ${from}. ` : "", r.jd_source !== "link-unreadable" ? srcLink : null));
    return sec("Job description", body);
  }

  function viewCompany(name) {
    const roles = sortRoles([...(byCompany().get(name) || [])], "all");
    const items = state.data.items.filter((i) => i.company === name && i.level !== "hidden").sort(sortNewest);
    mountPage(
      h("p", { class: "page-links" }, h("a", { href: "#companies" }, "← Companies")),
      h("h1", {}, name ? cleanName(name) : "Not found"),
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
              const out = await state.src.fn("ask-ping", { question: `my targets are ${patch.targets}` }).catch((e) => ({ answer: `Saved. Marking the roles didn't work just now (${plainly(e).replace(/\.$/, "").toLowerCase()}); the next check marks them.` }));
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
    const checkBtn = h("button", { type: "button", class: "btn ghost", id: "account-check", "data-check-now": true,
      onclick: () => checkNow() }, h("span", { class: "check-label" }, "Check now"));
    const account = h("section", { class: "card pcard", id: "pc-account", "aria-labelledby": "pc-account-h" },
      h("div", { class: "pcard-head" }, h("h2", { id: "pc-account-h" }, "Account")),
      kv([["Signed in as", demo ? "Demo visitor (anonymous, read-only)" : "The owner"], ["Last check", run ? when(run.finished_at || run.started_at) : "Not yet"]]),
      h("div", { class: "actions" }, checkBtn, h("a", { class: "btn ghost", href: "#feed" }, "All updates"),
        state.exit ? h("button", { type: "button", class: "btn ghost", id: "sign-out", onclick: () => state.exit.run() }, state.exit.label) : null),
      h("div", {}, h("div", { class: "hint", style: "margin-bottom:4px" }, "Theme"), themeChips));

    mountPage(h("h1", {}, "Profile"), h("p", { class: "lede" },
      "Whether you applied comes from the ERP's companies list, not from here. Ping only reads the ERP."),
      h("div", { class: "pcards" }, about, looking, cvs, sched, pushCard(demo), installCard(), account));
    updateCheckButtons();
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
        } catch (e) { status.textContent = ` Couldn't upload it. ${plainly(e)}`; }
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
  // Used in the offline ?demo=1 copy and whenever the ask-ping function can't be reached. The same rules the
  // function uses when Gemini is busy (supabase/functions/_shared/answer_rules.js, loaded as window.PingRules):
  // a company in the question gets an answer about that company only; otherwise what was asked about.
  const thisPlatform = () => window.PingRules?.platformOf(navigator.userAgent, navigator.maxTouchPoints) || "other";
  // "how do I install?", "help": answered here from docs/HELP.md (help.js), for this device, with no server call
  function helpHere(question) {
    const R = window.PingRules;
    if (!R?.helpTopic(question)) return null;
    const data = state.data || {};
    const r = R.route(question, [], { now: nowDate(), roles: data.roles || [], items: [], notices: [] });
    return r.kind === "help" ? R.routed(r, question, { platform: thisPlatform(), installed: standalone() }).text : null;
  }
  // the same data shape the ask-ping function builds (factsData), from what the page has loaded
  function factsOf(data) {
    const run = (data.runs || [])[0] || {};
    return {
      now: nowDate(),
      lastChecked: run.finished_at || run.started_at || data.generated_at || null,
      profile: data.profile || {}, prefs: { listOthers: (state.prefs || data.profile || {}).list_other_roles !== false },
      roles: (data.roles || []).map((r) => {
        const m = state.marks?.size ? state.marks.get(r.id) : r.relevance;
        return { ...r, deadline: r.effective_deadline || r.apply_end, for_you: targetsOn() ? !!m?.relevant : undefined,
                 cv: m?.relevant ? m.best_cv : null, pay: r.more_details?.fields || {}, jd_location: r.jd_summary?.location || null };
      }),
      items: (data.items || []).filter((i) => !i.dismissed).map((i) => ({ ...i, hidden_because: i.details?.hidden_because,
        subject: i.details?.subject, venue: i.details?.venue, pdf: i.details?.pdf, kind: i.details?.kind, notice_time: i.details?.notice_time,
        via: i.details?.via, mail: i.details?.mail, todo: i.details?.todo })),
      notices: data.notices || [],
      platform: thisPlatform(), installed: standalone(),
    };
  }
  const previousQuestions = (question) => state.chat.filter((m) => m.role === "me" && m.text !== question).map((m) => m.text).reverse().slice(0, 4);
  function answerLocally(question, data) {
    const R = window.PingRules;
    if (!R) return "I can't answer that right now. Try again in a minute.";
    const facts = factsOf(data);
    return R.routed(R.route(question, previousQuestions(question), facts), question, facts).text;
  }

  // FACT questions are answered here, from the data this page already has, in a few milliseconds; only OPEN ones
  // (and preference changes, which the function saves) go to the ask-ping function. If a check has finished since
  // the page loaded its messages, or the "For you" marks aren't in yet, the function answers (its data is current).
  const lastRunId = () => LIVE.lastFinished(state.data?.runs || [])?.id ?? null;
  function stampItems() { state.itemsRun = lastRunId(); }
  function localFact(question) {
    const R = window.PingRules;
    if (!R || !state.data) return { why: "no rules" };
    if (R.prefsLike(question)) return { why: "preferences" };
    if (!LIVE.messagesCurrent(state.data.runs, state.itemsRun)) return { why: "stale" };
    if (targetsOn() && !state.marks?.size && !state.data.roles.some((r) => r.relevance)) return { why: "no marks" };
    const facts = factsOf(state.data);
    const r = R.route(question, previousQuestions(question), facts);
    if (r.kind === "open") return { why: "open" };
    return { text: R.routed(r, question, facts).text, kind: r.kind };
  }

  boot().catch((e) => mountPage(h("div", { class: "card" }, h("h1", {}, "Something went wrong"), h("p", {}, `${plainly(e)} Reloading the page usually fixes it.`))));
})();
