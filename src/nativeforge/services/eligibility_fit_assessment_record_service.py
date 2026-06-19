"""Sprint 208: eligibility fit assessment record assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.canonical_operator_guidance_reconciliation_service import (
    reconcile_operator_next_checks,
)
from nativeforge.services.eligibility_fit_assessment_evaluator_service import (
    assess_eligibility_fit,
)
from nativeforge.services.eligibility_fit_assessment_operator_next_check_service import (  # noqa: E501
    build_operator_next_check_guidance,
)
from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)

SCHEMA_VERSION = "nf_eligibility_fit_assessment_record_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_eligibility_fit_assessment_record(
    opportunity: dict[str, Any],
    profile: dict[str, Any],
    *,
    fixture_key: str | None = None,
    include_native_relevance_preview: bool = True,
) -> dict[str, Any]:
    fk = fixture_key or str(opportunity.get("fixture_key") or "unspecified_fixture")
    native_preview = (
        build_native_relevance_classification_record(opportunity, fixture_key=fk)
        if include_native_relevance_preview
        else None
    )
    assessment = assess_eligibility_fit(
        opportunity,
        profile,
        native_relevance_preview=native_preview,
    )
    operator_guidance = build_operator_next_check_guidance(
        opportunity,
        profile,
        assessment=assessment,
        native_relevance_preview=native_preview,
    )
    canonical_next_actions = reconcile_operator_next_checks(operator_guidance)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_key": fk,
            "profile_fixture_key": profile.get("fixture_key"),
            "native_relevance_preview": native_preview,
            "assessment": assessment,
            "operator_next_check": operator_guidance,
            "canonical_next_actions": canonical_next_actions,
            "discoverable": assessment["discoverable"],
            "human_review_required": assessment["human_review_required"],
            "final_eligibility_claim": assessment["final_eligibility_claim"],
            "preview_only": True,
            "no_live_ingestion": True,
            "synthetic_fixture": True,
        }
    )
