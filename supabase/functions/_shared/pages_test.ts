import { assertEquals } from "jsr:@std/assert@1";
import { inChunks, PAGE, pageAll } from "./pages.ts";

// a fake query over n rows that, like the database's API, returns at most 1,000 rows per request
const fake = (n: number, calls: number[]) => () => ({
  range: (a: number, b: number) => { calls.push(a); return Promise.resolve({ data: Array.from({ length: Math.max(0, Math.min(b, n - 1) - a + 1) }, (_, k) => a + k), error: null }); },
});

Deno.test("pageAll returns every row past the 1,000-row cap", async () => {
  for (const n of [0, 5, 999, 1000, 1001, 2500, 4000]) {
    const calls: number[] = [];
    const r = await pageAll(fake(n, calls));
    assertEquals(r.data.length, n, `n=${n}`);
    assertEquals(r.data[n - 1], n ? n - 1 : undefined);
    assertEquals(calls.length, Math.max(2, Math.floor(n / PAGE) + 1));
  }
});

Deno.test("inChunks asks a long list in parts and joins them", async () => {
  const vals = Array.from({ length: 400 }, (_, i) => `h${i}`);
  const seen: number[] = [];
  const r = await inChunks((part) => { seen.push(part.length); return Promise.resolve({ data: part, error: null }); }, vals);
  assertEquals(r.data.length, 400);
  assertEquals(seen, [150, 150, 100]);
});
