#!/usr/bin/env bash
# NM pilot staging verify — offline fixtures only; no live ingest / no source activation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
export NF_LIVE_SOURCE_INGESTION=0
python - <<'PY'
from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_honesty_regression_service import (
    run_nm_pilot_honesty_regression,
)

grants = [
    {
        "grant_id": "nm-staging-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]
block = run_nm_pilot_classify_match_block(grants=grants, allow_live_completeness_fetch=False)
assert block["all_needs_operator_review"] is True
assert block["profile_count"] == 22
hon = run_nm_pilot_honesty_regression(grants=grants)
assert hon["verification_passed"]
print("nm_pilot_staging_verify: OK")
PY
