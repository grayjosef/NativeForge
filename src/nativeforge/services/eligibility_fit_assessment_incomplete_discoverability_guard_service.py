"""Sprint 203: incomplete applicant data must stay discoverable with human review."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_incomplete_discoverability_guard_v1"

READINESS_COMPLETE = "complete"
READINESS_INCOMPLETE = "incomplete"
READINESS_UNKNOWN = "unknown"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def profile_data_complete(profile: dict[str, Any]) -> bool:
    required = (
        profile.get("organization_name"),
        profile.get("applicant_type"),
        profile.get("service_geography"),
    )
    return all(bool(v) for v in required)


def apply_incomplete_discoverability_guard(
    *,
    profile: dict[str, Any],
    proposed_discoverable: bool,
    proposed_human_review_required: bool,
    proposed_readiness: str,
) -> dict[str, Any]:
    """Fail-closed: incomplete profiles stay discoverable and force human review."""
    complete = profile_data_complete(profile)
    if complete:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "profile_data_complete": True,
                "final_discoverable": proposed_discoverable,
                "final_human_review_required": proposed_human_review_required,
                "final_readiness": proposed_readiness,
                "over_filter_blocked": False,
            }
        )

    over_filtered = not proposed_discoverable
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_data_complete": False,
            "final_discoverable": True,
            "final_human_review_required": True,
            "final_readiness": READINESS_INCOMPLETE
            if proposed_readiness != READINESS_COMPLETE
            else READINESS_INCOMPLETE,
            "over_filter_blocked": over_filtered,
            "guard_reason": (
                "incomplete applicant data must remain discoverable with human review"
            ),
        }
    )


def build_incomplete_discoverability_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_profile_fields": [
                "organization_name",
                "applicant_type",
                "service_geography",
            ],
            "preview_only": True,
        }
    )
