#!/usr/bin/env bash
# Combined NM/WA pilot staging verify — offline only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate
bash scripts/nm_pilot_staging_verify.sh
bash scripts/wa_pilot_staging_verify.sh
python - <<'PY'
from nativeforge.services.nm_wa_classify_match_closeout_packet_service import (
    build_nm_wa_classify_match_closeout_packet,
)
from nativeforge.services.nm_wa_validation_rollup_service import (
    build_nm_wa_validation_rollup,
)

grants = [
    {
        "grant_id": "nm-wa-combined-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]
pkt = build_nm_wa_classify_match_closeout_packet(grants=grants)
assert pkt["nm_wired"] and pkt["wa_wired"]
assert pkt["pushed"] is False
vr = build_nm_wa_validation_rollup()
assert vr["full_suite_run"] is False
print("nm_wa_pilot_staging_verify: OK")
PY
