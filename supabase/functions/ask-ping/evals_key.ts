// Two Gemini keys. Students and demo visitors use GEMINI_API_KEY (the live key). Evals and Admin checks use
// GEMINI_API_KEY_EVALS, so their traffic never touches the live key's quota: they send x-ping-evals, an
// HMAC-SHA256 of "ping-evals" made with the evals key (proof they hold it; the key itself is never sent).
// A request that claims to be an eval but can't prove it is refused, never quietly answered on the live key.
export async function evalsProof(evalsKey: string): Promise<string> {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(evalsKey), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode("ping-evals")));
  return [...sig].map((b) => b.toString(16).padStart(2, "0")).join("");
}
