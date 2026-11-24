// "Ask Ping": answers questions about YOUR feed and roles with Gemini.
// The Gemini key lives only here (a Supabase function secret). Only your own items, roles and
// profile are sent (never PDFs, never other students' data).
//
// Limits that matter on Supabase's free plan: a request may use about 2 s of CPU and must finish
// within 150 s. So dates are formatted with one shared formatter (making a new one per date was the
// slow part), each Gemini call has its own timeout, and the whole answer has a 100 s budget.
import { caller, cors, json } from "../_shared/owner.ts";
import { asksToAct, fitPrompt, glance, stripRefusal, todayNote, wantsLists } from "./wording.ts";
import { cvsText, markRoles, service } from "./marks.ts";
import { describe, parsePrefs, type Prefs } from "./prefs.ts";
import { evalsProof } from "./evals_key.ts";
import { chatComplete } from "../_shared/openai_compat.ts";
// answers from the data without the AI (shared with the dashboard, which loads the same file)
import "../_shared/help.js";          // what Ping says about itself (docs/HELP.md), read by answer_rules.js
import "../_shared/answer_rules.js";
import "../_shared/understand.js";   // the model reads the question and words the reply; the rules fetch every fact
const Rules = (globalThis as any).PingRules;
const U = (globalThis as any).PingUnderstand;
// the two model steps around the rules: off until the follow-up evals pass (Admin > followup-evals), then on
const MODEL_STEPS = (Deno.env.get("PING_MODEL_STEPS") || "off") === "on";
const UNDERSTAND_MS = 3_000;         // reading the question: past this, the rules alone route it
const COMPOSE_MS = 2_500;            // wording the reply: past this, the rules' answer is sent as it is

// Gemini, for the big-context jobs (re-marking every role when your targets change: one call for all of them,
// cached in role_marks). flash-lite first: flash-latest answered 0 of 7 calls on 23 Nov.
// Google retires model names (gemini-2.5-flash: "no longer available to new users", Nov 2026), and the
// free tier is sometimes overloaded (503) or slow, so try a few names in turn.
// The first model often answers 429 on the free tier; each model has its own quota. Chosen from the names this key
// can call (Admin > gemini-check, 21 Nov 2026); gemini-2.0-flash, gemini-2.5-flash-lite and gemma-3-27b-it answered 404.
const MODELS = ["gemini-3.1-flash-lite", Deno.env.get("PING_AI_MODEL") || "gemini-flash-latest", "gemini-flash-lite-latest",
                "gemini-3.5-flash-lite", "gemma-4-31b-it"];
// Latency cap for OPEN questions: the chat's main model gets at most 10 s in all (one retry if it's busy), then the
// other model once with at most 5 s, then the answer is built from the data by rules (never a "busy" error).
// 23 Nov: on the live key gemini-flash-latest answered 0 of 7 calls in 24 h (timeouts, 503, 429 quota) and
// gemini-3.1-flash-lite 5 of 5 (Admin > chat-diagnose), so the light model leads and the other is the fallback.
// The chat's chain (23 Nov): Groq first (when its key is set), then Gemini flash-lite, then the rules; 15 s in all.
// Groq: openai/gpt-oss-120b, its best production model with published free limits (1,000 requests and 200K tokens a
// day, 8K tokens a minute), so it gets a compact prompt (the facts for this question, not every role).
const PRIMARY = Deno.env.get("PING_CHAT_MODEL") || "gemini-3.1-flash-lite";
const GROQ_URL = "https://api.groq.com/openai/v1";
const GROQ_MODEL = Deno.env.get("PING_GROQ_MODEL") || "openai/gpt-oss-120b";
const GROQ_MS = 6_000;
const GROQ_MAX_CHARS = 16_000;       // about 5,000 tokens with numbers and names: with the answer, under 8K tokens a minute
const GROQ_MAX_TOKENS = 900;

const CHAT_CAP_MS = 15_000;
const PRIMARY_WINDOW_MS = 10_000;
const RETRY_PAUSE_MS = 500;
const busy = (status: number) => status === 429 || status >= 500;

const HISTORY_TURNS = 12;      // messages of the thread sent along (both sides): the last 6 turns
const HISTORY_CHARS = 8_000;   // about 2,000 tokens; the oldest messages go first

const FMT = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit",
  month: "short", hour: "2-digit", minute: "2-digit" });
const ist = (iso?: string | number | null) => (iso ? FMT.format(new Date(iso)) : "");
// "now" with the year and the date of tomorrow spelled out, so the model can't guess a wrong year
const DAY = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", weekday: "long", day: "numeric", month: "long", year: "numeric" });

// Pay and bond lines from a role's "more details" (CTC breakup, take home, bonuses, ESOPs, bond...)
const PAY = /ctc|salary|gross|take ?home|bonus|bond|stipend|esop|stock|perk|benefit|variable|incentive|retention|relocation|joining|allowance|compensation|cost to company/i;
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
const LEGAL = new Set(["private", "pvt", "limited", "ltd", "inc", "llp", "india", "the", "and", "co", "company", "technologies", "services", "solutions"]);

// Edit distance, for typos in company names ("eternl" -> "eternal")
function close(a: string, b: string): boolean {
  if (Math.abs(a.length - b.length) > 2 || Math.min(a.length, b.length) < 5) return false;
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
  }
  return d[a.length][b.length] <= (a.length >= 8 ? 2 : 1);
}

function mentioned(question: string, companies: string[]): string[] {
  const q = ` ${norm(question).replace(/'s\b/g, "")} `;
  const words = q.trim().split(" ");
  return companies.filter((c) => {
    const n = norm(c);
    if (n && q.includes(` ${n} `)) return true;
    const first = n.split(" ").find((w) => w.length >= 3 && !LEGAL.has(w));
    return !!first && (q.includes(` ${first} `) || words.some((w) => close(w, first)));
  });
}

function payLines(md: any): string {
  const fields: Record<string, string> = md?.fields || {};
  return Object.entries(fields)
    .filter(([k, v]) => PAY.test(k) && String(v ?? "").trim() !== "")
    .map(([k, v]) => `${k}: ${String(v).trim()}`).join("; ").slice(0, 1200);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  const t0 = Date.now();
  const who = await caller(req);
  if (!who) return json({ error: "not allowed" }, 403);
  const { sb, role } = who;
  const claim = req.headers.get("x-ping-evals");
  const evalsKey = Deno.env.get("GEMINI_API_KEY_EVALS");
  let keyName = "live";
  let key = Deno.env.get("GEMINI_API_KEY");
  if (claim) {
    if (!evalsKey || claim !== await evalsProof(evalsKey)) {
      console.error(JSON.stringify({ event: "evals_key_refused", why: evalsKey ? "proof doesn't match" : "GEMINI_API_KEY_EVALS not set" }));
      return json({ error: "an eval request needs GEMINI_API_KEY_EVALS on both sides (it never falls back to the live key)" }, 403);
    }
    key = evalsKey;
    keyName = "evals";
  }
  // Groq: its own live and evals keys, like Gemini (an eval never uses the live key; no evals key: no Groq in evals)
  const groqKey = keyName === "evals" ? Deno.env.get("GROQ_API_KEY_EVALS") || "" : Deno.env.get("GROQ_API_KEY") || "";
  if (!key) return json({ error: "GEMINI_API_KEY is not set for this function" }, 500);
  const body = await req.json().catch(() => ({}));

  // The caller's preferences: the owner's profile row, or for a demo session the demo profile with that session's
  // own changes on top (session_prefs: never the owner's profile, never another session's).
  const uid = role === "demo" ? (await sb.auth.getUser()).data.user?.id : null;
  const FIELDS = "targets,reminder_hours,list_other_roles,feed_mode,check_every_minutes,check_from,check_to";
  let base = await sb.from("profile").select(`${FIELDS},cvs`).limit(1);
  // before Admin > apply-sql has added the newer columns, read the ones that exist
  if (base.error) base = await sb.from("profile").select("targets,reminder_hours,list_other_roles,cvs").limit(1) as any;
  // CV summaries (never the files): the owner's, or the demo's made-up ones
  const cvs = cvsText(base.data?.[0]?.cvs);
  const cvLabels = (base.data?.[0]?.cvs || []).map((c: any) => c.label).filter(Boolean);
  const pick = (o: any): Prefs => Object.fromEntries(FIELDS.split(",").map((k) => [k, o?.[k] ?? null])) as Prefs;
  let prefs: Prefs = pick(base.data?.[0]);
  if (role === "demo") {
    // the session's own answers on top of the demo profile, field by field
    let own = await sb.from("session_prefs").select(FIELDS).limit(1);
    if (own.error) own = await sb.from("session_prefs").select("targets,reminder_hours,list_other_roles").limit(1) as any;
    const o: any = own.data?.[0] || {};
    for (const k of FIELDS.split(",")) if (o[k] != null) (prefs as any)[k] = o[k];
  }
  // Your feedback lists (hidden / always-shown companies and roles): the owner's profile, or for a demo session its
  // own copy on top of the demo profile's
  const LISTS = "not_interested_companies,interested_companies,hidden_roles,shown_roles,prefs_undo";
  const emptyLists = { not_interested_companies: [], interested_companies: [], hidden_roles: [], shown_roles: [], prefs_undo: null } as any;
  const listsOf = (o: any) => Object.fromEntries(LISTS.split(",").map((k) => [k, o?.[k] ?? emptyLists[k]]));
  let baseLists = await sb.from("profile").select(LISTS).limit(1);
  if (baseLists.error) baseLists = await sb.from("profile").select("not_interested_companies,interested_companies").limit(1) as any;
  let fbLists: any = listsOf(baseLists.data?.[0]);
  if (role === "demo") {
    const own = await sb.from("session_prefs").select(LISTS).limit(1);
    const o: any = own.data?.[0] || {};
    for (const k of LISTS.split(",")) if (o[k] != null) fbLists[k] = o[k];
  }
  const saveLists = async (next: any) => {
    if (role === "owner") {
      const up = await sb.from("profile").update(next).eq("id", 1).select("id");
      return up.error?.message || (up.data?.length ? "" : "no profile row");
    }
    const up = await sb.from("session_prefs").upsert({ owner_id: uid, ...next, updated_at: new Date().toISOString() });
    return up.error?.message || "";
  };

  const classifiable = async () => (await sb.from("roles")
    .select("id,company,designation,job_description,jd_text,more_details,eligible").limit(400)).data?.filter((r: any) => r.eligible !== false) || [];

  // The page asks for the "For you" marks of the caller's current targets (cache only, no Gemini) to split its lists.
  if (body?.marks === true) {
    const split = prefs.targets && prefs.feed_mode !== "all";
    const roles = split ? await classifiable() : [];
    const { marks } = split ? await markRoles(roles, prefs.targets!, [], "", 0, cvs) : { marks: new Map() };
    const { prefs_undo: _u, ...shown } = fbLists;
    return json({ prefs, marks: Object.fromEntries(marks), lists: shown });
  }
  const question = String(body?.question || "");
  if (!question || question.length > 500) return json({ error: "ask a question (max 500 characters)" }, 400);
  // a reply: the message it quotes travels on its own (it never counts against the question's length)
  const reply = body?.reply && typeof body.reply === "object" ? {
    sender: String(body.reply.sender || "Ping").slice(0, 20), text: String(body.reply.text || "").slice(0, 400),
    companies: (Array.isArray(body.reply.companies) ? body.reply.companies : []).map((c: unknown) => String(c).slice(0, 120)).slice(0, 20),
  } : null;
  const isQuestion = /\?\s*$|^\s*(?:is|are|am|was|which|what|whats|why|how|when|where|who|should|do|does|did|can|could|will|would|any|anything)\b/i.test(question);
  // The demo is a snapshot; "tomorrow" means the day after the snapshot, like on the page.
  const asOf = role === "demo" && body?.as_of && !isNaN(Number(new Date(body.as_of))) ? new Date(body.as_of) : new Date();

  // Demo sessions share the Gemini quota with everyone trying the demo: 15 questions per session per hour and
  // 100 per hour for all demo sessions together (counted in the database; no question text is kept).
  if (role === "demo") {
    const { data: take, error: takeErr } = await sb.rpc("demo_take_question");
    if (takeErr) console.error(JSON.stringify({ event: "demo_limit_check_failed", error: takeErr.message }));
    else if (take && take.ok === false) {
      console.log(JSON.stringify({ event: "demo_limited", why: take.why, session: take.session, all: take.all }));
      return json({ error: take.why === "session"
        ? "That's the demo's limit of 15 questions an hour for one visitor. Try again in a while, or open the demo again later."
        : "The demo has answered its 100 questions for this hour across all visitors. Please try again in a little while.",
        limited: true }, 429);
    } else if (take) {
      console.log(JSON.stringify({ event: "demo_question", key: keyName, session: take.session, all: take.all }));
    }
  }

  // "piramal not relevant", "hide Groww", "show Zeta again", "undo": by rules (works with the model down), saved,
  // one line back with an Undo button
  if (Rules.feedbackLike(question)) {
    const fbRoles = (await sb.from("roles").select("id,company,designation").limit(400)).data || [];
    const prevQ = (await sb.from("chat_messages").select("role,text").order("created_at", { ascending: false }).limit(4)).data || [];
    const fbData = { roles: fbRoles, items: [], notices: [] };
    const prevCos = prevQ.filter((m: any) => m.role === "me" && m.text.trim() !== question.trim()).slice(0, 1)
      .flatMap((m: any) => Rules.matchCompanies(m.text, fbData).hits.map((e: any) => e.name));
    const fb = Rules.feedbackOf(question, fbData, { anchorCompanies: reply?.companies || [], previousCompanies: prevCos });
    if (fb) {
      const said = (answer: string, extra: Record<string, unknown> = {}) => {
        console.log(JSON.stringify({ event: "answered", key: keyName, role, model: "rules", route: "feedback", action: fb.action,
          level: fb.level || null, asked: !!fb.ask, ms: Date.now() - t0 }));
        return json({ answer, model: "rules", route: "feedback", ...extra });
      };
      if (fb.action === "undo") {
        const u = fbLists.prefs_undo;
        if (!u?.lists) return said("Nothing to undo.");
        const err = await saveLists({ ...u.lists, prefs_undo: null });
        if (err) return json({ error: `couldn't undo that (${err})` }, 500);
        return said(`Undone: ${u.what} is back to how it was.`, { lists: u.lists, prefs_changed: true });
      }
      if (fb.ask) {
        const chips = fb.ask.chips.map((c: any) => `[${c.label}](#ask:${encodeURIComponent(c.send)})`).join(" ");
        return said(chips ? `${fb.ask.text} ${chips}` : fb.ask.text);
      }
      const before = { not_interested_companies: fbLists.not_interested_companies || [], interested_companies: fbLists.interested_companies || [],
                       hidden_roles: fbLists.hidden_roles || [], shown_roles: fbLists.shown_roles || [] };
      const next = Rules.applyFeedback(before, fb, fbRoles);
      const what = fb.level === "role" ? fb.roles.map((r: any) => r.label).join(", ") : fb.name;
      const err = await saveLists({ ...next, prefs_undo: { lists: before, what } });
      if (err) {
        console.error(JSON.stringify({ event: "feedback_save_failed", role, error: err }));
        return json({ error: `couldn't save that (${err})` }, 500);
      }
      return said(Rules.feedbackLine(fb), { lists: next, prefs_changed: true });
    }
  }

  // Preferences said in the chat: saved, the roles re-marked, then any question in the same message is answered.
  const parsed = parsePrefs(question, prefs);
  let saved = "";
  if (parsed.kind === "show") {
    const allRoles = (await sb.from("roles").select("id,company,designation").limit(400)).data || [];
    const line = `Your preferences${role === "demo" ? " (this demo session only)" : ""}: ${describe(prefs)}; ${Rules.describeLists(fbLists, allRoles)}.` +
      (fbLists.not_interested_companies?.length || fbLists.hidden_roles?.length || fbLists.interested_companies?.length || fbLists.shown_roles?.length
        ? " Say \"reset\" to clear them all, or \"show X again\" for one." : "");
    if (!parsed.rest) return json({ answer: line, model: "rules", prefs });
    saved = line;
  } else if (parsed.kind !== "none") {
    const next: Prefs = { ...prefs, ...parsed.changes };
    let err = "";
    if (role === "owner") {
      // reset: the hidden / always-shown companies and roles go too
      const changes = parsed.kind === "reset" ? { ...parsed.changes, not_interested_companies: [], interested_companies: [],
        hidden_roles: [], shown_roles: [], prefs_undo: null } : parsed.changes;
      const up = await sb.from("profile").update(changes).eq("id", 1).select("id");
      if (up.error || !up.data?.length) {
        // a brand-new setup may have no profile row yet: the first message can be the preferences
        const svc = service();
        const ins = svc ? await svc.from("profile").upsert({ id: 1, ...parsed.changes }) : { error: { message: "no service key" } };
        if (ins.error) err = up.error?.message || ins.error.message;
      }
    } else {
      // counts against the demo's limit like a question (it may cost a Gemini call)
      await sb.rpc("demo_take_question");
      const up = parsed.kind === "reset"
        ? await sb.from("session_prefs").delete().eq("owner_id", uid)
        : await sb.from("session_prefs").upsert({ owner_id: uid, ...next, updated_at: new Date().toISOString() });
      if (up.error) err = up.error.message;
    }
    if (err) {
      console.error(JSON.stringify({ event: "prefs_save_failed", role, error: err }));
      return json({ error: `couldn't save that preference (${err})` }, 500);
    }
    if (role === "demo" && parsed.kind === "reset") {
      const b: any = base.data?.[0] || {};
      Object.assign(next, { targets: b.targets ?? null, reminder_hours: b.reminder_hours ?? null, list_other_roles: b.list_other_roles ?? null });
    }
    saved = `Saved${role === "demo" ? " for this demo session" : ""}: ${describe(next, parsed.changes)}.`;
    if ("targets" in parsed.changes && next.targets) {
      const roles = await classifiable();
      const m = await markRoles(roles, next.targets, MODELS, key, 60_000, cvs);
      const yes = [...m.marks.values()].filter((x) => x.relevant).length;
      saved += m.marks.size === roles.length
        ? ` ${yes} of ${roles.length} roles are now for you.`
        : " The roles will be re-marked at the next check (Gemini didn't answer in time).";
      console.log(JSON.stringify({ event: "prefs_saved", key: keyName, role, fields: Object.keys(parsed.changes), cached: m.cached,
                                   classified: m.classified, error: m.error }));
    } else {
      console.log(JSON.stringify({ event: "prefs_saved", role, fields: Object.keys(parsed.changes) }));
    }
    prefs = next;
    if (!parsed.rest) return json({ answer: saved, model: "rules", prefs, prefs_changed: true });
  }
  const ask = parsed.kind === "none" ? question : parsed.rest;
  // a reply: the quoted message scopes which companies are meant; the message itself decides what's asked
  const replyNote = reply ? `\n[replying to ${reply.sender}'s message: "${reply.text}"${reply.companies.length
    ? `; about: ${reply.companies.map((c: string) => Rules.shortName(c)).join(", ")}` : ""}]` : "";

  // The thread so far, from the database (never from the page): this login's last messages, oldest first.
  // The owner reads its own thread; a demo session only its own messages (database rules). The page saves the
  // new question before asking, so it's dropped here if it's the newest message.
  const thread = await sb.from("chat_messages").select("role,text,created_at")
    .order("created_at", { ascending: false }).limit(HISTORY_TURNS + 2);
  if (thread.error) console.error(JSON.stringify({ event: "read_failed", table: "chat_messages", error: thread.error.message }));
  const earlier = (thread.data || []).slice();
  if (earlier[0]?.role === "me" && earlier[0].text.trim() === question.trim()) earlier.shift();
  const history = earlier.slice(0, HISTORY_TURNS).reverse();
  let historyChars = 0;
  const kept: { role: string; text: string }[] = [];
  for (const m of history.slice().reverse()) {          // newest first, so the oldest are dropped
    const text = m.text.length > 1200 ? m.text.slice(0, 1200) + "…" : m.text;
    if (historyChars + text.length > HISTORY_CHARS) break;
    historyChars += text.length;
    kept.unshift({ role: m.role, text });
  }
  const lastQuestion = [...kept].reverse().find((m) => m.role === "me")?.text || "";

  const [items, roles, profile] = await Promise.all([
    sb.from("items").select("level,category,title,company,due_at,event_at,first_seen,details")
      .neq("level", "hidden").eq("dismissed", false).order("first_seen", { ascending: false }).limit(150),
    sb.from("roles").select("id,company,designation,job_description,jd_text,jd_source,jd_url,jd_note,jd_summary,applied,effective_deadline,eligible,ctc,currency,cgpa_cutoff,bond").limit(400),
    sb.from("profile").select("department,degree,cgpa,active_backlogs,interested_companies,not_interested_companies,targets,list_other_roles").limit(1),
  ]);
  for (const [name, r] of [["items", items], ["roles", roles], ["profile", profile]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }
  // JD questions go through the router like every other fact (its lookup reads the role page, the notices and their
  // files, placement mail and form pages, and knows the conversation): no separate shortcut
  // ---- the router: FACT questions are answered here by rules, with no model call (answer_rules.js route)
  const hasTargets = !!prefs.targets && prefs.feed_mode !== "all";
  const rmarks = hasTargets
    ? (await markRoles((roles.data || []).filter((r: any) => r.eligible !== false), prefs.targets!, [], "", 0, cvs)).marks
    : new Map();
  const [allItems, allNotices, lastRun] = await Promise.all([
    sb.from("items").select("id,company,category,title,due_at,event_at,level,pdf_status,role_ids,notice_id,first_seen," +
      "hidden_because:details->>hidden_because,subject:details->>subject,venue:details->>venue,kind:details->>kind," +
      "notice_time:details->>notice_time,pdf:details->pdf,via:details->>via,mail:details->mail,todo:details->todo,sort_at").eq("dismissed", false)
      .order("first_seen", { ascending: false }).limit(1000),
    sb.from("notices").select("id,notice_id,year,company,subject,notice_time,has_attachment").order("notice_time", { ascending: false }).limit(1000),
    sb.from("runs").select("started_at,finished_at").order("started_at", { ascending: false }).limit(1),
  ]);
  for (const [name, r] of [["items(rules)", allItems], ["notices(rules)", allNotices], ["runs", lastRun]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }
  const run: any = lastRun.data?.[0];
  const factsData: any = {
    now: asOf,
    // a demo session can't read the runs: its "last checked" is the snapshot's time
    lastChecked: run?.finished_at || run?.started_at || (role === "demo" ? asOf.toISOString() : null),
    profile: { ...(profile.data?.[0] || {}) }, prefs: { listOthers: prefs.list_other_roles !== false },
    roles: (roles.data || []).map((r: any) => ({ ...r, deadline: r.effective_deadline,
      for_you: Rules.pinned(r, fbLists) ?? (hasTargets ? rmarks.get(r.id)?.relevant === true : undefined),
      cv: rmarks.get(r.id)?.relevant ? rmarks.get(r.id)?.best_cv || null : null, jd_location: r.jd_summary?.location || null })),
    items: allItems.data || [],
    notices: allNotices.data || [],
    // help answers ("how do I install?") give the steps for the asker's own device
    platform: Rules.platformOf(req.headers.get("user-agent") || ""),
  };
  // the last answer Ping gave in this thread: never the same answer twice in a row
  factsData.lastAnswer = [...kept].reverse().find((m) => m.role !== "me")?.text || null;
  // the questions before this one, newest first (follow-ups resolve against them)
  const previous = [...kept].reverse().filter((m) => m.role === "me").map((m) => m.text);
  // a question in a reply that names no company is about the quoted message's companies; a statement is routed on
  // its own words (never "a company" -> a status dump of everything quoted)
  const named = Rules.matchCompanies(ask, factsData).hits.length;
  const askRoute = reply && isQuestion && !named && reply.companies.length
    ? `${ask} ${reply.companies.map((c: string) => Rules.shortName(c)).join(" ")}` : ask;
  // 1. the model reads the question with the last 6 turns (Groq, then Gemini flash-lite; 3 s cap): company, role, fact,
  //    source, follow-up. Checked against the data; what the question left out is filled in for the rules.
  const noAiEarly = body?.no_ai === true;
  const modelCall = async (p: string, ms: number): Promise<{ text?: string; model?: string; error?: string }> => {
    const t = Date.now();
    if (groqKey) {
      const r = await chatComplete({ baseUrl: GROQ_URL, key: groqKey, model: GROQ_MODEL, prompt: p, timeoutMs: ms, maxTokens: 700,
                                     extra: /gpt-oss/.test(GROQ_MODEL) ? { reasoning_effort: "low", include_reasoning: false } : {} });
      if (r.status === 200 && r.text) return { text: r.text, model: `groq/${GROQ_MODEL}` };
    }
    const left = ms - (Date.now() - t);
    if (key && left > 400) {
      try {
        const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${PRIMARY}:generateContent`, {
          method: "POST", signal: AbortSignal.timeout(left), headers: { "Content-Type": "application/json", "x-goog-api-key": key },
          body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: p }] }], generationConfig: { temperature: 0, maxOutputTokens: 700 } }) });
        if (r.ok) {
          const out = await r.json();
          const text = out?.candidates?.[0]?.content?.parts?.map((x: { text?: string }) => x.text || "").join("").trim();
          if (text) return { text, model: PRIMARY };
        }
      } catch (_) { /* past the cap: the rules alone */ }
    }
    return { error: "no model answer" };
  };
  const understood = MODEL_STEPS && !noAiEarly && (groqKey || key) && !Rules.feedbackLike(ask)
    ? await U.understand({ question: ask, turns: kept.map((m) => ({ role: m.role, text: m.text })), data: factsData, Rules,
                           call: (p: string) => modelCall(p, UNDERSTAND_MS), capMs: UNDERSTAND_MS })
    : null;
  const askUnderstood = understood?.u ? U.augment(askRoute, understood.u, factsData, Rules) : askRoute;
  const routed = Rules.route(askUnderstood, previous, factsData);
  // the details a FACT answer about a company needs (pay, bond, departments, backlogs), for those companies only
  const withDetails = async (hits: any[]) => {
    const raw = [...new Set(hits.flatMap((e: any) => [...e.raw]))];
    if (!raw.length) return;
    const d = await sb.from("roles").select("id,more_details,allowed,backlog_rule,contract").in("company", raw).limit(60);
    if (d.error) console.error(JSON.stringify({ event: "read_failed", table: "roles(facts)", error: d.error.message }));
    const byId = new Map((d.data || []).map((x: any) => [x.id, x]));
    factsData.roles = factsData.roles.map((r: any) => byId.has(r.id)
      ? { ...r, pay: byId.get(r.id).more_details?.fields || {}, allowed: byId.get(r.id).allowed, backlog_rule: byId.get(r.id).backlog_rule } : r);
  };
  // every source a fact can be in, for the companies asked about: the notices' text and files, placement mail, the
  // form pages (answer_rules.js lookup); a source not loaded would make an absence answer wrong
  const withSources = async (hits: any[]) => {
    const raw = [...new Set(hits.flatMap((e: any) => [...e.raw]))];
    if (!raw.length) return;
    const word = (hits[0]?.words || []).find((w: string) => w.length >= 4) || "";
    const like = word ? `,text.ilike.%${word.replace(/[%_,()]/g, "")}%` : "";
    const [nt, em, fo] = await Promise.all([
      sb.from("notices").select("id,notice_id,year,company,subject,text,notice_time,has_attachment")
        .or(`company.in.(${raw.map((c) => `"${c.replace(/"/g, "")}"`).join(",")})${like}`).order("notice_time", { ascending: false }).limit(40),
      sb.from("emails").select("id,received_at,sender,subject,snippet,company,main_link,due_at,pdf").order("received_at", { ascending: false }).limit(400),
      sb.from("forms").select("key,company,companies,title,description,link,final_url,due_at,purpose").limit(400),
    ]);
    for (const [name, r] of [["notices(sources)", nt], ["emails(sources)", em], ["forms(sources)", fo]] as const) {
      if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
    }
    const ids = (nt.data || []).map((n: any) => n.id);
    const ck = ids.length ? await sb.from("pdf_checks").select("notice_id,status,context").in("notice_id", ids) : { data: [] as any[] };
    const byId = new Map((nt.data || []).map((n: any) => [n.id, n]));
    factsData.notices = [...(nt.data || []), ...factsData.notices.filter((n: any) => !byId.has(n.id))];
    // a student list's check keeps only your row: its text never leaves here; a JD's text does
    factsData.pdf_checks = (ck.data || []).map((c: any) => ({ notice_id: c.notice_id, status: c.status, context: c.status === "jd" ? c.context : null }));
    factsData.emails = (em.data || []).map((m: any) => ({ ...m, pdf: m.pdf ? { status: m.pdf.status, file: m.pdf.file, context: m.pdf.status === "jd" ? m.pdf.context : null } : null }));
    factsData.forms = fo.data || [];
  };
  if (routed.kind !== "open") {
    await Promise.all([withDetails(routed.spec?.hits || []), withSources(routed.spec?.hits || [])]);
    const out = Rules.routed(routed, askUnderstood, factsData);
    // 3. the model words the reply from the rules' answer only; kept if every date, time, number, name, status and
    //    link in it is in that answer and no link is dropped (U.verify), else the rules' answer as it is
    const names = Rules.entities(factsData).map((e: any) => e.name);
    const composed = MODEL_STEPS && !noAiEarly && (groqKey || key) && out.recheck === undefined
      ? await U.compose({ question: ask, answer: out.text, data: factsData, companyNames: names,
                          call: (p: string) => modelCall(p, COMPOSE_MS), capMs: COMPOSE_MS })
      : null;
    const text = composed?.used ? composed.text : out.text;
    console.log(JSON.stringify({ event: "answered", key: keyName, role, model: composed?.used ? `rules+${composed.model}` : "rules",
      route: routed.kind, why: routed.why, intents: routed.spec?.intents || [], kind: out.kind,
      understood: understood ? { ok: !!understood.u, ms: understood.ms, model: understood.model, why: understood.why, added: askUnderstood !== askRoute } : null,
      composed: composed ? { used: composed.used, ms: composed.ms, why: composed.why || null } : null, ms: Date.now() - t0 }));
    return json({ answer: saved ? `${saved}\n\n${text}` : text, model: composed?.used ? `rules+${composed.model}` : "rules", route: routed.kind,
                  understood: understood ? { ...understood.u, ms: understood.ms, fell: understood.fell, why: understood.why } : null,
                  asked_as: askUnderstood, composed: composed ? { used: composed.used, ms: composed.ms, why: composed.why || null } : null,
                  ...(out.recheck !== undefined ? { recheck: out.recheck, companies: out.companies } : {}),
                  ...(saved ? { prefs, prefs_changed: true } : {}) });
  }

  const companies = [...new Set((roles.data || []).map((r) => r.company as string))];
  // a follow-up that names no company ("same for analyst role?") is about the previous question's companies
  let names = mentioned(ask, companies).slice(0, 6);
  if (!names.length && lastQuestion) names = mentioned(lastQuestion, companies).slice(0, 6);
  const since = new Date(asOf.getTime() - 21 * 86_400_000).toISOString();
  const [detail, lists, notices] = await Promise.all([
    names.length
      ? sb.from("roles").select("company,designation,more_details,bond,contract,backlog_rule,cgpa_cutoff,allowed," +
          "selection_details,applied,effective_deadline,job_description,jd_text,jd_source,jd_url").in("company", names).limit(20)
      : Promise.resolve({ data: [] as any[], error: null }),
    // your results on shortlists / test room lists (also the ones already past), newest first
    sb.from("items").select("title,company,pdf_status,event_at,details").not("pdf_status", "is", null)
      .gte("sort_at", since).order("sort_at", { ascending: false }).limit(60),
    names.length
      ? sb.from("notices").select("company,subject,notice_time,text").in("company", names.map((n) => n.toUpperCase())
          .concat(names)).order("notice_time", { ascending: false }).limit(6)
      : Promise.resolve({ data: [] as any[], error: null }),
  ]);
  for (const [name, r] of [["roles(details)", detail], ["list results", lists], ["notices", notices]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }

  // Your own row from each list PDF (room, slot, time...). Never anyone else's.
  const myRow = (d: any) => {
    const p = d?.pdf;
    if (!p || p.status !== "yes" || !p.my_row) return "";
    const pairs = p.header ? p.header.map((h: string, k: number) => `${h || "?"}: ${p.my_row[k] ?? ""}`) : p.my_row;
    return ` [your row in the PDF: ${pairs.join(", ")}]`;
  };
  const feed = (items.data || []).map((i) =>
    `- [${i.level}] ${i.title}${i.due_at ? ` (due ${ist(i.due_at)}${todayNote(i.due_at, asOf)})` : ""}` +
    `${i.event_at ? ` (at ${ist(i.event_at)}${todayNote(i.event_at, asOf)})` : ""}` +
    `${i.details?.venue ? ` (venue ${i.details.venue})` : ""}${myRow(i.details)}`);
  // "For you" or not: the same answer the feed uses (cached on the role by the hourly run, ping/relevance.py),
  // valid only for the targets the student has now
  const prof = { ...(profile.data?.[0] || {}), ...prefs } as any;
  // reasons stay in the feed; the chat only needs yes / no
  const forYou = (r: any) => {
    const pin = Rules.pinned(r, fbLists);
    if (pin !== null) return pin ? "yes (you said so)" : "no (you hid it)";
    const m = rmarks.get(r.id);
    if (!hasTargets || !m) return "not classified";
    return m.relevant ? `yes${m.best_cv ? `; apply with ${m.best_cv}` : ""}` : "no";
  };
  // the follow-up's own words may be short ("and tomorrow?"): the last question counts too
  const blocks = wantsLists(`${ask} ${lastQuestion}`)
    ? Rules.dueBlocks(factsData, asOf.getTime(), asOf.getTime() + 7 * 86_400_000).join("\n\n") : "";
  // what the rules make of this question (the router's reading of it, a follow-up included): the model phrases, the
  // rules count
  await withDetails(routed.spec?.hits || []);
  const ruledFacts = routed.spec && (routed.spec.intents?.length || routed.spec.hits?.length)
    ? Rules.answer(ask, factsData, routed.spec).text : "";
  const roleLines = (roles.data || []).map((r) =>
    `- ${r.company} | ${r.designation} | applied: ${r.applied ? "yes" : "no"} | deadline: ${ist(r.effective_deadline)}` +
    `${todayNote(r.effective_deadline, asOf)} | eligible: ${r.eligible === true ? "yes" : r.eligible === false ? "no" : "unknown"}` +
    ` | for you: ${forYou(r)} | CTC ${r.ctc ?? "?"} ${r.currency ?? ""}`);
  const past = (iso?: string | null) => todayNote(iso, asOf) || (iso && new Date(iso) < asOf ? " (already passed)" : "");
  const depts = (allowed: any[]) => [...new Set((allowed || []).map((a) => a.department).filter(Boolean))].join("; ");
  const detailLines = (detail.data || []).map((r: any) =>
    `- ${r.company} | ${r.designation} | applied: ${r.applied ? "yes" : "no"} | deadline: ${ist(r.effective_deadline)}` +
    `${past(r.effective_deadline)} | CG cut-off: ${r.cgpa_cutoff ?? "none given"} | backlogs: ${r.backlog_rule || "not stated"}` +
    ` | written test: ${r.selection_details?.["Written Test"] ?? "not stated"}` +
    ` | pay: ${payLines(r.more_details) || "no pay details given"}` +
    `${r.bond ? ` | bond: ${r.bond}` : ""}${r.contract ? ` | contract: ${r.contract}` : ""}` +
    ` | departments allowed: ${depts(r.allowed) || "not stated"}` +
    // the JD (ping/jd.py found it: the ERP's field, its file, a public link or the role's details)
    (r.jd_text || r.job_description ? ` | JD (${r.jd_source || "ERP field"}): ${String(r.jd_text || r.job_description).replace(/\s+/g, " ").slice(0, 1500)}`
      : r.jd_source === "link-unreadable" ? ` | JD: a link Ping can't open: ${r.jd_url}` : " | JD: none on the ERP"));
  const listLines = (lists.data || []).map((i: any) =>
    `- ${i.title}${i.event_at ? ` (test/event at ${ist(i.event_at)}${past(i.event_at)})` : ""}` +
    ` [${i.pdf_status === "yes" ? "you ARE on this list" : i.pdf_status === "no" ? "roll number not found in this file (read in full): say 'I couldn't find your roll number in it, please check the list yourself', never that the student isn't on it" : "file not read reliably: say 'I couldn't read it reliably, check it yourself'"}]` +
    `${i.details?.venue ? ` (venue ${i.details.venue})` : ""}${myRow(i.details)}` +
    `${i.details?.notice_time ? ` (posted ${ist(i.details.notice_time)})` : ""}`);
  const noticeLines = (notices.data || []).slice(0, 3).map((n: any) =>
    `- ${ist(n.notice_time)} | ${n.company} | ${n.subject}: ${(n.text || "").replace(/\s+/g, " ").slice(0, 600)}`);

  // counted here, not by the model: tests today, deadlines left today and this week
  const events = [
    ...(items.data || []).filter((i) => i.event_at && /test|ppt|interview|event/i.test(i.category || ""))
      .map((i) => ({ title: i.title.replace(/\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2} \w{3} \d{2}:\d{2}\.?$/, ""), at: i.event_at })),
    ...(lists.data || []).filter((i: any) => i.event_at && i.pdf_status === "yes").map((i: any) => ({ title: i.title, at: i.event_at })),
  ];
  const atAGlance = glance(events, (roles.data || []).filter((r: any) => r.eligible !== false)
    .map((r: any) => ({ ...r, for_you: forYou(r).startsWith("yes") })) as any[], asOf);

  // decided here, not by the model: only a request to act may get the read-only refusal
  const act = asksToAct(ask);
  const convo = kept.map((m) => `${m.role === "me" ? "Student" : "Ping"}: ${m.text.replace(/\s+/g, " ")}`).join("\n");
  const prompt = `You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete: dates in IST, times as HH:MM in 24-hour form (e.g. 20:00), money in rupees as written
(e.g. 22,00,000 or 22 LPA). For pay questions, list every component the data gives (fixed / take-home, bonuses,
ESOPs, bond) per role. When a deadline or test is before Now, say it has already passed.
Always name the company (and role) you are answering about, even in a one-word answer: "No, Harness has no bond",
"Groww: eligibility unknown, because ...", never a bare "No" or "Eligibility status is unknown".
If what was asked about isn't in the data at all (a company, field or record Ping doesn't have), start with "I don't
have" and what's missing ("I don't have Google in your companies list", "I don't have any notice for Harness"), then
mention the closest thing the data does show. Never guess locations, scores, contacts or phone numbers.
Eligibility questions ("am I eligible for X"): always give the role's CG cut-off and the student's CGPA from Profile
("CG cut-off 7.5, your CGPA 8.0: met"), then anything that can't be checked (department, degree, backlogs).
"What's due" questions (today, tonight, tomorrow, this week): name the companies and roles, with the time, by
copying the role list block for each closing time; a count alone is not an answer. "This week" includes today: if
"Today and this week" shows deadlines, they are due this week.
Only when "Today and this week" and the role lists show nothing for the day asked about, start with "Nothing is
due on <day>". When the answer is simply "no" or
"nothing" (no other test, nothing due), say it short and specific, and add the
next relevant thing if there is one: "No other tests today. Next one is X on Mon 24 Nov, 10:00." Never write a
sentence about what the data does or doesn't contain for such an answer.
Time: times today carry a note in the data, "(earlier today, already over)" or "(later today, in 1h 25m)". Use it:
"was at 15:00 today, so it's over" or "at 20:00 today (in 1h 25m)". Never say "is today at 15:00" once it's past. For "anything else?"-type follow-ups answer with the count: "No, that was the only
test today" or "Two more: ...", then add one line with the most urgent other thing from "Today and this week"
below, with its count and time: "No other tests. 48 applications close at 20:00 today (in 1h 25m), 39 of them not
applied: Ather Energy, Auro Group, Axis Bank, BlackBuck, Diageo +15 more." Never give a count without the names that
"Today and this week" lists after it (the first 5, then "+N more"). "Today and this week" is counted from the data: use its numbers for questions about today, tonight or this
week (a deadline later today IS this week).
Numbers: you may phrase, never compute. Every number, time, count, amount and company name in your answer must be
copied from FACTS below: never add, subtract, count or convert yourself. If FACTS has no number for something,
say you don't have it. An answer with a number that isn't in FACTS is thrown away.
Lists of roles: "Role lists by closing time" below is ready-made. When an answer lists roles that close at one of
those times, copy that time's whole block exactly: its heading (the deadline is said once, there; "8 for you" means
for you and not applied yet), "For you", "Applied" (each with "✓ applied"), then "Others", one "Company — Role" line
each (keep Others unless the question narrows the list). Don't add
reasons, deadlines or groupings per line, and don't merge roles of one company into one line. To narrow a list
("only product ones"), drop lines but keep the format.
Lists (shortlists, tests, rooms, results): never tell the student they are not on a list. If their roll number
wasn't found, say "I couldn't find your roll number in the <company> <list> (posted <time>). Please check the list
yourself." If the file wasn't read reliably, say so and ask them to check it. Say which notice and when it was read.
CVs: the student's CVs are ${cvLabels.length ? cvLabels.map((l: string) => `"${l}"`).join(", ") : "not uploaded yet"}. For "which cv for X" or "what
should I apply to with my <label>", use "apply with" in the role lines and answer "Apply with: <label>" per role
(if no CV fits a role, leave its Apply with line out; never write "no CV fits it best"). Write plain text: no
**bold** or other markdown except "- " list lines, and company names without their bracketed website. ${cvLabels.length ? "" : 'With no CVs uploaded, say "Add your CVs on the Profile page (My CVs)" instead.'}
Roles marked eligible: no are never listed. If eligibility is "unknown" because the Profile has no department or
degree, say once "Add your department and degree on the Profile page to check eligibility". Questions like "which of these are relevant to me", "anything for product roles tonight", "what's
due that's relevant" use the "for you" marks (and the targets text for a narrower ask like "product"); don't
re-judge roles yourself. If no targets are set, list roles normally and mention once that the Profile page's
"What I'm looking for" box makes Ping split them.
Conversation: "Conversation so far" below is this thread, oldest first. A short or elliptical message ("nothing
else?", "and tomorrow?", "what about slice?", "same for analyst role?", "when?", "why not?") continues the previous
turn: work out the full question from the last question and answer, then answer that. Never answer about the literal
words of the follow-up and never quote them back. If a follow-up could mean two things, answer the more likely one in
one line and offer the other in a second line; ask a question back only if neither can be answered. A message that
starts a new topic ("ok. what's due this week?") is a new question: don't carry the old topic into it.
Replies: a "[replying to ...]" line after the question is the message the student replied to; it says which companies
are meant, the question says what is wanted. A statement ("ok", "this one isn't for me", "already did it") is not a
request for data: answer it in one line and never list the status of every company in the quoted message.
Ping is read-only: it can never apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV,
or change anything on the ERP or anywhere else. ${act
    ? `This message asks Ping to do something: start with "Ping is read-only, so I can't" followed by what was asked,
then add anything useful from the data (deadline, form link).`
    : `This message is a question, not a request to act: do not mention being read-only or what Ping can't do.`}
FACTS start here.
${ruledFacts ? `Ping's own answer from the data (the rules), for: ${routed.resolved || ask}\n${ruledFacts}\n\n` : ""}Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
All dates in the data are in ${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", year: "numeric" }).format(asOf)} unless they say otherwise.

Today and this week (counted from the data below):
${atAGlance}

Profile: ${JSON.stringify(prof)}

Role lists by closing time (next 7 days):
${blocks || "(no open deadlines)"}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}
${detailLines.length ? `\nDetails for the companies in the question (from the ERP's "more details"):\n${detailLines.join("\n")}\n` : ""}
Your results on shortlists and test room lists in the last 21 days, newest first:
${listLines.join("\n") || "(none)"}
${noticeLines.length ? `\nLatest notices for the companies in the question, newest first:\n${noticeLines.join("\n")}\n` : ""}
FACTS end here.

Conversation so far, oldest first:
${convo || "(this is the first message)"}

Question: ${ask}${replyNote}`;

  // every model try ("groq/openai/gpt-oss-120b:200:1830ms"), so the page's checks can score each provider
  const done = (answer: string, model: string, extra: Record<string, unknown> = {}) =>
    json({ answer: saved ? `${saved}\n\n${answer}` : answer, model, tried, ...extra, ...(saved ? { prefs, prefs_changed: true } : {}) });
  const tried: string[] = [];
  // one call: the answer, or why there is none ("busy" may be retried)
  const call = async (model: string, limit: number): Promise<{ answer?: string; busy: boolean }> => {
    const t = Date.now();
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
        method: "POST",
        signal: AbortSignal.timeout(limit),
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        // room for "thinking" models: their reasoning counts against the output limit
        body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }],
                               generationConfig: { temperature: 0.2, maxOutputTokens: 4096 } }),
      });
      tried.push(`${model}:${r.status}:${Date.now() - t}ms`);
      if (!r.ok) {
        console.error(JSON.stringify({ event: "gemini_error", model, status: r.status, body: (await r.text()).slice(0, 300) }));
        return { busy: busy(r.status) };
      }
      const out = await r.json();
      const raw = out?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text || "").join("").trim() || "";
      const answer = act ? raw : stripRefusal(raw);
      if (!answer) { tried.push(`${model}:empty(${out?.candidates?.[0]?.finishReason})`); return { busy: false }; }
      return { answer, busy: false };
    } catch (e) {
      tried.push(`${model}:${(e as Error).name}:${Date.now() - t}ms`);
      return { busy: true };                       // a timeout or a dropped connection: worth another try
    }
  };
  // Groq: the compact prompt (the full one without the long lists), through the OpenAI-compatible client
  const compactPrompt = (() => {
    const own = (l: string) => names.some((n) => l.startsWith(`- ${n} |`));
    let c = prompt
      .replace(`All roles in the companies list:\n${roleLines.join("\n") || "(empty)"}`,
               `Roles of the companies in the question:\n${roleLines.filter(own).join("\n") || "(none named; the lists above cover what's due)"}`)
      .replace(`Feed (things for this student):\n${feed.join("\n") || "(empty)"}`,
               `Feed (the newest 25 things for this student):\n${feed.slice(0, 25).join("\n") || "(empty)"}`);
    return fitPrompt(c, [
      // least needed first: each is cut (at a line end) only as far as the prompt is still over the limit
      feed.slice(0, 25).join("\n"), JSON.stringify(prof), listLines.join("\n"), noticeLines.join("\n"),
      { text: convo, oldestFirst: true }, roleLines.filter(own).join("\n"), detailLines.join("\n"), blocks, ruledFacts || "",
    ], GROQ_MAX_CHARS);
  })();
  const callGroq = async (limit: number): Promise<{ answer?: string; busy: boolean }> => {
    const name = `groq/${GROQ_MODEL}`;
    if (!compactPrompt) { tried.push(`${name}:skipped(prompt too big)`); return { busy: false }; }
    const r = await chatComplete({ baseUrl: GROQ_URL, key: groqKey, model: GROQ_MODEL, prompt: compactPrompt, timeoutMs: limit,
                                   maxTokens: GROQ_MAX_TOKENS, extra: /gpt-oss/.test(GROQ_MODEL) ? { reasoning_effort: "low", include_reasoning: false } : {} });
    tried.push(`${name}:${r.status || r.error}:${r.ms}ms`);
    if (r.status !== 200) {
      if (r.status) console.error(JSON.stringify({ event: "groq_error", model: name, status: r.status, body: r.error }));
      return { busy: !r.status || busy(r.status) };
    }
    const answer = act ? r.text : stripRefusal(r.text);
    if (!answer) { tried.push(`${name}:empty(${r.finish})`); return { busy: false }; }
    return { answer, busy: false };
  };
  // FACTS: the prompt between its two markers (the instructions' examples and the conversation don't count)
  const factsText = prompt.slice(prompt.indexOf("FACTS start here."), prompt.indexOf("FACTS end here."));
  const noAi = body?.no_ai === true;               // the evals test the rules path on its own
  let mismatch = false;
  if (!noAi) {
    const start = Date.now();
    // 1. Groq, once, at most 6 s
    if (groqKey) {
      const g = await callGroq(GROQ_MS);
      if (g.answer) { const ok = answered(g.answer, `groq/${GROQ_MODEL}`); if (ok) return ok; }
    }
    // 2. Gemini flash-lite: one try, one retry if it's busy, within what's left of the 15 s
    const geminiStart = Date.now();
    for (let i = 0; i < 2; i++) {
      if (i) await new Promise((r) => setTimeout(r, RETRY_PAUSE_MS));
      const left = Math.min(PRIMARY_WINDOW_MS - (Date.now() - geminiStart), CHAT_CAP_MS - (Date.now() - start));
      if (left < 1_500) break;
      const res = await call(PRIMARY, left);
      if (res.answer) { const ok = answered(res.answer, PRIMARY); if (ok) return ok; break; }
      if (!res.busy) break;                        // retired or refused: retrying won't help
    }
    console.error(JSON.stringify({ event: "no_answer", key: keyName, role, tried, prompt_chars: prompt.length, ms: Date.now() - t0 }));
  }
  // a model's answer, or null when it has a number that isn't in the facts (the next in the chain, then the rules)
  function answered(answer: string, model: string) {
    const bad = Rules.unsupportedNumbers(answer, factsText, ask);
    if (bad.length) {
      console.log(JSON.stringify({ event: "model_count_mismatch", key: keyName, role, model, numbers: bad.slice(0, 8), route: routed.kind,
        why: routed.why, ms: Date.now() - t0 }));
      mismatch = true;
      return null;
    }
    console.log(JSON.stringify({ event: "answered", key: keyName, role, model, tried, history: kept.length, act,
      items: items.data?.length ?? 0, roles: roles.data?.length ?? 0, detail_roles: detail.data?.length ?? 0,
      prompt_chars: prompt.length, ms: Date.now() - t0 }));
    return done(answer, model);
  }

  return rulesReply(noAi ? "no_ai" : mismatch ? "model_count_mismatch" : "model_busy");

  // No model answer (busy, switched off, or a number it made up): the rules answer for what the router made of the
  // question (a follow-up: the last question's companies and intent); nothing understood: says so, then what's due
  // soon. Same code as the dashboard's offline answers.
  function rulesReply(reason: string) {
    // a reply that is a statement Ping can't place: one short question with buttons, never every quoted company's status
    if (reply && !isQuestion && reply.companies.length && routed.kind === "open") {
      const c = Rules.clarify(ask, reply.companies, factsData);
      if (c) {
        console.log(JSON.stringify({ event: "answered", key: keyName, role, model: "rules", reason, route: "clarify", tried, ms: Date.now() - t0 }));
        return done(c.text, "rules", { fallback: true, kind: "clarify", reason });
      }
    }
    const ruled = routed.spec && (routed.spec.intents?.length || routed.spec.hits?.length)
      ? Rules.answer(ask, factsData, routed.spec) : Rules.answer(ask, factsData);
    console.log(JSON.stringify({ event: "answered", key: keyName, role, model: "rules", reason, route: routed.kind, kind: ruled.kind,
      companies: ruled.companies.length, no_ai: noAi, tried, ms: Date.now() - t0 }));
    const note = reason === "model_busy" ? "\n\n(Gemini busy: answered from your ERP data by rules, not by the model.)" : "";
    return done(ruled.text + note, "rules", { fallback: true, kind: ruled.kind, reason });
  }
});
