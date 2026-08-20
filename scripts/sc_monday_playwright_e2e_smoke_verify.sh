#!/usr/bin/env bash
# SC Monday Playwright E2E smoke — headless Chromium, offline demo route.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

python3 <<'PY'
from nativeforge.services.sc_monday_playwright_smoke_runner_service import (
    run_playwright_sc_monday_smoke,
)

result = run_playwright_sc_monday_smoke()
print(f"run_id={result['run_id']}")
print(f"overall_status={result['overall_status']}")
print(f"smoke_mode={result['smoke_mode']}")
print(f"demo_route_path={result['demo_route_path']}")
print(f"headless={result['headless']}")
for s in result["surfaces"]:
    print(f"screen={s['surface']} status={s['status']} detail={s['detail']}")
print(f"artifact={result['artifact_log']}")
print(f"artifact={result['artifact_json']}")
if result["overall_status"] != "PASS":
    raise SystemExit(1)
PY
