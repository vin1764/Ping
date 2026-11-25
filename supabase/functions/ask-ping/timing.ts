// Where an answer's time goes: each stage in order (wall time between laps) and each database read on its own (reads
// that run side by side overlap, so they don't add up to their stage). Sent back with the answer as `timing` and
// logged; no question text, no data.
const BOOT = Date.now();
let served = 0;

export function timer() {
  const t0 = Date.now();
  let last = t0;
  const cold = served++ === 0;                 // the first request this instance serves: it booted for it
  const stages: Record<string, number> = {};
  const reads: Record<string, number> = {};
  return {
    lap(name: string) {
      const n = Date.now();
      stages[name] = (stages[name] || 0) + (n - last);
      last = n;
    },
    // a database read (a query builder is a thenable): its own time, whatever runs beside it
    read<T>(name: string, q: PromiseLike<T>): Promise<T> {
      const s = Date.now();
      return Promise.resolve(q).then((r) => { reads[name] = (reads[name] || 0) + (Date.now() - s); return r; });
    },
    // part of a stage that was really another (the fact check inside the wording step)
    move(from: string, to: string, ms: number) {
      const m = Math.max(0, Math.min(ms, stages[from] || 0));
      stages[from] = (stages[from] || 0) - m;
      stages[to] = (stages[to] || 0) + m;
    },
    out() { return { total: Date.now() - t0, cold, instance_age_ms: t0 - BOOT, stages, reads }; },
  };
}
