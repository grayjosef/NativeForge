#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
export NO_COLOR=1
python - <<'PY'
from nativeforge.services.campaign_block02_smoke_runner_service import (
    run_campaign_block02_smoke,
)
r = run_campaign_block02_smoke()
print(r["run_id"], r["status"], r.get("failed_surfaces"))
raise SystemExit(0 if r["status"] == "PASS" else 1)
PY
