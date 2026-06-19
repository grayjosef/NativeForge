"""Sprint 219: fail-closed on missing profile, eligibility, or deadline data."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_BLOCKED,
    LABEL_NEEDS_MORE_PROFILE_DATA,
)

SCHEMA_VERSION = "nf_matching_readiness_missing_data_fail_closed_guard_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_missing_data_fail_closed_guard(
    *,
    profile_present: bool,
    eligibility_data_present: bool,
    deadline_present: bool,
    proposed_match_label: str,
) -> dict[str, Any]:
    """Fail-closed: missing critical data forces blocked or needs_more_profile_data."""
    missing: list[str] = []
    if not profile_present:
        missing.append("profile")
    if not eligibility_data_present:
        missing.append("eligibility")
    if not deadline_present:
        missing.append("deadline")

    if not missing:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "missing_data_fields": [],
                "final_match_label": proposed_match_label,
                "fail_closed_triggered": False,
            }
        )

    if not profile_present:
        final = LABEL_NEEDS_MORE_PROFILE_DATA
    else:
        final = LABEL_BLOCKED

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "missing_data_fields": missing,
            "final_match_label": final,
            "fail_closed_triggered": True,
            "guard_reason": f"missing critical data: {', '.join(missing)}",
        }
    )


def build_missing_data_fail_closed_guard_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_data_domains": ["profile", "eligibility", "deadline"],
            "preview_only": True,
        }
    )
