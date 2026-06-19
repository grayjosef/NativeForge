"""Sprint 205: fit dimension evaluators for eligibility fit assessment."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (
    DIMENSION_CAPACITY_FIT,
    DIMENSION_ELIGIBILITY_FIT,
    DIMENSION_GEOGRAPHY_FIT,
    DIMENSION_PROGRAM_FIT,
    DIMENSION_RELEVANCE_FIT,
    FIT_STATUS_BLOCKED,
    FIT_STATUS_MODERATE,
    FIT_STATUS_STRONG,
    FIT_STATUS_UNKNOWN,
    FIT_STATUS_WEAK,
)

SCHEMA_VERSION = "nf_eligibility_fit_assessment_dimension_evaluator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dimension_result(dimension: str, status: str, rationale: str) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "fit_status": status,
        "rationale": rationale,
    }


def evaluate_eligibility_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not profile.get("applicant_type"):
        return _dimension_result(
            DIMENSION_ELIGIBILITY_FIT,
            FIT_STATUS_UNKNOWN,
            "applicant type missing from profile",
        )
    if opportunity.get("tribal_eligible") and profile.get("applicant_type") == "tribal_government":
        return _dimension_result(
            DIMENSION_ELIGIBILITY_FIT,
            FIT_STATUS_STRONG,
            "tribal-eligible opportunity matches tribal government applicant",
        )
    if opportunity.get("tribal_eligible"):
        return _dimension_result(
            DIMENSION_ELIGIBILITY_FIT,
            FIT_STATUS_MODERATE,
            "tribal-eligible opportunity with non-tribal-government applicant type",
        )
    return _dimension_result(
        DIMENSION_ELIGIBILITY_FIT,
        FIT_STATUS_WEAK,
        "open eligibility; cautious fit only",
    )


def evaluate_relevance_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    native_relevance_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if native_relevance_preview is None:
        return _dimension_result(
            DIMENSION_RELEVANCE_FIT,
            FIT_STATUS_UNKNOWN,
            "native relevance classification preview not supplied",
        )
    label = native_relevance_preview.get("classification", {}).get("classification_label", "unknown")
    if label in {"native_specific", "tribal_government_specific", "native_entity_eligible_broad"}:
        return _dimension_result(
            DIMENSION_RELEVANCE_FIT,
            FIT_STATUS_STRONG,
            f"native relevance label {label} supports application readiness review",
        )
    if label in {"broadly_eligible_potentially_relevant", "indigenous_community_relevant"}:
        return _dimension_result(
            DIMENSION_RELEVANCE_FIT,
            FIT_STATUS_MODERATE,
            f"native relevance label {label} suggests cautious fit",
        )
    if label == "irrelevant":
        return _dimension_result(
            DIMENSION_RELEVANCE_FIT,
            FIT_STATUS_BLOCKED,
            "native relevance label irrelevant for applicant pursuit",
        )
    return _dimension_result(
        DIMENSION_RELEVANCE_FIT,
        FIT_STATUS_WEAK,
        f"native relevance label {label} requires operator review",
    )


def evaluate_geography_fit(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    req = opportunity.get("required_geography")
    svc = profile.get("service_geography")
    if not req or not svc:
        return _dimension_result(
            DIMENSION_GEOGRAPHY_FIT,
            FIT_STATUS_UNKNOWN,
            "geography fields incomplete",
        )
    if str(req).lower() == "national":
        return _dimension_result(
            DIMENSION_GEOGRAPHY_FIT,
            FIT_STATUS_STRONG,
            "national opportunity accepts applicant service geography",
        )
    if str(req).lower() == str(svc).lower():
        return _dimension_result(
            DIMENSION_GEOGRAPHY_FIT,
            FIT_STATUS_STRONG,
            "service geography matches required geography",
        )
    return _dimension_result(
        DIMENSION_GEOGRAPHY_FIT,
        FIT_STATUS_BLOCKED,
        "service geography does not match required geography",
    )


def evaluate_program_fit(opportunity: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    program = opportunity.get("program_area")
    areas = profile.get("program_areas") or []
    if not program:
        return _dimension_result(
            DIMENSION_PROGRAM_FIT,
            FIT_STATUS_UNKNOWN,
            "opportunity program area missing",
        )
    if program in areas:
        return _dimension_result(
            DIMENSION_PROGRAM_FIT,
            FIT_STATUS_STRONG,
            "program area aligned with organization profile",
        )
    if areas:
        return _dimension_result(
            DIMENSION_PROGRAM_FIT,
            FIT_STATUS_MODERATE,
            "partial program alignment across profile areas",
        )
    return _dimension_result(
        DIMENSION_PROGRAM_FIT,
        FIT_STATUS_UNKNOWN,
        "organization program areas missing",
    )


def evaluate_capacity_fit(opportunity: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    capacity = profile.get("grant_management_capacity")
    if not capacity:
        return _dimension_result(
            DIMENSION_CAPACITY_FIT,
            FIT_STATUS_UNKNOWN,
            "grant management capacity not recorded",
        )
    if capacity == "strong":
        return _dimension_result(
            DIMENSION_CAPACITY_FIT,
            FIT_STATUS_STRONG,
            "strong grant management capacity in profile",
        )
    if capacity == "moderate":
        return _dimension_result(
            DIMENSION_CAPACITY_FIT,
            FIT_STATUS_MODERATE,
            "moderate grant management capacity in profile",
        )
    return _dimension_result(
        DIMENSION_CAPACITY_FIT,
        FIT_STATUS_WEAK,
        "limited grant management capacity in profile",
    )


def evaluate_all_fit_dimensions(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    native_relevance_preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dimensions = [
        evaluate_eligibility_fit(opportunity, profile),
        evaluate_relevance_fit(opportunity, profile, native_relevance_preview=native_relevance_preview),
        evaluate_geography_fit(opportunity, profile),
        evaluate_program_fit(opportunity, profile),
        evaluate_capacity_fit(opportunity, profile),
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dimension_results": dimensions,
            "preview_only": True,
        }
    )
