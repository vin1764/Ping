// One client for chat models behind an OpenAI-compatible API (Groq today). Server-side only: the key is a Supabase
// function secret and never reaches the browser. Returns what happened, never throws.
export type ChatResult = { text: string; status: number; ms: number; finish?: string; error?: string };

export async function chatComplete(opts: {
  baseUrl: string; key: string; model: string; prompt: string; timeoutMs: number; maxTokens?: number;
  extra?: Record<string, unknown>;
}): Promise<ChatResult> {
  const t = Date.now();
  try {
    const r = await fetch(`${opts.baseUrl.replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      signal: AbortSignal.timeout(opts.timeoutMs),
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${opts.key}` },
      body: JSON.stringify({ model: opts.model, temperature: 0.2, max_tokens: opts.maxTokens ?? 1200,
                             messages: [{ role: "user", content: opts.prompt }], ...(opts.extra || {}) }),
    });
    if (!r.ok) return { text: "", status: r.status, ms: Date.now() - t, error: (await r.text()).slice(0, 300) };
    const out = await r.json();
    const choice = out?.choices?.[0];
    return { text: String(choice?.message?.content || "").trim(), status: r.status, ms: Date.now() - t, finish: choice?.finish_reason };
  } catch (e) {
    return { text: "", status: 0, ms: Date.now() - t, error: (e as Error).name };
  }
}
