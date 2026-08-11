#!/usr/bin/env bash
# Offline NM/WA operator surfacing smoke runner.
# Produces a real run_id and per-surface PASS/FAIL/NOT_RUN JSON.
# No network, live ingest, source activation, or migrations.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT_DIR="${1:-$ROOT/artifacts/nm_wa_smoke}"
mkdir -p "$OUT_DIR"

# shellcheck disable=SC1091
if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # Prefer project venv when present.
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

python3 - "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)

out_dir = Path(sys.argv[1])
result = run_nm_wa_operator_surfacing_smoke()
run_id = result["run_id"]
out_path = out_dir / f"{run_id}.json"
out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"run_id={run_id}")
print(f"overall_status={result['overall_status']}")
print(f"result_path={out_path}")
for s in result["surfaces"]:
    print(f"surface={s['surface']} status={s['status']} detail={s['detail']}")
if result.get("failures"):
    print("failures=" + ",".join(result["failures"]))
if result["overall_status"] == "FAIL":
    raise SystemExit(1)
PY
