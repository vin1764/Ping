#!/usr/bin/env bash
# Builds the dashboard into _site/ (used by GitHub Pages, or any static host:
# build command "bash dashboard/build.sh", output folder "_site").
# Needs SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the environment for the
# real (logged-in) mode; without them the site only offers the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r requirements.txt >/dev/null 2>&1 || true
rm -rf _site && mkdir -p _site
cp dashboard/index.html dashboard/style.css dashboard/app.js dashboard/onboarding.js dashboard/names.js dashboard/live.js dashboard/today.js supabase/functions/_shared/answer_rules.js _site/
# the demo is the anonymised snapshot of a real run (Actions > Admin > build-demo writes it);
# the made-up sample is only a fallback for a fresh copy of the project that hasn't built one yet
if [ -s dashboard/demo-data.json ]; then cp dashboard/demo-data.json _site/; else python3 -m ping.sample _site/demo-data.json; fi
python3 - <<'PY'
import json, os
cfg = {"supabaseUrl": os.environ.get("SUPABASE_URL", ""), "supabaseKey": os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")}
build = os.environ.get("GITHUB_SHA", "local")[:7]  # lets the deploy check that the live site is this build
open("_site/config.js", "w").write("window.PING_CONFIG = " + json.dumps(cfg) + ";\nwindow.PING_BUILD = "
                                   + json.dumps(build) + ";\n")
PY
python3 setup/build_setup_page.py _site/setup.html >/dev/null   # "Set up Ping for yourself", from docs/SETUP.md
cp dashboard/PUBLIC_README.md _site/README.md   # the public repo's README
touch _site/.nojekyll                             # serve the files as they are (no Jekyll on GitHub Pages)
echo "built _site/ (real mode: $([ -n "${SUPABASE_URL:-}" ] && echo on || echo off))"
