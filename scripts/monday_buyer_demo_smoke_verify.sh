#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export NO_COLOR=1
python - <<'PY'
from nativeforge.services.monday_buyer_demo_smoke_runner_service import (
    run_monday_buyer_demo_smoke,
)
r = run_monday_buyer_demo_smoke()
print(r["run_id"], r["status"], r.get("failed_surfaces"))
raise SystemExit(0 if r["status"] == "PASS" else 1)
PY
