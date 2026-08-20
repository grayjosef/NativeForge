#!/usr/bin/env bash
# Offline verify for NOFO showcase surfaces (no live ingest).
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export NO_COLOR=1
python - <<'PY'
from nativeforge.services.nofo_showcase_smoke_runner_service import run_nofo_showcase_offline_smoke
r = run_nofo_showcase_offline_smoke()
print(r["run_id"], r["status"], r.get("failed_surfaces"))
raise SystemExit(0 if r["status"] == "PASS" else 1)
PY
