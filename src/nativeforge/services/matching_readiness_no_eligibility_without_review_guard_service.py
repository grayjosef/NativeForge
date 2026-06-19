"""Sprint 218: no final eligibility without operator review."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_matching_readiness_no_eligibility_without_review_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_no_eligibility_without_review_guard(
    *,
    proposed_final_eligibility: bool,
    operator_review_completed: bool,
    human_confirmation_present: bool,
) -> dict[str, Any]:
    """Fail-closed: suppress final eligibility without completed operator review."""
    if not proposed_final_eligibility:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_final_eligibility": False,
                "final_eligibility": False,
                "eligibility_blocked": False,
            }
        )

    if operator_review_completed and human_confirmation_present:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "proposed_final_eligibility": True,
                "final_eligibility": True,
                "eligibility_blocked": False,
                "operator_review_completed": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proposed_final_eligibility": True,
            "final_eligibility": False,
            "eligibility_blocked": True,
            "operator_review_completed": operator_review_completed,
            "guard_reason": "no final eligibility without operator review and confirmation",
        }
    )


def build_no_eligibility_without_review_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requires_operator_review": True,
            "preview_only": True,
        }
    )
