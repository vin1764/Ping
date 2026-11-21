import { describe, merge, parsePrefs } from "./prefs.ts";
import { roleHash, targetsHash } from "./marks.ts";
const eq = (a: unknown, b: unknown) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${JSON.stringify(a)} != ${JSON.stringify(b)}`); };
const NONE = { targets: null, reminder_hours: null, list_other_roles: null };

Deno.test("preference statements are saved; questions are not", () => {
  eq(parsePrefs("only show me product, consulting and analyst roles", NONE).changes,
     { targets: "product, consulting and analyst roles" });
  const cur = { ...NONE, targets: "product, consulting and analyst roles" };
  eq(parsePrefs("also include data scientist roles", cur).changes.targets,
     "product, consulting and analyst roles; also data scientist roles");
  eq(parsePrefs("don't count SDE as relevant", cur).changes.targets, "product, consulting and analyst roles; not SDE");
  eq(parsePrefs("remind me 3 hours before deadlines", NONE).changes, { reminder_hours: 3 });
  eq(parsePrefs("stop listing other roles separately", NONE).changes, { list_other_roles: false });
  eq(parsePrefs("what are my preferences?", NONE).kind, "show");
  eq(parsePrefs("reset my preferences", cur).changes, { targets: null, reminder_hours: 2, list_other_roles: true });
  // questions that mention roles change nothing
  for (const q of ["any product roles tonight?", "anything for product roles tonight", "show me product roles closing tonight",
                   "which of these are relevant to me", "what's due tonight that's relevant to me", "apply to groww for me",
                   "include?", "is slice a product role?"]) {
    eq([q, parsePrefs(q, cur).kind], [q, "none"]);
  }
  // a preference and a question in one message
  const both = parsePrefs("only show me product roles. what's due tonight?", NONE);
  eq([both.changes, both.rest], [{ targets: "product roles" }, "what's due tonight?"]);
});

Deno.test("additive edits merge, not overwrite", () => {
  eq(merge("product roles; not SDE", "SDE", "also"), "product roles; also SDE");
  eq(merge("product roles; also SDE", "SDE", "not"), "product roles; not SDE");
  eq(merge(null, "finance roles", "also"), "finance roles");
  eq(describe({ targets: "x", reminder_hours: 3, list_other_roles: false }, { reminder_hours: 3 }), "reminders 3 h before");
});

Deno.test("cache keys match ping/relevance.py", async () => {
  // values from: python -c "from ping.relevance import *; print(targets_hash(...), role_hash(...))"
  eq(await targetsHash("  Backend   and Infrastructure roles "), "pboaociipcpjndci");
  eq(await roleHash({ company: "Alpha", designation: "Software Engineer I", job_description: "Build  backend services." }),
     "enobgabombhdlgoh");
});
