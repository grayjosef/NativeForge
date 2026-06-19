"""Sprint 226: Stages 8-10 matching + readiness closeout packet."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    MATCH_LABELS,
)
from nativeforge.services.matching_readiness_readiness_label_vocabulary_service import (
    READINESS_LABELS,
)
from nativeforge.services.matching_readiness_stages8_10_gate_verification_service import (
    verify_stages8_10_gates_on_demo_corpus,
)

ARTIFACT_TYPE = "nf_matching_readiness_stages8_10_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_matching_readiness_stages8_10_closeout_packet() -> dict[str, Any]:
    verification = verify_stages8_10_gates_on_demo_corpus()
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 226,
            "preview_only": True,
            "no_execution": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "actual_external_calls": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "stages": [8, 9, 10],
            "stage_inputs": [
                "Stage 5 funding opportunity intake",
                "Stage 6 native relevance classification",
                "Stage 7 org/applicant profile",
            ],
            "canonical_fit_layer": "eligibility_fit_assessment_*",
            "matching_readiness_layer": "matching_readiness_* (labels + readiness only)",
            "match_labels": list(MATCH_LABELS),
            "readiness_labels": list(READINESS_LABELS),
            "hard_invariants": [
                "applicant-specific recommendations stay needs_operator_review until human confirmation",
                "never mutate a profile to make a match fit",
                "no final eligibility without operator review",
                "fail-closed on missing profile/eligibility/deadline data",
            ],
            "reconciliation_cleanup_candidates": verification["reconciliation_cleanup_candidates"],
            "gate_verification_passed": verification["verification_passed"],
            "recommended_next_safe_action": (
                "Review-only: walk Stages 8-10 gate verification rollup; consolidate "
                "overlapping operator guidance from eligibility_fit_assessment_* before "
                "any live matching deployment."
            ),
        }
    )


def render_matching_readiness_stages8_10_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    pkt = packet or build_matching_readiness_stages8_10_closeout_packet()
    lines = [
        "# Matching + Readiness Stages 8-10 Closeout",
        "",
        f"- artifact_type: `{pkt['artifact_type']}`",
        f"- gate_verification_passed: {pkt['gate_verification_passed']}",
        "",
        "## Hard invariants",
    ]
    for inv in pkt["hard_invariants"]:
        lines.append(f"- {inv}")
    lines.extend(["", "## Reconciliation / cleanup candidates"])
    for item in pkt["reconciliation_cleanup_candidates"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended next safe action", pkt["recommended_next_safe_action"]])
    return "\n".join(lines)
