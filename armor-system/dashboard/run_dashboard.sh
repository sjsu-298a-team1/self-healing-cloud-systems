#!/usr/bin/env bash
# One-command launcher:  armor-system/dashboard/run_dashboard.sh [port]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${ARMOR_PYTHON:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
cd "$HERE"
exec "$PY" -m streamlit run app.py --server.port "${1:-8501}" --server.headless true --browser.gatherUsageStats false
