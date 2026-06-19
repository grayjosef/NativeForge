"""Sprint 196: Stage 6 native relevance classification closeout packet."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_relevance_classification_stage6_gate_verification_service import (
    verify_stage6_gates_on_demo_corpus,
)

ARTIFACT_TYPE = "nf_native_relevance_classification_stage6_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_GATE_VERIFICATION = "nf_native_relevance_classification_stage6_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_native_relevance_classification_stage6_closeout_packet() -> dict[str, Any]:
    verification = verify_stage6_gates_on_demo_corpus()
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 196,
            "preview_only": True,
            "no_execution": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "prerequisite_gate_verification_artifact_type": _PREREQUISITE_GATE_VERIFICATION,
            "actual_external_calls": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "stage6_capabilities": [
                "eight evidence-based classification labels",
                "per-label explanation",
                "classification confidence",
                "human-review triggers",
                "overclaim guard",
                "over-filter guard",
            ],
            "classification_labels": [
                "native_specific",
                "tribal_government_specific",
                "indigenous_community_relevant",
                "native_entity_eligible_broad",
                "broadly_eligible_potentially_relevant",
                "weak_native_relevance",
                "uncertain_relevance",
                "irrelevant",
            ],
            "hard_invariants": [
                "overclaim guard: never native_specific without explicit source evidence",
                "over-filter guard: broad opportunities stay discoverable",
            ],
            "gate_verification_passed": verification["verification_passed"],
            "recommended_next_safe_action": (
                "Review-only: walk Stage 6 gate verification rollup and demo fixture "
                "corpus; pursue live classification only after separate human authorization."
            ),
        }
    )


def render_native_relevance_classification_stage6_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    pkt = packet or build_native_relevance_classification_stage6_closeout_packet()
    lines = [
        "# Native Relevance Classification Stage 6 Closeout",
        "",
        f"- artifact_type: `{pkt['artifact_type']}`",
        f"- sprint_number: {pkt['sprint_number']}",
        f"- gate_verification_passed: {pkt['gate_verification_passed']}",
        "",
        "## Hard invariants",
    ]
    for inv in pkt["hard_invariants"]:
        lines.append(f"- {inv}")
    lines.extend(
        [
            "",
            "## Classification labels",
        ]
    )
    for label in pkt["classification_labels"]:
        lines.append(f"- {label}")
    lines.extend(
        [
            "",
            "## Recommended next safe action",
            pkt["recommended_next_safe_action"],
        ]
    )
    return "\n".join(lines)
