#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
python - <<'PY'
from nativeforge.services.campaign_block38_smoke_runner_service import (
    run_campaign_block38_smoke,
)
r = run_campaign_block38_smoke(run_python_sca=True)
print(
    f"{r['run_id']} {r['overall_status']} "
    f"py_sca_run={r.get('python_sca_run')} "
    f"py_passed={r.get('python_sca_passed')} "
    f"full={r.get('full_sca_passed_claimed')} fails={r.get('fails')}"
)
raise SystemExit(0 if r["overall_status"] == "PASS" else 1)
PY
