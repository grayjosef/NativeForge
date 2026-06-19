"""Sprint 216: applicant-specific recommendations stay needs_operator_review until confirmed."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
    is_applicant_specific_match_label,
)

SCHEMA_VERSION = "nf_matching_readiness_applicant_recommendation_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_applicant_recommendation_guard(
    *,
    proposed_match_label: str,
    human_confirmation_present: bool,
) -> dict[str, Any]:
    """Fail-closed: applicant-specific labels require human confirmation."""
    if not is_applicant_specific_match_label(proposed_match_label):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_match_label": proposed_match_label,
                "final_match_label": proposed_match_label,
                "recommendation_blocked": False,
                "human_confirmation_present": human_confirmation_present,
            }
        )

    if human_confirmation_present:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_match_label": proposed_match_label,
                "final_match_label": proposed_match_label,
                "recommendation_blocked": False,
                "human_confirmation_present": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_match_label": proposed_match_label,
            "final_match_label": LABEL_NEEDS_OPERATOR_REVIEW,
            "recommendation_blocked": True,
            "human_confirmation_present": False,
            "guard_reason": (
                "applicant-specific match recommendations require human confirmation"
            ),
        }
    )


def build_applicant_recommendation_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fallback_label": LABEL_NEEDS_OPERATOR_REVIEW,
            "preview_only": True,
        }
    )
