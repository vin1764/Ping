// The demo snapshot (dashboard/demo-data.json) in the shape the rules read, with every source (notices' text and
// files, placement mail, form pages), at the snapshot's own time. Used by the generated evals in CI.
const fs = require("fs");
const path = require("path");

module.exports = function demoData() {
  const root = path.join(__dirname, "..", "..");
  const demo = JSON.parse(fs.readFileSync(path.join(root, "dashboard", "demo-data.json"), "utf8"));
  const asOf = JSON.parse(fs.readFileSync(path.join(root, "evals", "ask_ping", "cases.json"), "utf8")).snapshot_as_of;
  const hasTargets = !!demo.profile.targets && demo.profile.feed_mode !== "all";
  return {
    now: asOf, lastChecked: asOf, profile: demo.profile, prefs: { listOthers: demo.profile.list_other_roles !== false },
    roles: demo.roles.map((r) => ({ ...r, deadline: r.effective_deadline || r.apply_end,
      for_you: hasTargets ? !!r.relevance?.relevant : undefined, cv: r.relevance?.relevant ? r.relevance?.best_cv || null : null,
      pay: r.more_details?.fields || {}, jd_location: r.jd_summary?.location || null })),
    items: demo.items.filter((i) => !i.dismissed).map((i) => ({ ...i, hidden_because: i.details?.hidden_because,
      subject: i.details?.subject, venue: i.details?.venue, pdf: i.details?.pdf, kind: i.details?.kind, notice_time: i.details?.notice_time,
      via: i.details?.via, mail: i.details?.mail, todo: i.details?.todo })),
    notices: demo.notices,
    pdf_checks: (demo.pdf_checks || []).map((c) => ({ notice_id: c.notice_id, status: c.status, context: c.status === "jd" ? c.context : null })),
    emails: demo.emails || [], forms: demo.forms || [],
  };
};
