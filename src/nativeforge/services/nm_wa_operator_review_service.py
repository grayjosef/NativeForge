"""NM/WA operator review queue metadata — offline, no live execution."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    run_nm_wa_pilot_full_rollup,
)

SCHEMA_VERSION = "nf_nm_wa_operator_review_v1"

REVIEW_REASON_UNKNOWN_PROGRAM_AREAS = "unknown_program_areas"
REVIEW_REASON_UNKNOWN_GRANT_POSTURE = "unknown_grant_posture"
REVIEW_REASON_PUBLIC_INFERRED_PROFILE = "public_inferred_profile_requires_review"
REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE = (
    "no_final_eligibility_without_explicit_evidence"
)

NEXT_CHECK_CONFIRM_PROGRAM_AREAS = "confirm_program_areas_with_operator_evidence"
NEXT_CHECK_CONFIRM_GRANT_POSTURE = "confirm_grant_posture_with_operator_evidence"
NEXT_CHECK_HUMAN_REVIEW_MATCHES = "human_review_classify_match_rows_before_any_claim"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def derive_review_reasons(profile_row: dict[str, Any]) -> list[str]:
    """Sprint 32: review reasons from profile unknowns / capture method."""
    reasons = [REVIEW_REASON_PUBLIC_INFERRED_PROFILE]
    reasons.append(REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE)
    if profile_row.get("program_areas_unknown") is True:
        reasons.append(REVIEW_REASON_UNKNOWN_PROGRAM_AREAS)
    if profile_row.get("grant_posture") in (None, "", "UNKNOWN"):
        reasons.append(REVIEW_REASON_UNKNOWN_GRANT_POSTURE)
    return reasons


def derive_next_check_guidance(reasons: list[str]) -> list[str]:
    """Sprint 33: next-check guidance from review reasons."""
    guidance = [NEXT_CHECK_HUMAN_REVIEW_MATCHES]
    if REVIEW_REASON_UNKNOWN_PROGRAM_AREAS in reasons:
        guidance.append(NEXT_CHECK_CONFIRM_PROGRAM_AREAS)
    if REVIEW_REASON_UNKNOWN_GRANT_POSTURE in reasons:
        guidance.append(NEXT_CHECK_CONFIRM_GRANT_POSTURE)
    return guidance


def build_operator_review_queue(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 31: operator review queue metadata for NM/WA profiles."""
    full = run_nm_wa_pilot_full_rollup(grants=grants)
    items: list[dict[str, Any]] = []
    for state, rows in full["readiness"]["per_state"].items():
        for row in rows:
            gaps = [
                g
                for g in full["missing_data"]["gaps"]
                if g["profile_fixture_key"] == row["profile_fixture_key"]
            ]
            program_unknown = any("program_areas" in g["missing_fields"] for g in gaps)
            posture_unknown = any("grant_posture" in g["missing_fields"] for g in gaps)
            profile_hint = {
                "program_areas_unknown": program_unknown,
                "grant_posture": "UNKNOWN" if posture_unknown else "mixed",
            }
            reasons = derive_review_reasons(profile_hint)
            items.append(
                {
                    "state": state,
                    "profile_fixture_key": row["profile_fixture_key"],
                    "organization_name": row.get("organization_name"),
                    "readiness_label": row["readiness_label"],
                    "review_reasons": reasons,
                    "next_checks": derive_next_check_guidance(reasons),
                    "final_eligibility_claim_allowed": False,
                    "queue_priority": (
                        "high"
                        if row["readiness_label"] == READINESS_INCOMPLETE_PROFILE
                        else "normal"
                    ),
                }
            )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "item_count": len(items),
            "items": items,
            "all_require_operator_review": True,
            "offline_only": True,
        }
    )


def build_fixture_coverage_report() -> dict[str, Any]:
    """Sprint 34: fixture coverage report for NM/WA (+ references OK/SC presence)."""
    from nativeforge.services.nm_pilot_fixture_loader_service import (
        EXPECTED_PROFILE_COUNT as NM_N,
    )
    from nativeforge.services.nm_pilot_fixture_loader_service import (
        fixtures_present as nm_present,
    )
    from nativeforge.services.nm_pilot_fixture_loader_service import (
        load_nm_tribal_profiles,
    )
    from nativeforge.services.ok_pilot_fixture_loader_service import (
        fixtures_present as ok_present,
    )
    from nativeforge.services.sc_pilot_fixture_loader_service import (
        fixtures_present as sc_present,
    )
    from nativeforge.services.wa_pilot_fixture_loader_service import (
        EXPECTED_PROFILE_COUNT as WA_N,
    )
    from nativeforge.services.wa_pilot_fixture_loader_service import (
        fixtures_present as wa_present,
    )
    from nativeforge.services.wa_pilot_fixture_loader_service import (
        load_wa_tribal_profiles,
    )

    nm_count = len(load_nm_tribal_profiles()) if nm_present().get("profiles") else 0
    wa_count = len(load_wa_tribal_profiles()) if wa_present().get("profiles") else 0
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_fixture_coverage",
            "NM": {
                "present": nm_present().get("profiles", False),
                "loaded_count": nm_count,
                "expected_count": NM_N,
                "complete": nm_count == NM_N,
            },
            "WA": {
                "present": wa_present().get("profiles", False),
                "loaded_count": wa_count,
                "expected_count": WA_N,
                "complete": wa_count == WA_N,
            },
            "reference_pilots": {
                "OK_fixtures_present": ok_present().get("profiles", False),
                "SC_fixtures_present": bool(
                    sc_present().get("profiles") or sc_present().get("rules")
                ),
            },
            "classify_match_wired": {"NM": True, "WA": True},
        }
    )
