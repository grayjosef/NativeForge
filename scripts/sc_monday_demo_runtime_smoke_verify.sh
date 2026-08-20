#!/usr/bin/env bash
# SC Monday demo-runtime smoke (static vitest lane). Playwright remains separate.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

python3 <<'PY'
from nativeforge.services.sc_monday_demo_runtime_smoke_runner_service import (
    run_sc_monday_demo_runtime_smoke,
)

result = run_sc_monday_demo_runtime_smoke()
print(f"run_id={result['run_id']}")
print(f"overall_status={result['overall_status']}")
print(f"smoke_mode={result['smoke_mode']}")
print(f"playwright_status={result['playwright_status']}")
for s in result["screens"]:
    print(f"screen={s['screen']} status={s['status']} detail={s['detail']}")
if result["overall_status"] != "PASS":
    raise SystemExit(1)
PY
