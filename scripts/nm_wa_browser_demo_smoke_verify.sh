#!/usr/bin/env bash
# Demo-runtime NM/WA browser/UI smoke runner.
# Produces a real run_id + per-screen PASS/FAIL.
# Playwright remains NOT_RUN (not installed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-$ROOT/artifacts/nm_wa_browser_smoke}"
mkdir -p "$OUT_DIR"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

python3 - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)

out_dir = Path(sys.argv[1])
result = run_nm_wa_browser_demo_smoke()
run_id = result["run_id"]
out_path = out_dir / f"{run_id}.json"
out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"run_id={run_id}")
print(f"overall_status={result['overall_status']}")
print(f"smoke_mode={result['smoke_mode']}")
print(f"playwright_status={result['playwright_status']}")
print(f"result_path={out_path}")
for s in result["screens"]:
    print(f"screen={s['screen']} status={s['status']} detail={s['detail']}")
if result.get("failures"):
    print("failures=" + ",".join(result["failures"]))
if result["overall_status"] == "FAIL":
    raise SystemExit(1)
PY
