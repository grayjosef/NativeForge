"""Sprint 201: operator next-check guidance for eligibility fit assessment."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_eligibility_fit_assessment_operator_guidance_v1"

_GUIDANCE_BY_TOPIC: dict[str, str] = {
    "eligibility_evidence": (
        "Confirm applicant type and tribal eligibility against source NOFO and organization profile."
    ),
    "geography": (
        "Verify service area and geography fields in applicant profile match opportunity geography."
    ),
    "capacity": (
        "Review staffing, grant-management capacity, and prior award history in organization profile."
    ),
    "documentation": (
        "Collect missing documentation inventory items before application readiness sign-off."
    ),
    "deadline": (
        "Validate application deadline and internal submission timeline with operator calendar."
    ),
    "native_relevance": (
        "Cross-check Native relevance classification preview with applicant mission fit."
    ),
    "missing_profile": (
        "Complete applicant/organization profile fixture before issuing any eligibility claim."
    ),
    "human_gate": (
        "Route to operator human gate; do not auto-advance without explicit profile evidence."
    ),
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def get_operator_next_check(topic: str) -> str:
    if topic not in _GUIDANCE_BY_TOPIC:
        raise ValueError(f"unknown operator guidance topic: {topic!r}")
    return _GUIDANCE_BY_TOPIC[topic]


def build_operator_guidance_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "guidance_topics": sorted(_GUIDANCE_BY_TOPIC.keys()),
            "guidance_by_topic": dict(_GUIDANCE_BY_TOPIC),
            "preview_only": True,
        }
    )
