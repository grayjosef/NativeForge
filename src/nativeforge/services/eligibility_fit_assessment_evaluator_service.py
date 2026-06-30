"""Sprint 206: eligibility fit assessment evaluator (Stage 7 orchestrator)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_CAPACITY_GAP,
    BLOCKER_DEADLINE_PASSED,
    BLOCKER_ELIGIBILITY_EVIDENCE_GAP,
    BLOCKER_GEOGRAPHY_MISMATCH,
    BLOCKER_MISSING_DEADLINE,
    BLOCKER_MISSING_DOCUMENTATION,
    BLOCKER_MISSING_PROFILE,
    BLOCKER_RECOGNITION_TIER_MISMATCH,
    build_blockers_assessment,
)
from nativeforge.services.eligibility_fit_assessment_confidence_service import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_UNKNOWN,
    merge_fit_confidence_levels,
    resolve_human_review_status,
)
from nativeforge.services.eligibility_fit_assessment_deadline_risk_service import (
    RISK_HIGH,
    assess_deadline_risk,
)
from nativeforge.services.eligibility_fit_assessment_dimension_evaluator_service import (
    evaluate_all_fit_dimensions,
)
from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    FIT_STATUS_BLOCKED,
    FIT_STATUS_STRONG,
)
from nativeforge.services.eligibility_fit_assessment_documentation_readiness_service import (
    READINESS_COMPLETE,
    READINESS_INCOMPLETE,
    assess_documentation_readiness,
)
from nativeforge.services.eligibility_fit_assessment_incomplete_discoverability_guard_service import (
    apply_incomplete_discoverability_guard,
)
from nativeforge.services.eligibility_fit_assessment_missing_data_service import (
    FLAG_MISSING_APPLICANT_TYPE,
    FLAG_MISSING_CAPACITY,
    FLAG_MISSING_DEADLINE,
    FLAG_MISSING_DOCUMENTATION_INVENTORY,
    FLAG_MISSING_GEOGRAPHY,
    FLAG_MISSING_NATIVE_RELEVANCE_PREVIEW,
    build_missing_data_assessment,
)
from nativeforge.services.eligibility_fit_assessment_no_claim_without_evidence_guard_service import (
    apply_no_claim_without_evidence_guard,
    has_explicit_profile_evidence,
)
from nativeforge.services.recognition_tier_eligibility_gate_service import (
    apply_recognition_tier_eligibility_gate,
)

SCHEMA_VERSION = "nf_eligibility_fit_assessment_evaluator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _propose_final_eligibility_claim(
    dimension_results: list[dict[str, Any]],
    documentation_readiness: str,
) -> bool:
    blocked = any(d["fit_status"] == FIT_STATUS_BLOCKED for d in dimension_results)
    if blocked:
        return False
    strong_count = sum(1 for d in dimension_results if d["fit_status"] == FIT_STATUS_STRONG)
    return strong_count >= 3 and documentation_readiness == READINESS_COMPLETE


def assess_eligibility_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    native_relevance_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic Stage 7 assessment with both hard invariants applied."""
    dimensions = evaluate_all_fit_dimensions(
        opportunity,
        profile,
        native_relevance_preview=native_relevance_preview,
    )
    dimension_results = list(dimensions["dimension_results"])

    recognition_tier_gate = None
    if profile.get("recognition_type") or opportunity.get("recognition_requirement"):
        recognition_tier_gate = apply_recognition_tier_eligibility_gate(
            opportunity=opportunity,
            profile=profile,
        )
        dimension_results.append(recognition_tier_gate["dimension_result"])

    deadline = assess_deadline_risk(opportunity)
    documentation = assess_documentation_readiness(profile)

    missing_flags: list[str] = []
    if not profile.get("applicant_type"):
        missing_flags.append(FLAG_MISSING_APPLICANT_TYPE)
    if not profile.get("service_geography"):
        missing_flags.append(FLAG_MISSING_GEOGRAPHY)
    if not profile.get("grant_management_capacity"):
        missing_flags.append(FLAG_MISSING_CAPACITY)
    if native_relevance_preview is None:
        missing_flags.append(FLAG_MISSING_NATIVE_RELEVANCE_PREVIEW)
    if not opportunity.get("application_deadline"):
        missing_flags.append(FLAG_MISSING_DEADLINE)
    if documentation["documentation_readiness"] != READINESS_COMPLETE:
        missing_flags.append(FLAG_MISSING_DOCUMENTATION_INVENTORY)

    blockers: list[str] = []
    if not profile:
        blockers.append(BLOCKER_MISSING_PROFILE)
    if not opportunity.get("application_deadline"):
        blockers.append(BLOCKER_MISSING_DEADLINE)
    if documentation["documentation_readiness"] in {READINESS_INCOMPLETE, "unknown"}:
        blockers.append(BLOCKER_MISSING_DOCUMENTATION)
    if not has_explicit_profile_evidence(list(profile.get("profile_evidence_codes") or [])):
        blockers.append(BLOCKER_ELIGIBILITY_EVIDENCE_GAP)
    if recognition_tier_gate:
        gate_blockers = list(recognition_tier_gate.get("blocker_codes") or [])
        if not gate_blockers and recognition_tier_gate.get("blocker_code"):
            gate_blockers = [recognition_tier_gate["blocker_code"]]
        for code in gate_blockers:
            if code not in blockers:
                blockers.append(code)
    if any(d["dimension"] == "geography_fit" and d["fit_status"] == FIT_STATUS_BLOCKED for d in dimension_results):
        blockers.append(BLOCKER_GEOGRAPHY_MISMATCH)
    if any(d["dimension"] == "capacity_fit" and d["fit_status"] == FIT_STATUS_BLOCKED for d in dimension_results):
        blockers.append(BLOCKER_CAPACITY_GAP)
    if deadline["deadline_risk"] == RISK_HIGH and (deadline.get("days_until_deadline") or 0) < 0:
        blockers.append(BLOCKER_DEADLINE_PASSED)

    missing_data = build_missing_data_assessment(flags=missing_flags)
    blockers_assessment = build_blockers_assessment(blocker_codes=blockers)

    proposed_claim = _propose_final_eligibility_claim(
        dimension_results,
        documentation["documentation_readiness"],
    )
    claim_guard = apply_no_claim_without_evidence_guard(
        proposed_final_eligibility_claim=proposed_claim,
        profile_evidence_codes=list(profile.get("profile_evidence_codes") or []),
    )

    confidence_levels = []
    if claim_guard["final_eligibility_claim"]:
        confidence_levels.append(CONFIDENCE_CONFIRMED)
    elif claim_guard["claim_blocked"]:
        confidence_levels.append(CONFIDENCE_LOW)
    elif missing_data["data_incomplete"]:
        confidence_levels.append(CONFIDENCE_UNKNOWN)
    else:
        confidence_levels.append(CONFIDENCE_MEDIUM)
    confidence = merge_fit_confidence_levels(confidence_levels)

    human_review_required = (
        claim_guard["human_review_required"]
        or missing_data["data_incomplete"]
        or blockers_assessment["application_blocked"]
        or documentation["human_review_required"]
        or deadline["human_review_recommended"]
    )
    human_review_status = resolve_human_review_status(
        human_review_required=human_review_required,
        blocked_pending_evidence=claim_guard["claim_blocked"],
    )

    readiness = (
        READINESS_COMPLETE
        if claim_guard["final_eligibility_claim"] and not blockers_assessment["application_blocked"]
        else READINESS_INCOMPLETE
    )

    discover_guard = apply_incomplete_discoverability_guard(
        profile=profile,
        proposed_discoverable=claim_guard["final_eligibility_claim"] or not blockers_assessment["application_blocked"],
        proposed_human_review_required=human_review_required,
        proposed_readiness=readiness,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": opportunity.get("fixture_key"),
            "profile_fixture_key": profile.get("fixture_key"),
            "dimension_results": dimension_results,
            "deadline_risk": deadline,
            "documentation_readiness": documentation,
            "missing_data": missing_data,
            "blockers": blockers_assessment,
            "confidence": confidence,
            "human_review_status": human_review_status,
            "human_review_required": discover_guard["final_human_review_required"],
            "application_readiness": discover_guard["final_readiness"],
            "final_eligibility_claim": claim_guard["final_eligibility_claim"],
            "discoverable": discover_guard["final_discoverable"],
            "claim_guard": claim_guard,
            "discoverability_guard": discover_guard,
            "recognition_tier_gate": recognition_tier_gate,
            "preview_only": True,
        }
    )
