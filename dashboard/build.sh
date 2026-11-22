#!/usr/bin/env bash
# Builds the dashboard into _site/ (used by GitHub Pages, or any static host:
# build command "bash dashboard/build.sh", output folder "_site").
# Needs SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the environment for the
# real (logged-in) mode; without them the site only offers the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r requirements.txt >/dev/null 2>&1 || true
rm -rf _site && mkdir -p _site
cp dashboard/index.html dashboard/style.css dashboard/app.js dashboard/onboarding.js dashboard/names.js dashboard/live.js dashboard/today.js dashboard/forms.js supabase/functions/_shared/answer_rules.js supabase/functions/_shared/help.js dashboard/manifest.webmanifest _site/
# the installable app: icons, and a service worker that knows this build (a new deploy = a new worker and cache)
mkdir -p _site/icons && cp dashboard/icons/*.png dashboard/icons/*.svg _site/icons/
sed "s/__BUILD__/${GITHUB_SHA:-local}/" dashboard/sw.js > _site/sw.js
# the demo is the anonymised snapshot of a real run (Actions > Admin > build-demo writes it);
# the made-up sample is only a fallback for a fresh copy of the project that hasn't built one yet
if [ -s dashboard/demo-data.json ]; then cp dashboard/demo-data.json _site/; else python3 -m ping.sample _site/demo-data.json; fi
# the published copy is packed: each distinct list of allowed departments once (58 lists for 201 roles; the page
# unpacks them), only the role details the page reads, no spaces: 6.6 MB -> about 3 MB to parse on a phone.
python3 - <<'PY'
import json
d = json.load(open("_site/demo-data.json", encoding="utf-8"))
lists, index = [], {}
for r in d.get("roles", []):
    md = r.get("more_details")
    if isinstance(md, dict):                 # the page reads only the fields; the same text twice more is left out
        r["more_details"] = {"fields": md.get("fields") or {}}
    if r.get("jd_text") and r.get("jd_text") == r.get("job_description"):
        r["job_description"] = None          # the page shows jd_text first; no second copy
    key = json.dumps(r.get("allowed"), sort_keys=True)
    if key not in index:
        index[key] = len(lists)
        lists.append(r.get("allowed"))
    r["allowed"] = index[key]
d["allowed_lists"] = lists
# the roles' JD text, pay details and JD summaries (two thirds of the file) go in a second file the page fetches after
# the chat is on screen; the role sheet and the questions that need them wait for it (app.js demoDetails)
HEAVY = ("jd_text", "job_description", "more_details", "jd_summary", "selection_details")
details = {}
for r in d.get("roles", []):
    got = {k: r.pop(k) for k in HEAVY if k in r}
    if got:
        details[str(r["id"])] = got
d["details_file"] = "demo-details.json"
open("_site/demo-data.json", "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
open("_site/demo-details.json", "w", encoding="utf-8").write(json.dumps(details, ensure_ascii=False, separators=(",", ":")))
PY
python3 - <<'PY'
import json, os
cfg = {"supabaseUrl": os.environ.get("SUPABASE_URL", ""), "supabaseKey": os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")}
# push notifications: the VAPID public key (Actions > Admin > push-setup writes it; public by design)
if os.path.exists("dashboard/push-public-key.txt"):
    cfg["pushKey"] = open("dashboard/push-public-key.txt").read().strip()
build = os.environ.get("GITHUB_SHA", "local")[:7]  # lets the deploy check that the live site is this build
open("_site/config.js", "w").write("window.PING_CONFIG = " + json.dumps(cfg) + ";\nwindow.PING_BUILD = "
                                   + json.dumps(build) + ";\n")
PY
python3 setup/build_setup_page.py _site/setup.html >/dev/null   # "Set up Ping for yourself", from docs/SETUP.md
cp dashboard/PUBLIC_README.md _site/README.md   # the public repo's README
touch _site/.nojekyll                             # serve the files as they are (no Jekyll on GitHub Pages)
echo "built _site/ (real mode: $([ -n "${SUPABASE_URL:-}" ] && echo on || echo off))"
