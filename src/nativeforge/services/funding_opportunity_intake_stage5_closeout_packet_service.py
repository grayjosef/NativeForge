"""Sprint 181: Stage 5 funding opportunity intake closeout packet (preview-only)."""

from __future__ import annotations

import json
from typing import Any

ARTIFACT_TYPE = "nf_funding_opportunity_intake_stage5_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_SPRINT180 = "nf_funding_opportunity_stage5_verification_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_funding_opportunity_intake_stage5_closeout_packet() -> dict[str, Any]:
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 181,
            "preview_only": True,
            "no_execution": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "prerequisite_stage5_verification_rollup_artifact_type": _PREREQUISITE_SPRINT180,
            "actual_external_calls": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "stage5_capabilities": [
                "provenance-first opportunity record",
                "field-level provenance",
                "per-field confidence",
                "missing-data flags",
                "intake status model",
                "fail-closed gates",
                "operator-approved duplicate detection",
            ],
            "fail_closed_on": [
                "missing deadline",
                "missing source",
                "missing provenance",
                "stale record",
                "unresolved duplicate",
            ],
            "recommended_next_safe_action": (
                "Review-only: walk Stage 5 verification rollup and demo fixture "
                "corpus; pursue live ingestion only after separate human authorization."
            ),
        }
    )


def render_funding_opportunity_intake_stage5_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    pkt = (
        packet
        if isinstance(packet, dict)
        else build_funding_opportunity_intake_stage5_closeout_packet()
    )
    lines = [
        "# NativeForge Funding Opportunity Intake Stage 5 Closeout Packet v1",
        "",
        "## Purpose",
        "",
        "Closeout for Block NF-1 Sprints 167–181: funding opportunity intake hardening.",
        "",
        "## Stage 5 Capabilities",
        "",
    ]
    for cap in pkt.get("stage5_capabilities") or []:
        lines.append(f"- {cap}")
    lines.extend(
        [
            "",
            "## Fail-Closed Gates",
            "",
        ]
    )
    for gate in pkt.get("fail_closed_on") or []:
        lines.append(f"- {gate}")
    lines.extend(
        [
            "",
            "## Recommended Next Safe Action",
            "",
            str(pkt.get("recommended_next_safe_action") or ""),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
