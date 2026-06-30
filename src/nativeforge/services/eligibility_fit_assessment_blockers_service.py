"""Sprint 199: blockers contract for eligibility fit assessment."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_blockers_v1"

BLOCKER_MISSING_PROFILE = "missing_applicant_profile"
BLOCKER_MISSING_DEADLINE = "missing_application_deadline"
BLOCKER_MISSING_DOCUMENTATION = "missing_documentation"
BLOCKER_ELIGIBILITY_EVIDENCE_GAP = "eligibility_evidence_gap"
BLOCKER_GEOGRAPHY_MISMATCH = "geography_mismatch"
BLOCKER_CAPACITY_GAP = "capacity_gap"
BLOCKER_DEADLINE_PASSED = "deadline_passed"
BLOCKER_RECOGNITION_TIER_MISMATCH = "recognition_tier_mismatch"
BLOCKER_ELIGIBILITY_CONDITION_MISMATCH = "eligibility_condition_mismatch"

BLOCKER_CODES: tuple[str, ...] = (
    BLOCKER_MISSING_PROFILE,
    BLOCKER_MISSING_DEADLINE,
    BLOCKER_MISSING_DOCUMENTATION,
    BLOCKER_ELIGIBILITY_EVIDENCE_GAP,
    BLOCKER_RECOGNITION_TIER_MISMATCH,
    BLOCKER_ELIGIBILITY_CONDITION_MISMATCH,
    BLOCKER_GEOGRAPHY_MISMATCH,
    BLOCKER_CAPACITY_GAP,
    BLOCKER_DEADLINE_PASSED,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def is_valid_blocker_code(code: str) -> bool:
    return code in BLOCKER_CODES


def build_blockers_assessment(
    *,
    blocker_codes: list[str],
) -> dict[str, Any]:
    valid = sorted({c for c in blocker_codes if is_valid_blocker_code(c)})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "blocker_count": len(valid),
            "blocker_codes": valid,
            "application_blocked": bool(valid),
        }
    )
