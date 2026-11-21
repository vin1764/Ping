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
  eq(parsePrefs("reset my preferences", cur).changes, { targets: null, reminder_hours: 2, list_other_roles: true,
    feed_mode: "personal", check_every_minutes: 60, check_from: "06:00", check_to: "01:00" });
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
  // a role whose JD Ping found elsewhere (roles.jd_text) is keyed on that text: it gets marked again
  eq(await roleHash({ company: "Alpha", designation: "Software Engineer I", job_description: "Find Attached",
                      jd_text: "Build backend services in Go and run them on Kubernetes." }), "jhklhhanbjlpjbec");
});

Deno.test("schedule and feed preferences", () => {
  eq(parsePrefs("check every 30 minutes", NONE).changes, { check_every_minutes: 30 });
  eq(parsePrefs("check every 2 hours", NONE).changes, { check_every_minutes: 120 });
  eq(parsePrefs("check hourly", NONE).changes, { check_every_minutes: 60 });
  eq(parsePrefs("only check between 8 and 22", NONE).changes, { check_from: "08:00", check_to: "22:00" });
  eq(parsePrefs("check from 7am to 11pm", NONE).changes, { check_from: "07:00", check_to: "23:00" });
  eq(parsePrefs("remind me 4 hours before deadlines", NONE).changes, { reminder_hours: 4 });
  eq(parsePrefs("remind me the day before", NONE).changes, { reminder_hours: 24 });
  eq(parsePrefs("show me everything", NONE).changes, { feed_mode: "all" });
  eq(parsePrefs("only what fits me", NONE).changes, { feed_mode: "personal" });
  for (const q of ["when do you check the erp?", "how often do you check?", "is there anything every hour?"]) {
    eq([q, parsePrefs(q, NONE).kind], [q, "none"]);
  }
});
