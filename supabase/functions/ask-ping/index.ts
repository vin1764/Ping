// "Ask Ping": answers questions about YOUR feed and roles with Gemini.
// The Gemini key lives only here (a Supabase function secret). Only your own items, roles and
// profile are sent (never PDFs, never other students' data).
//
// Limits that matter on Supabase's free plan: a request may use about 2 s of CPU and must finish
// within 150 s. So dates are formatted with one shared formatter (making a new one per date was the
// slow part), each Gemini call has its own timeout, and the whole answer has a 100 s budget.
import { caller, cors, json } from "../_shared/owner.ts";

// Google retires model names (gemini-2.5-flash: "no longer available to new users", Nov 2026), and the
// free tier is sometimes overloaded (503) or slow, so try a few names in turn.
const MODELS = [Deno.env.get("PING_AI_MODEL") || "gemini-flash-latest", "gemini-flash-lite-latest", "gemini-2.0-flash"];
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
    sb.from("roles").select("company,designation,applied,effective_deadline,eligible,ctc,currency,cgpa_cutoff").limit(400),
    sb.from("profile").select("department,degree,cgpa,active_backlogs,interested_companies,not_interested_companies").limit(1),
  ]);
  for (const [name, r] of [["items", items], ["roles", roles], ["profile", profile]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }
  const companies = [...new Set((roles.data || []).map((r) => r.company as string))];
  // a follow-up that names no company ("same for analyst role?") is about the previous question's companies
  let names = mentioned(question, companies).slice(0, 6);
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
    `- [${i.level}] ${i.title}${i.due_at ? ` (due ${ist(i.due_at)})` : ""}${i.event_at ? ` (at ${ist(i.event_at)})` : ""}` +
    `${i.details?.venue ? ` (venue ${i.details.venue})` : ""}${myRow(i.details)}`);
  const roleLines = (roles.data || []).map((r) =>
    `- ${r.company} | ${r.designation} | applied: ${r.applied ? "yes" : "no"} | deadline: ${ist(r.effective_deadline)}` +
    ` | eligible: ${r.eligible === true ? "yes" : r.eligible === false ? "no" : "unknown"} | CTC ${r.ctc ?? "?"} ${r.currency ?? ""}`);
  const past = (iso?: string | null) => (iso && new Date(iso) < asOf ? " (already passed)" : "");
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

  const prompt = `You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete: dates in IST, times as HH:MM in 24-hour form (e.g. 20:00), money in rupees as written
(e.g. 22,00,000 or 22 LPA). For pay questions, list every component the data gives (fixed / take-home, bonuses,
ESOPs, bond) per role. When a deadline or test is before Now, say it has already passed.
If what was asked about isn't in the data at all (a company, field or record Ping doesn't have), say so in one
sentence and mention what the data does show. Never guess locations, scores, contacts or phone numbers.
When the answer is simply "no" or "nothing" (no other test, nothing due), say it short and specific, and add the
next relevant thing if there is one: "No other tests today. Next one is X on Mon 24 Nov, 10:00." Never write a
sentence about what the data does or doesn't contain for such an answer.
Time: for anything today, say whether it is already over ("the Groww test was at 15:00 today, so it's over"), coming
up ("in 2 hours") or happening now. For "anything else?"-type follow-ups answer with the count: "No, that was the only
test today" or "Two more: ...".
Conversation: "Conversation so far" below is this thread, oldest first. A short or elliptical message ("nothing
else?", "and tomorrow?", "what about slice?", "same for analyst role?", "when?", "why not?") continues the previous
turn: work out the full question from the last question and answer, then answer that. Never answer about the literal
words of the follow-up and never quote them back. If a follow-up could mean two things, answer the more likely one in
one line and offer the other in a second line; ask a question back only if neither can be answered. A message that
starts a new topic ("ok. what's due this week?") is a new question: don't carry the old topic into it.
Ping is read-only: it can never apply, withdraw, accept or decline offers, fill or submit forms, upload or change a CV,
or change anything on the ERP or anywhere else. Only when the message asks Ping to DO one of those things, start
with "Ping is read-only, so I can't" followed by what was asked, then add anything useful from the data (deadline,
form link). Follow-ups like "why not?", "same for X?" or "and Y?" are questions, never requests to act.
Now: ${DAY.format(asOf)}, ${ist(asOf.getTime()).split(", ").pop()} IST. Today is ${DAY.format(asOf)}; tomorrow is ${DAY.format(new Date(asOf.getTime() + 86_400_000))}.
All dates in the data are in ${new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", year: "numeric" }).format(asOf)} unless they say otherwise.

Profile: ${JSON.stringify(profile.data?.[0] || {})}

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

Question: ${question}`;

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
      const answer = out?.candidates?.[0]?.content?.parts?.map((p: { text?: string }) => p.text || "").join("").trim() || "";
      if (!answer) { tried.push(`${model}:empty(${out?.candidates?.[0]?.finishReason})`); continue; }
      console.log(JSON.stringify({ event: "answered", role, model, tried, history: kept.length, items: items.data?.length ?? 0,
        roles: roles.data?.length ?? 0, detail_roles: detail.data?.length ?? 0, prompt_chars: prompt.length, ms: Date.now() - t0 }));
      return json({ answer, model });
    } catch (e) {
      tried.push(`${model}:${(e as Error).name}:${Date.now() - t}ms`);
    }
  }
  console.error(JSON.stringify({ event: "no_answer", role, tried, prompt_chars: prompt.length, ms: Date.now() - t0 }));
  return json({ error: last === 503 || last === 429 ? "Gemini is busy right now, try again in a minute"
    : `no answer from Gemini (${tried.join(", ")})` }, 502);
});
