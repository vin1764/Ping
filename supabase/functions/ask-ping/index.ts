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
const PER_MODEL_MS = 45_000;

const FMT = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", weekday: "short", day: "2-digit",
  month: "short", hour: "2-digit", minute: "2-digit" });
const ist = (iso?: string | number | null) => (iso ? FMT.format(new Date(iso)) : "");

// Pay and bond lines from a role's "more details" (CTC breakup, take home, bonuses, ESOPs, bond...)
const PAY = /ctc|salary|gross|take ?home|bonus|bond|stipend|esop|stock|perk|benefit|variable|incentive|retention|relocation|joining|allowance|compensation|cost to company/i;
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
const LEGAL = new Set(["private", "pvt", "limited", "ltd", "inc", "llp", "india", "the", "and", "co", "company", "technologies", "services", "solutions"]);

function mentioned(question: string, companies: string[]): string[] {
  const q = ` ${norm(question)} `;
  return companies.filter((c) => {
    const n = norm(c);
    if (n && q.includes(` ${n} `)) return true;
    const first = n.split(" ").find((w) => w.length >= 3 && !LEGAL.has(w));
    return !!first && q.includes(` ${first} `);
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
  // The reviewer sees a snapshot; "tomorrow" means the day after the snapshot, like on the page.
  const asOf = role === "reviewer" && body?.as_of && !isNaN(Number(new Date(body.as_of))) ? new Date(body.as_of) : new Date();

  const [items, roles, profile] = await Promise.all([
    sb.from("items").select("level,category,title,company,due_at,event_at,first_seen,details")
      .neq("level", "hidden").eq("dismissed", false).order("first_seen", { ascending: false }).limit(150),
    sb.from("roles").select("company,designation,applied,effective_deadline,eligible,ctc,currency,cgpa_cutoff").limit(400),
    sb.from("profile").select("department,degree,cgpa,active_backlogs,interested_companies,not_interested_companies").limit(1),
  ]);
  for (const [name, r] of [["items", items], ["roles", roles], ["profile", profile]] as const) {
    if (r.error) console.error(JSON.stringify({ event: "read_failed", table: name, error: r.error.message }));
  }
  const names = mentioned(question, [...new Set((roles.data || []).map((r) => r.company as string))]).slice(0, 6);
  const detail = names.length
    ? await sb.from("roles").select("company,designation,more_details,bond,contract,backlog_rule").in("company", names).limit(20)
    : { data: [] as any[], error: null };
  if (detail.error) console.error(JSON.stringify({ event: "read_failed", table: "roles(details)", error: detail.error.message }));

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
  const detailLines = (detail.data || []).map((r: any) =>
    `- ${r.company} | ${r.designation} | ${payLines(r.more_details) || "no pay details given"}` +
    `${r.bond ? ` | bond: ${r.bond}` : ""}${r.contract ? ` | contract: ${r.contract}` : ""}`);

  const prompt = `You are Ping, a placement assistant for one IIT Kharagpur student. Answer ONLY from the data below.
Be short and concrete: dates in IST, money in rupees as written (e.g. 22,00,000 or 22 LPA). For pay questions, list
every component the data gives (fixed / take-home, bonuses, ESOPs, bond) per role.
If the answer isn't in the data, say so in one sentence and mention what the data does show.
Now: ${ist(asOf.getTime())} IST.

Profile: ${JSON.stringify(profile.data?.[0] || {})}

Feed (things for this student):
${feed.join("\n") || "(empty)"}

All roles in the companies list:
${roleLines.join("\n") || "(empty)"}
${detailLines.length ? `\nPay and bond details for the companies in the question (from the ERP's "more details"):\n${detailLines.join("\n")}\n` : ""}
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
      console.log(JSON.stringify({ event: "answered", role, model, tried, items: items.data?.length ?? 0,
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
