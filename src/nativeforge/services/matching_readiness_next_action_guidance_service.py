"""Sprint 215: next-action guidance for matching + readiness."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_matching_readiness_next_action_guidance_v1"

_GUIDANCE: dict[str, str] = {
    "needs_operator_review": (
        "Route to operator human gate; applicant-specific match requires confirmation."
    ),
    "needs_more_profile_data": (
        "Complete org/applicant profile fixture before issuing match recommendation."
    ),
    "missing_documents": (
        "Collect required documents on file before application readiness sign-off."
    ),
    "deadline_risk": (
        "Validate application deadline and internal submission timeline with operator."
    ),
    "eligibility_uncertain": (
        "Confirm eligibility markers and applicant type against funding opportunity source."
    ),
    "capacity_gap": (
        "Review grant/staff/match capacity in organization profile before pursuit."
    ),
    "blocked": (
        "Resolve blockers before advancing; do not auto-promote match or readiness."
    ),
    "strong_fit_review": (
        "Strong fit preview only — obtain operator confirmation before application action."
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def get_next_action_guidance(topic: str) -> str:
    if topic not in _GUIDANCE:
        raise ValueError(f"unknown next-action topic: {topic!r}")
    return _GUIDANCE[topic]


def build_next_action_guidance_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "guidance_topics": sorted(_GUIDANCE.keys()),
            "guidance_by_topic": dict(_GUIDANCE),
            "preview_only": True,
        }
    )
