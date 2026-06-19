"""Sprint 242: reconcile operator_next_check with matching_readiness guidance."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_next_action_guidance_service import (
    get_next_action_guidance,
)

SCHEMA_VERSION = "nf_canonical_operator_guidance_reconciliation_v1"

# Eligibility-fit topic -> canonical matching_readiness next-action topic.
FIT_TOPIC_TO_CANONICAL: dict[str, str] = {
    "human_gate": "needs_operator_review",
    "missing_profile": "needs_more_profile_data",
    "documentation": "missing_documents",
    "deadline": "deadline_risk",
    "eligibility_evidence": "eligibility_uncertain",
    "capacity": "capacity_gap",
    "geography": "needs_operator_review",
    "native_relevance": "needs_operator_review",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def map_fit_topic_to_canonical(fit_topic: str) -> str:
    if fit_topic not in FIT_TOPIC_TO_CANONICAL:
        raise ValueError(f"unknown eligibility-fit guidance topic: {fit_topic!r}")
    return FIT_TOPIC_TO_CANONICAL[fit_topic]


def reconcile_operator_next_checks(
    operator_next_check: dict[str, Any],
) -> list[dict[str, str]]:
    """Translate eligibility_fit operator_next_checks to canonical next_actions."""
    checks = operator_next_check.get("operator_next_checks") or []
    canonical_topics: set[str] = set()
    for item in checks:
        fit_topic = str(item.get("topic") or "")
        if fit_topic in FIT_TOPIC_TO_CANONICAL:
            canonical_topics.add(map_fit_topic_to_canonical(fit_topic))
    return [
        {"topic": t, "guidance": get_next_action_guidance(t)}
        for t in sorted(canonical_topics)
    ]


def build_reconciliation_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_layer": "matching_readiness_next_action_guidance_service",
            "legacy_layer": "eligibility_fit_assessment_operator_next_check_service",
            "topic_map": dict(FIT_TOPIC_TO_CANONICAL),
            "reconciliation_status": "complete",
            "preview_only": True,
        }
    )
