#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
python - <<'PY'
from nativeforge.services.campaign_block64_smoke_runner_service import (
    run_campaign_block64_smoke,
)
r = run_campaign_block64_smoke()
print(f"{r['run_id']} {r['overall_status']} {r.get('fails')}")
raise SystemExit(0 if r["overall_status"] == "PASS" else 1)
PY
