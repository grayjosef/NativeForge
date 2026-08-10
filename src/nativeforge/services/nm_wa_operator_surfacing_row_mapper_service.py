"""Map existing NM/WA classify+match / review outputs into operator report rows.

Does not alter classify+match logic. Offline synthetic fixtures only.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_operator_review_service import (
    derive_next_check_guidance,
    derive_review_reasons,
)
from nativeforge.services.nm_wa_operator_surfacing_report_schema_service import (
    CLASSIFICATION_INCOMPLETE_PROFILE,
    CLASSIFICATION_NEEDS_OPERATOR_REVIEW,
    CONFIDENCE_PUBLIC_INFERRED_LOW,
    DISCOVERABILITY_VISIBLE,
    empty_operator_report_row,
    validate_operator_report_row,
)
from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    READINESS_NEEDS_OPERATOR_REVIEW,
)

SCHEMA_VERSION = "nf_nm_wa_operator_surfacing_row_mapper_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def map_readiness_to_classification(readiness_label: str) -> str:
    """Sprint 004: map readiness labels to operator classification labels."""
    if readiness_label == READINESS_INCOMPLETE_PROFILE:
        return CLASSIFICATION_INCOMPLETE_PROFILE
    return CLASSIFICATION_NEEDS_OPERATOR_REVIEW


def build_operator_report_row_from_review_item(
    item: dict[str, Any],
    *,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Sprint 005: build one operator report row from review-queue style item."""
    state = str(item.get("state") or item.get("state_cohort") or "UNKNOWN")
    profile_id = str(item.get("profile_fixture_key") or item.get("profile_id") or "")
    readiness = str(item.get("readiness_label") or READINESS_NEEDS_OPERATOR_REVIEW)
    missing = list(missing_fields or item.get("missing_fields") or [])
    reasons = list(item.get("review_reasons") or [])
    if not reasons:
        reasons = derive_review_reasons(
            {
                "program_areas_unknown": "program_areas" in missing,
                "grant_posture": ("UNKNOWN" if "grant_posture" in missing else "mixed"),
            }
        )
    next_checks = list(item.get("next_checks") or item.get("operator_next_check") or [])
    if not next_checks:
        next_checks = derive_next_check_guidance(reasons)

    row = empty_operator_report_row(profile_id=profile_id, state_cohort=state)
    row["classification_label"] = map_readiness_to_classification(readiness)
    row["match_readiness_label"] = readiness
    row["discoverability"] = DISCOVERABILITY_VISIBLE
    row["confidence"] = CONFIDENCE_PUBLIC_INFERRED_LOW
    row["missing_data"] = missing
    row["blockers"] = reasons
    row["operator_next_check"] = next_checks
    row["provenance_evidence_notes"] = [
        "capture_method:public_inferred",
        "evidence_codes:empty_expected_for_public_inferred",
        f"organization_name:{item.get('organization_name') or 'UNKNOWN'}",
    ]
    row["human_review_required"] = True
    row["final_eligibility_claim_allowed"] = False
    failures = validate_operator_report_row(row)
    if failures:
        raise ValueError(f"invalid operator report row: {failures}")
    return _json_safe(row)


def build_operator_report_rows(
    items: list[dict[str, Any]],
    *,
    gaps_by_profile: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Sprint 006: map many review items to operator report rows."""
    gaps = gaps_by_profile or {}
    rows: list[dict[str, Any]] = []
    for item in items:
        pid = str(item.get("profile_fixture_key") or item.get("profile_id") or "")
        rows.append(
            build_operator_report_row_from_review_item(
                item, missing_fields=gaps.get(pid)
            )
        )
    return _json_safe(rows)
