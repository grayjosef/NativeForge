#!/usr/bin/env bash
# Operator surfacing staging verify — offline only; no live ingest/activation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
export NF_LIVE_SOURCE_INGESTION=0
python3 - <<'PY'
from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)
from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)
from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)
from nativeforge.services.nm_wa_operator_surfacing_closeout_packet_service import (
    build_operator_surfacing_closeout_packet,
)

grants = [
    {
        "grant_id": "os-staging-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]
nm = build_nm_operator_surfacing_report(grants=grants)
wa = build_wa_operator_surfacing_report(grants=grants)
q = build_combined_operator_review_queue(grants=grants)
pkt = build_operator_surfacing_closeout_packet(grants=grants)
assert nm["total_profiles"] == 22
assert wa["total_profiles"] == 29
assert q["combined_profile_count"] == 51
assert pkt["scoring_match_logic_changed"] is False
assert pkt["pushed"] is False
assert all(pkt["hard_invariants"].values())
print("nm_wa_operator_surfacing_staging_verify: OK")
PY
