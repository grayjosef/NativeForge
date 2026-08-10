"""Shared NM/WA pilot rollup — offline batch classify+match summary (no live exec)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as NM_EXPECTED,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    fixtures_present as nm_fixtures_present,
)
from nativeforge.services.wa_pilot_classify_match_orchestrator_service import (
    run_wa_pilot_classify_match_block,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as WA_EXPECTED,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    fixtures_present as wa_fixtures_present,
)

SCHEMA_VERSION = "nf_nm_wa_pilot_rollup_v1"

# Conservative readiness — never claim ready without evidence + operator review.
READINESS_NEEDS_OPERATOR_REVIEW = "needs_operator_review"
READINESS_INCOMPLETE_PROFILE = "incomplete_profile_data"
READINESS_NOT_READY = "not_ready_for_final_claim"

_DEFAULT_SYNTH_GRANTS: list[dict[str, Any]] = [
    {
        "grant_id": "nm-wa-rollup-001",
        "opportunity_title": "Federal Tribal Discretionary Support",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nm_wa_pilot_rollup_skeleton() -> dict[str, Any]:
    """Sprint 21: contract skeleton describing NM/WA rollup surface."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "states": ["NM", "WA"],
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
            "fixtures": {
                "NM": {
                    "present": nm_fixtures_present().get("profiles", False),
                    "expected_profile_count": NM_EXPECTED,
                },
                "WA": {
                    "present": wa_fixtures_present().get("profiles", False),
                    "expected_profile_count": WA_EXPECTED,
                },
            },
            "capabilities": {
                "batch_classify_match_summary": True,
                "conservative_readiness_labels": True,
                "missing_data_reporting": True,
                "provenance_confidence_reporting": True,
            },
        }
    )


def _run_state_block(
    state: str,
    *,
    grants: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    corpus = grants if grants is not None else _DEFAULT_SYNTH_GRANTS
    if state == "NM":
        return run_nm_pilot_classify_match_block(
            grants=corpus,
            allow_live_completeness_fetch=False,
        )
    if state == "WA":
        return run_wa_pilot_classify_match_block(
            grants=corpus,
            allow_live_completeness_fetch=False,
        )
    raise ValueError(f"unsupported rollup state: {state!r}")


def build_batch_classify_match_summary(
    *,
    grants: list[dict[str, Any]] | None = None,
    states: list[str] | None = None,
) -> dict[str, Any]:
    """Sprint 22: batch classify+match summary across NM/WA (offline)."""
    selected = states or ["NM", "WA"]
    per_state: dict[str, Any] = {}
    total_matches = 0
    total_profiles = 0
    for state in selected:
        block = _run_state_block(state, grants=grants)
        per_state[state] = {
            "profile_count": block["profile_count"],
            "grant_count": block["grant_count"],
            "match_count": len(block["matches"]),
            "all_needs_operator_review": block["all_needs_operator_review"],
            "grant_posture_advisory_only": block["grant_posture_advisory_only"],
            "program_fit_summary": block.get("program_fit_summary"),
        }
        total_matches += len(block["matches"])
        total_profiles += int(block["profile_count"])
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_batch_summary",
            "offline_only": True,
            "states": selected,
            "per_state": per_state,
            "total_profile_count": total_profiles,
            "total_match_count": total_matches,
            "all_needs_operator_review": True,
        }
    )


def assign_conservative_readiness_label(profile_row: dict[str, Any]) -> str:
    """Sprint 23: conservative readiness — never final-claim without review."""
    if profile_row.get("program_areas_unknown") is True:
        return READINESS_INCOMPLETE_PROFILE
    if profile_row.get("grant_posture") in (None, "", "UNKNOWN"):
        return READINESS_INCOMPLETE_PROFILE
    # Public-inferred pilot profiles always require operator review.
    return READINESS_NEEDS_OPERATOR_REVIEW


def build_conservative_readiness_report(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 23: readiness labels for NM/WA per-profile rollup."""
    labels: dict[str, list[dict[str, Any]]] = {"NM": [], "WA": []}
    for state in ("NM", "WA"):
        block = _run_state_block(state, grants=grants)
        for row in block["per_profile"]:
            label = assign_conservative_readiness_label(row)
            labels[state].append(
                {
                    "profile_fixture_key": row["profile_fixture_key"],
                    "organization_name": row.get("organization_name"),
                    "readiness_label": label,
                    "final_eligibility_claim_allowed": False,
                    "match_label": LABEL_NEEDS_OPERATOR_REVIEW,
                }
            )
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_readiness",
            "final_eligibility_claim_allowed": False,
            "not_ready_sentinel": READINESS_NOT_READY,
            "per_state": labels,
            "all_require_operator_review": True,
        }
    )


def build_missing_data_report(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 24: missing/unknown applicant data remains discoverable."""
    gaps: list[dict[str, Any]] = []
    for state in ("NM", "WA"):
        block = _run_state_block(state, grants=grants)
        for row in block["per_profile"]:
            missing: list[str] = []
            if row.get("program_areas_unknown") is True:
                missing.append("program_areas")
            if row.get("grant_posture") in (None, "", "UNKNOWN"):
                missing.append("grant_posture")
            if missing:
                gaps.append(
                    {
                        "state": state,
                        "profile_fixture_key": row["profile_fixture_key"],
                        "organization_name": row.get("organization_name"),
                        "missing_fields": missing,
                        "remains_in_classify_match_outputs": True,
                        "forces_operator_review": True,
                    }
                )
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_missing_data",
            "gap_count": len(gaps),
            "gaps": gaps,
            "unknown_data_never_dropped": True,
        }
    )


def build_provenance_confidence_report(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 25: provenance/confidence reporting for NM/WA pilots."""
    rows: list[dict[str, Any]] = []
    for state in ("NM", "WA"):
        block = _run_state_block(state, grants=grants)
        for row in block["per_profile"]:
            rows.append(
                {
                    "state": state,
                    "profile_fixture_key": row["profile_fixture_key"],
                    "organization_name": row.get("organization_name"),
                    "capture_method": row.get("capture_method"),
                    "confidence": "public_inferred_low",
                    "evidence_codes_empty_expected": True,
                    "operator_review_required": True,
                }
            )
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_provenance",
            "row_count": len(rows),
            "rows": rows,
            "default_confidence": "public_inferred_low",
            "no_high_confidence_without_evidence": True,
        }
    )


def run_nm_wa_pilot_full_rollup(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Combined rollup for later closeout / operator review layers."""
    return _json_safe(
        {
            "schema_version": f"{SCHEMA_VERSION}_full",
            "skeleton": build_nm_wa_pilot_rollup_skeleton(),
            "batch_summary": build_batch_classify_match_summary(grants=grants),
            "readiness": build_conservative_readiness_report(grants=grants),
            "missing_data": build_missing_data_report(grants=grants),
            "provenance": build_provenance_confidence_report(grants=grants),
            "offline_only": True,
            "live_ingestion": False,
            "source_activation": False,
        }
    )
