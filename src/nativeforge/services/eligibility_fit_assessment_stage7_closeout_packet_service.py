"""Sprint 211: Stage 7 eligibility fit assessment closeout packet."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_fit_assessment_stage7_gate_verification_service import (
    verify_stage7_gates_on_demo_corpus,
)

ARTIFACT_TYPE = "nf_eligibility_fit_assessment_stage7_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_GATE_VERIFICATION = "nf_eligibility_fit_assessment_stage7_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_eligibility_fit_assessment_stage7_closeout_packet() -> dict[str, Any]:
    verification = verify_stage7_gates_on_demo_corpus()
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 211,
            "preview_only": True,
            "no_execution": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "prerequisite_gate_verification_artifact_type": _PREREQUISITE_GATE_VERIFICATION,
            "actual_external_calls": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "stage7_capabilities": [
                "eligibility fit",
                "relevance fit",
                "geography fit",
                "program fit",
                "capacity fit",
                "deadline risk",
                "documentation readiness",
                "blockers",
                "missing data",
                "confidence",
                "human-review status",
                "operator next-check guidance",
            ],
            "hard_invariants": [
                "no final eligibility claim without explicit applicant/profile evidence",
                "incomplete applicant data stays discoverable with human review",
            ],
            "gate_verification_passed": verification["verification_passed"],
            "recommended_next_safe_action": (
                "Review-only: walk Stage 7 gate verification rollup and demo fixture "
                "corpus; pursue live fit assessment only after separate human authorization."
            ),
        }
    )


def render_eligibility_fit_assessment_stage7_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    pkt = packet or build_eligibility_fit_assessment_stage7_closeout_packet()
    lines = [
        "# Eligibility Fit Assessment Stage 7 Closeout",
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
            "## Stage 7 capabilities",
        ]
    )
    for cap in pkt["stage7_capabilities"]:
        lines.append(f"- {cap}")
    lines.extend(
        [
            "",
            "## Recommended next safe action",
            pkt["recommended_next_safe_action"],
        ]
    )
    return "\n".join(lines)
