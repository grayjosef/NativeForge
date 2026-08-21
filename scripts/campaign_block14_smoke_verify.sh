#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
python - <<'PY'
from nativeforge.services.campaign_block14_smoke_runner_service import (
    run_campaign_block14_smoke,
)
result = run_campaign_block14_smoke()
print(f"{result['run_id']} {result['overall_status']} {result.get('fails')}")
raise SystemExit(0 if result["overall_status"] == "PASS" else 1)
PY
