// "Ask Ping": answers questions about YOUR feed and roles with Gemini.
// The Gemini key lives only here (a Supabase function secret). Only your own items, roles and
// profile are sent (never PDFs, never other students' data).
//
// Limits that matter on Supabase's free plan: a request may use about 2 s of CPU and must finish
// within 150 s. So dates are formatted with one shared formatter (making a new one per date was the
// slow part), each Gemini call has its own timeout, and the whole answer has a 100 s budget.
import { caller, cors, json } from "../_shared/owner.ts";
import { asksToAct, glance, roleLists, stripRefusal, todayNote, wantsLists } from "./wording.ts";
import { cvsText, markRoles, service } from "./marks.ts";
import { describe, parsePrefs, type Prefs } from "./prefs.ts";

// Google retires model names (gemini-2.5-flash: "no longer available to new users", Nov 2026), and the
// free tier is sometimes overloaded (503) or slow, so try a few names in turn.
// The first model often answers 429 on the free tier; each model has its own quota. Chosen from the names this key
// can call (Admin > gemini-check, 21 Nov 2026); gemini-2.0-flash, gemini-2.5-flash-lite and gemma-3-27b-it answered 404.
const MODELS = [Deno.env.get("PING_AI_MODEL") || "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite", "gemma-4-31b-it"];
const BUDGET_MS = 100_000;
const HISTORY_TURNS = 10;      // messages of the thread sent along (both sides)
const HISTORY_CHARS = 8_000;   // about 2,000 tokens; the oldest messages go first
const PER_MODEL_MS = 45_000;

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
  const key = Deno.env.get("GEMINI_API_KEY");
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
  const classifiable = async () => (await sb.from("roles")
    .select("id,company,designation,job_description,more_details,eligible").limit(400)).data?.filter((r: any) => r.eligible !== false) || [];

  // The page asks for the "For you" marks of the caller's current targets (cache only, no Gemini) to split its lists.
  if (body?.marks === true) {
    const split = prefs.targets && prefs.feed_mode !== "all";
    const roles = split ? await classifiable() : [];
    const { marks } = split ? await markRoles(roles, prefs.targets!, [], "", 0, cvs) : { marks: new Map() };
    return json({ prefs, marks: Object.fromEntries(marks) });
  }
  const question = String(body?.question || "");
  if (!question || question.length > 500) return json({ error: "ask a question (max 500 characters)" }, 400);
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
      console.log(JSON.stringify({ event: "demo_question", session: take.session, all: take.all }));
    }
  }

  // Preferences said in the chat: saved, the roles re-marked, then any question in the same message is answered.
  const parsed = parsePrefs(question, prefs);
  let saved = "";
  if (parsed.kind === "show") {
    const line = `Your preferences${role === "demo" ? " (this demo session only)" : ""}: ${describe(prefs)}.`;
    if (!parsed.rest) return json({ answer: line, model: "rules", prefs });
    saved = line;
  } else if (parsed.kind !== "none") {
    const next: Prefs = { ...prefs, ...parsed.changes };
    let err = "";
    if (role === "owner") {
      const up = await sb.from("profile").update(parsed.changes).eq("id", 1).select("id");
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
      console.log(JSON.stringify({ event: "prefs_saved", role, fields: Object.keys(parsed.changes), cached: m.cached,
                                   classified: m.classified, error: m.error }));
    } else {
      console.log(JSON.stringify({ event: "prefs_saved", role, fields: Object.keys(parsed.changes) }));
    }
    prefs = next;
    if (!parsed.rest) return json({ answer: saved, model: "rules", prefs, prefs_changed: true });
  }
  const ask = parsed.kind === "none" ? question : parsed.rest;

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
    sb.from("roles").select("id,company,designation,job_description,applied,effective_deadline,eligible,ctc,currency,cgpa_cutoff").limit(400),
    sb.from("profile").select("department,degree,cgpa,active_backlogs,interested_companies,not_interested_companies,targets,list_other_roles").limit(1),
  ]);
  for (const [name, r] of [["items", items], ["roles", roles], ["profile", profile]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }
  const companies = [...new Set((roles.data || []).map((r) => r.company as string))];
  // a follow-up that names no company ("same for analyst role?") is about the previous question's companies
  let names = mentioned(ask, companies).slice(0, 6);
  if (!names.length && lastQuestion) names = mentioned(lastQuestion, companies).slice(0, 6);
  const since = new Date(asOf.getTime() - 21 * 86_400_000).toISOString();
  const [detail, lists, notices] = await Promise.all([
    names.length
      ? sb.from("roles").select("company,designation,more_details,bond,contract,backlog_rule,cgpa_cutoff,allowed," +
          "selection_details,applied,effective_deadline").in("company", names).limit(20)
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
  const hasTargets = !!prefs.targets && prefs.feed_mode !== "all";
  const rmarks = hasTargets
    ? (await markRoles((roles.data || []).filter((r: any) => r.eligible !== false), prefs.targets!, [], "", 0, cvs)).marks
    : new Map();
  // reasons stay in the feed; the chat only needs yes / no
  const forYou = (r: any) => {
    const m = rmarks.get(r.id);
    if (!hasTargets || !m) return "not classified";
    return m.relevant ? `yes${m.best_cv ? `; apply with ${m.best_cv}` : ""}` : "no";
  };
  // the follow-up's own words may be short ("and tomorrow?"): the last question counts too
  const blocks = wantsLists(`${ask} ${lastQuestion}`)
    ? roleLists((roles.data || []) as any[], rmarks, asOf, hasTargets, prefs.list_other_roles !== false) : "";
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
    ` | departments allowed: ${depts(r.allowed) || "not stated"}`);
  const listLines = (lists.data || []).map((i: any) =>
    `- ${i.title}${i.event_at ? ` (test/event at ${ist(i.event_at)}${past(i.event_at)})` : ""}` +
    ` [${i.pdf_status === "yes" ? "you ARE on this list" : i.pdf_status === "no" ? "you are NOT on this list" : "list not readable"}]` +
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
applied." "Today and this week" is counted from the data: use its numbers for questions about today, tonight or this
week (a deadline later today IS this week).
Lists of roles: "Role lists by closing time" below is ready-made. When an answer lists roles that close at one of
those times, copy that time's whole block exactly: its heading (the deadline is said once, there), "For you" with
"✓ applied" after the ones already applied to, then "Others", one "Company — Role" line each (keep Others unless
the question narrows the list). Don't add
reasons, deadlines or groupings per line, and don't merge roles of one company into one line. To narrow a list
("only product ones"), drop lines but keep the format.
CVs: the student's CVs are ${cvLabels.length ? cvLabels.map((l: string) => `"${l}"`).join(", ") : "not uploaded yet"}. For "which cv for X" or "what
should I apply to with my <label>", use "apply with" in the role lines and answer "Apply with: <label>" per role
(if a role has none, say no CV fits it best). ${cvLabels.length ? "" : 'With no CVs uploaded, say "Add your CVs on the Profile page (My CVs)" instead.'}
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
Ping is read-only: it can never apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV,
or change anything on the ERP or anywhere else. ${act
    ? `This message asks Ping to do something: start with "Ping is read-only, so I can't" followed by what was asked,
then add anything useful from the data (deadline, form link).`
    : `This message is a question, not a request to act: do not mention being read-only or what Ping can't do.`}
Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
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
Conversation so far, oldest first:
${kept.map((m) => `${m.role === "me" ? "Student" : "Ping"}: ${m.text.replace(/\s+/g, " ")}`).join("\n") || "(this is the first message)"}

Question: ${ask}`;

  const tried: string[] = [];
  let last = 0;
  for (const model of MODELS) {
    const left = BUDGET_MS - (Date.now() - t0);
    if (left < 5_000) break;
    const t = Date.now();
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
        method: "POST",
        signal: AbortSignal.timeout(Math.min(PER_MODEL_MS, left)),
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        // room for "thinking" models: their reasoning counts against the output limit
        body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }],
                               generationConfig: { temperature: 0.2, maxOutputTokens: 4096 } }),
      });
      last = r.status;
      tried.push(`${model}:${r.status}:${Date.now() - t}ms`);
      if (!r.ok) {
        console.error(JSON.stringify({ event: "gemini_error", model, status: r.status, body: (await r.text()).slice(0, 300) }));
        continue; // retired, busy or refused: try the next model
      }
      const out = await r.json();
      const raw = out?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text || "").join("").trim() || "";
      const answer = act ? raw : stripRefusal(raw);
      if (!answer) { tried.push(`${model}:empty(${out?.candidates?.[0]?.finishReason})`); continue; }
      console.log(JSON.stringify({ event: "answered", role, model, tried, history: kept.length, act,
        refusal_removed: answer !== raw, items: items.data?.length ?? 0,
        roles: roles.data?.length ?? 0, detail_roles: detail.data?.length ?? 0, prompt_chars: prompt.length, ms: Date.now() - t0 }));
      return json({ answer: saved ? `${saved}\n\n${answer}` : answer, model, ...(saved ? { prefs, prefs_changed: true } : {}) });
    } catch (e) {
      tried.push(`${model}:${(e as Error).name}:${Date.now() - t}ms`);
    }
  }
  console.error(JSON.stringify({ event: "no_answer", role, tried, prompt_chars: prompt.length, ms: Date.now() - t0 }));
  return json({ error: last === 503 || last === 429 ? "Gemini is busy right now, try again in a minute"
    : `no answer from Gemini (${tried.join(", ")})` }, 502);
});
