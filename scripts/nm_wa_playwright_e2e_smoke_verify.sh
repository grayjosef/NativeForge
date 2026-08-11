#!/usr/bin/env bash
# Real Playwright E2E smoke for NM/WA operator demo.
# Produces run_id + per-screen PASS/FAIL JSON under artifacts/nm_wa_playwright_smoke/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

python3 - <<'PY'
import json
from pathlib import Path

from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)

result = run_playwright_nm_wa_smoke()
run_id = result["run_id"]
print(f"run_id={run_id}")
print(f"overall_status={result['overall_status']}")
print(f"smoke_mode={result['smoke_mode']}")
print(f"demo_route_path={result['demo_route_path']}")
print(f"headless={result['headless']}")
for s in result["screens"]:
    print(f"screen={s['screen']} status={s['status']} detail={s['detail']}")
if result.get("failures"):
    print("failures=" + ",".join(result["failures"]))
for p in result.get("artifact_paths") or []:
    print(f"artifact={p}")
if result["overall_status"] == "FAIL":
    raise SystemExit(1)
PY
