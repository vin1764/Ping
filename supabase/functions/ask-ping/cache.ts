// The heavy reads every answer needs (roles, items, notices, mail, forms) and the "For you" marks, kept for a few
// minutes (5) in this function instance, one copy for the owner and one for the demo (the database's own rules give every
// demo session the same demo rows). A copy is used only while its freshness key still matches what the database says
// now: the latest run (a check that started or finished) and the number and newest of your undismissed items (a
// dismissal, a new item). While a check is running nothing is kept. So an answer from the copy is the answer fresh
// reads would give. Preferences, feedback lists, the student profile and the thread are never kept: read each time.
export const TTL_MS = 5 * 60_000;

type Entry = { key: string; at: number; data: any };
const store = new Map<string, Entry>();

// a copy young enough to try (the freshness key is checked once the probe is back)
export function peek(scope: string): Entry | null {
  const e = store.get(scope);
  return e && Date.now() - e.at <= TTL_MS ? e : null;
}

// nothing kept at all (a fresh instance): the heavy reads start before the login check is back
export function empty(): boolean {
  for (const e of store.values()) if (Date.now() - e.at <= TTL_MS) return false;
  return true;
}

export function keep(scope: string, key: string | null, data: any) {
  if (!key) { store.delete(scope); return; }
  store.set(scope, { key, at: Date.now(), data });
}

// the freshness key from the probe: null while a check is running (nothing is kept then)
export function freshKey(run: any, count: number | null, newest: string | null): string | null {
  if (run && run.started_at && !run.finished_at) return null;
  return `${run?.started_at || "-"}|${run?.finished_at || "-"}|${count ?? "-"}|${newest || "-"}`;
}

export function clear() { store.clear(); }
