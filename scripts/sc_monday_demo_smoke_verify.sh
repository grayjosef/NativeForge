#!/usr/bin/env bash
# Offline SC Monday customer demo smoke — no network/live ingest/activation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT_DIR="${1:-$ROOT/artifacts/sc_monday_smoke}"
mkdir -p "$OUT_DIR"
# shellcheck disable=SC1091
source .venv/bin/activate

python3 - "$OUT_DIR" <<'PY'
import sys
from pathlib import Path
from nativeforge.services.sc_monday_demo_smoke_runner_service import (
    run_sc_monday_demo_smoke,
    write_sc_monday_demo_smoke_result,
)

out_dir = Path(sys.argv[1])
result = run_sc_monday_demo_smoke()
path = write_sc_monday_demo_smoke_result(result, out_dir=out_dir)
print(f"run_id={result['run_id']}")
print(f"overall_status={result['overall_status']}")
print(f"result_path={path}")
for s in result["surfaces"]:
    print(f"surface={s['surface']} status={s['status']} detail={s['detail']}")
if result["overall_status"] != "PASS":
    raise SystemExit(1)
PY
