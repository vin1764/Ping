// Every row of a read, a page at a time: the database's API returns at most 1,000 rows per request whatever limit is
// asked, so a single read of a longer table silently stops at its first 1,000 (25 Nov: the newest messages never
// reached the page). `make` builds the query (with its filters and a stable order); the first `ahead` pages are asked
// at once (one wait, not two), the rest one after another until a page comes back short.
export const PAGE = 1000;

// deno-lint-ignore no-explicit-any
export async function pageAll(make: () => any, ahead = 2, cap = 20_000): Promise<{ data: any[]; error: any }> {
  const out: any[] = [];
  const get = (i: number) => make().range(i * PAGE, (i + 1) * PAGE - 1);
  let first: any[] = await Promise.all(Array.from({ length: ahead }, (_, i) => get(i)));
  let i = ahead;
  for (;;) {
    for (const r of first) {
      if (r.error) return { data: out, error: r.error };
      out.push(...(r.data || []));
      if ((r.data || []).length < PAGE) return { data: out, error: null };
    }
    if (i * PAGE >= cap) return { data: out, error: null };
    first = [await get(i++)];
  }
}

// the rows whose `col` is one of `values`, asked in chunks (a long list doesn't fit in one request's address)
// deno-lint-ignore no-explicit-any
export async function inChunks(make: (part: string[]) => any, values: string[], size = 150): Promise<{ data: any[]; error: any }> {
  const parts: string[][] = [];
  for (let k = 0; k < values.length; k += size) parts.push(values.slice(k, k + size));
  const res: any[] = await Promise.all(parts.map((p) => make(p)));
  const err = res.find((r) => r.error)?.error || null;
  return { data: res.flatMap((r) => r.data || []), error: err };
}
