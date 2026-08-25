#!/usr/bin/env bash
# Gate 85D - regenerate Discovery Baseline X into artifacts/discovery_baseline_x/.
#
# Measurement only. This script reads committed fixtures and seed catalogs and
# writes three artifacts. It never fetches, never scrapes, and never writes to
# fixtures/.
#
# It exits nonzero rather than producing an artifact if the baseline or its
# rendered summary carries a forbidden claim - live coverage, active source
# monitoring, or an improvement figure. A refused run leaves no file behind to
# be quoted later, which is the point: the failure has to be empty-handed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate

OUT_DIR="artifacts/discovery_baseline_x"

# Fixture bytes before and after. The baseline reads committed corpora, and a
# read that turns into a write is the failure mode this campaign has already
# been bitten by (Gate 78E). Cheap to check, so check every run.
FIXTURE_HASH_BEFORE="$(find fixtures -type f -name '*.json' -print0 \
  | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"

echo "== Discovery Baseline X =="
echo "fixtures sha256 (before): ${FIXTURE_HASH_BEFORE}"

PYTHONPATH=src python - <<'PY'
import json
import sys

from nativeforge.services.discovery_baseline_x_artifact_service import (
    BaselineClaimError,
    artifact_claim_failures,
    render_baseline_x_summary,
    write_discovery_baseline_x_artifacts,
)
from nativeforge.services.discovery_baseline_x_service import (
    build_discovery_baseline_x,
)

baseline = build_discovery_baseline_x()
summary = render_baseline_x_summary(baseline)

failures = artifact_claim_failures(baseline, summary)
if failures:
    print("REFUSED: forbidden claim in Discovery Baseline X", file=sys.stderr)
    for failure in sorted(failures):
        print(f"  - {failure}", file=sys.stderr)
    raise SystemExit(2)

try:
    result = write_discovery_baseline_x_artifacts(baseline=baseline)
except BaselineClaimError as exc:
    print(f"REFUSED: {exc}", file=sys.stderr)
    raise SystemExit(2) from exc

print(json.dumps(result, indent=2, sort_keys=True))
PY

FIXTURE_HASH_AFTER="$(find fixtures -type f -name '*.json' -print0 \
  | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"
echo "fixtures sha256 (after):  ${FIXTURE_HASH_AFTER}"

if [[ "$FIXTURE_HASH_BEFORE" != "$FIXTURE_HASH_AFTER" ]]; then
  echo "FAIL: committed fixtures changed during baseline generation" >&2
  exit 3
fi

# The Python guard checks the rendered *summary* only. This scans everything
# that actually landed on disk, so a forbidden phrase reaching the JSON or the
# CSV - neither of which the in-memory guard reads - still fails the run.
for phrase in "65% improvement" "live coverage" "source monitoring active"; do
  if grep -riq -- "$phrase" "$OUT_DIR"; then
    echo "FAIL: forbidden phrase in written artifact: ${phrase}" >&2
    exit 4
  fi
done

echo "fixture-hash-stable"
echo "RESULT=PASS"
