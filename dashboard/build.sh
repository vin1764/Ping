#!/usr/bin/env bash
# Builds the dashboard into _site/ (used by GitHub Pages, or any static host:
# build command "bash dashboard/build.sh", output folder "_site").
# Needs SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the environment for the
# real (logged-in) mode; without them the site only offers the demo.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q -r requirements.txt >/dev/null 2>&1 || true
rm -rf _site && mkdir -p _site
cp dashboard/index.html dashboard/style.css dashboard/app.js _site/
python3 -m ping.sample _site/demo-data.json
python3 - <<'PY'
import json, os
cfg = {"supabaseUrl": os.environ.get("SUPABASE_URL", ""), "supabaseKey": os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")}
open("_site/config.js", "w").write("window.PING_CONFIG = " + json.dumps(cfg) + ";\n")
PY
echo "built _site/ (real mode: $([ -n "${SUPABASE_URL:-}" ] && echo on || echo off))"
