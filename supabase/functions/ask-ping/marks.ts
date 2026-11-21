// "For you" marks inside the function: the same as ping/relevance.py (same hashes, same prompt, same cache table),
// so a preference said in the chat re-marks the roles at once, and the hourly run then finds them cached.
// The role_marks cache holds hashes only and is read/written with the service key; callers never see it.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

// Kept identical to ping/relevance.py PROMPT (tests/test_prompts_doc.py checks it).
export const RELEVANCE_PROMPT = `A student at IIT Kharagpur describes the jobs they want:
<<<
{targets}
>>>
{cvs}
For each role below, decide whether it is one of the jobs they want. Judge the work the role actually does (from
the job description when there is one), not just the company. If what they want and their CVs disagree, what they
want wins. Reply with JSON only, one entry per role, in order:
[{"id": "<role id>", "relevant": true or false, "best_cv": "<label of the CV to apply with, or empty>", "reason": "at most 8 words"}]

Roles:
{roles}`;

export const CV_BLOCK = "Their CVs (label: summary):\n{lines}\n";
const JD_CHARS = 400;
const FIELDS = ["Job Profile", "Job Designation", "Profile", "Role", "Domain", "Job Type"];
const PLACEHOLDER = new RegExp(String.raw`^(?:none|null|n/?a|-+|\.+|tbd|attached|find attached|pfa(?: the)? jd|as mentioned in .{0,40}|` +
  String.raw`attached for your reference|sharing as attachment.{0,30}|will be shared.{0,60}|` +
  String.raw`(?:please )?(?:see|refer)(?: to)? .{0,40}|https?://\S+)\.?$`, "i");
const clean = (s: unknown) => String(s ?? "").replace(/\s+/g, " ").trim();
const LETTERS: Record<string, string> = { 0: "g", 1: "h", 2: "i", 3: "j", 4: "k", 5: "l", 6: "m", 7: "n", 8: "o", 9: "p" };

async function h(s: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(s));
  const hex = [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex.slice(0, 16).replace(/[0-9]/g, (d) => LETTERS[d]);
}
// the CV summaries are part of the key (they decide best_cv); same as ping/relevance.py targets_hash
export const targetsHash = (targets: string, cvs = "") => h(clean(targets).toLowerCase() + (clean(cvs) ? "\n" + clean(cvs) : ""));
export const cvsText = (cvs: any[] | null | undefined) =>
  (cvs || []).filter((c) => c?.label && c?.summary).map((c) => `- ${c.label}: ${c.summary}`).join("\n");
export const roleHash = (r: any) => h(["company", "designation", "job_description"].map((k) => clean(r[k])).join("|"));

export function noJd(jd: unknown): boolean {
  const s = clean(jd);
  return !s || PLACEHOLDER.test(s) || s.replace(/https?:\/\/\S+/g, "").trim().length < 25;
}

function roleText(r: any): string {
  const jd = noJd(r.job_description) ? "" : clean(r.job_description);
  const fields = r.more_details?.fields || {};
  const extra = FIELDS.filter((k) => fields[k]).map((k) => `${k}: ${clean(fields[k]).slice(0, 120)}`);
  return `Company: ${clean(r.company)}\nTitle: ${clean(r.designation)}` + (extra.length ? "\n" + extra.join("\n") : "") +
    `\nJob description: ${jd ? jd.slice(0, JD_CHARS) : "(none given; judge on the title)"}`;
}

export function service() {
  const k = Deno.env.get("PING_SERVICE_KEY") || Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  return k ? createClient(Deno.env.get("SUPABASE_URL")!, k) : null;
}

export type Mark = { relevant: boolean; reason: string; jd_missing: boolean; best_cv: string };

// Marks for these roles and targets: from the cache, and the missing ones in ONE Gemini call (then cached).
export async function markRoles(roles: any[], targets: string, models: string[], key: string, budgetMs: number, cvs = ""):
  Promise<{ marks: Map<string, Mark>; classified: number; cached: number; error?: string }> {
  const marks = new Map<string, Mark>();
  const svc = service();
  if (!clean(targets) || !svc) return { marks, classified: 0, cached: 0, error: svc ? undefined : "no service key" };
  const th = await targetsHash(targets, cvs);
  const labels = cvs.split("\n").filter((l) => l.startsWith("- ")).map((l) => l.slice(2).split(":")[0]);
  const hashes = new Map<string, string>();
  for (const r of roles) hashes.set(r.id, await roleHash(r));
  const { data: rows } = await svc.from("role_marks").select("role_hash,relevant,reason,jd_missing,best_cv").eq("targets_hash", th).limit(5000);
  const byHash = new Map((rows || []).map((x: any) => [x.role_hash, x]));
  const todo = roles.filter((r) => !byHash.has(hashes.get(r.id)!));
  for (const r of roles) {
    const c: any = byHash.get(hashes.get(r.id)!);
    if (c) marks.set(r.id, { relevant: c.relevant, reason: c.reason || "", jd_missing: !!c.jd_missing, best_cv: c.best_cv || "" });
  }
  const cached = marks.size;
  if (!todo.length) return { marks, classified: 0, cached };
  const listing = todo.map((r) => `[id: ${r.id}]\n${roleText(r)}`).join("\n\n");
  const prompt = RELEVANCE_PROMPT.replace("{targets}", clean(targets).slice(0, 600))
    .replace("{cvs}", cvs ? CV_BLOCK.replace("{lines}", cvs) : "").replace("{roles}", listing);
  const t0 = Date.now();
  let error = "";
  for (const model of models) {
    const left = budgetMs - (Date.now() - t0);
    if (left < 5_000) break;
    try {
      const r = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`, {
        method: "POST", signal: AbortSignal.timeout(left),
        headers: { "Content-Type": "application/json", "x-goog-api-key": key },
        body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0, maxOutputTokens: 16384, responseMimeType: "application/json" } }),
      });
      if (!r.ok) { error = `${model}:${r.status}`; continue; }
      const out = await r.json();
      const text = out?.candidates?.[0]?.content?.parts?.map((p: any) => p.text || "").join("") || "";
      const m = text.match(/\[[\s\S]*\]/);
      if (!m) { error = `${model}:no JSON`; continue; }
      const answer = JSON.parse(m[0]);
      const save: any[] = [];
      for (const a of answer) {
        const r = todo.find((x) => x.id === a?.id);
        if (!r || typeof a.relevant !== "boolean") continue;
        const cv = clean(a.best_cv);
        const mark = { relevant: a.relevant, reason: clean(a.reason).split(" ").slice(0, 8).join(" ").replace(/[.,;]+$/, ""),
                       jd_missing: noJd(r.job_description), best_cv: labels.includes(cv) ? cv : "" };
        marks.set(r.id, mark);
        save.push({ targets_hash: th, role_hash: hashes.get(r.id), ...mark, model });
      }
      if (save.length) {
        const uniq = [...new Map(save.map((s) => [s.role_hash, s])).values()];
        const { error: e } = await svc.from("role_marks").upsert(uniq, { onConflict: "targets_hash,role_hash" });
        if (e) console.error(JSON.stringify({ event: "role_marks_save_failed", error: e.message }));
      }
      return { marks, classified: save.length, cached };
    } catch (e) {
      error = `${model}:${(e as Error).name}`;
    }
  }
  return { marks, classified: 0, cached, error };
}
