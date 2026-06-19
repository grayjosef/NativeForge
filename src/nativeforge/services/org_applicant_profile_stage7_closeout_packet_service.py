"""Sprint 211: Stage 7 org/applicant profile foundation closeout packet."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_applicant_profile_schema_service import (
    PROFILE_SCHEMA_FIELDS,
)
from nativeforge.services.org_applicant_profile_stage7_gate_verification_service import (
    verify_stage7_org_profile_gates_on_demo_corpus,
)

ARTIFACT_TYPE = "nf_org_applicant_profile_stage7_closeout_packet_v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

_PREREQUISITE_GATE_VERIFICATION = "nf_org_applicant_profile_stage7_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_org_applicant_profile_stage7_closeout_packet() -> dict[str, Any]:
    verification = verify_stage7_org_profile_gates_on_demo_corpus()
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "generated_at": DETERMINISTIC_GENERATED_AT,
            "sprint_number": 211,
            "preview_only": True,
            "no_execution": True,
            "no_live_ingestion": True,
            "synthetic_fixtures_only": True,
            "no_runtime_db_mutation": True,
            "prerequisite_gate_verification_artifact_type": _PREREQUISITE_GATE_VERIFICATION,
            "actual_external_calls": 0,
            "actual_scrapes": 0,
            "actual_source_activations": 0,
            "stage7_capabilities": [
                "profile schema",
                "field-level provenance",
                "sensitive-field flags",
                "review status model",
                "unknown value policy",
                "no-invention guard",
                "verified_by_user guard",
                "no-mutation-without-approval guard",
                "hardened profile record",
                "operator review queue",
            ],
            "profile_schema_fields": list(PROFILE_SCHEMA_FIELDS),
            "hard_invariants": [
                "never invent tribal affiliation, federally-recognized status, "
                "Native-serving status, certifications, geography, past awards, "
                "UEI, authorized representative, documents, or eligibility",
                "no profile reaches verified_by_user without explicit human/customer confirmation",
                "no profile mutation without operator approval",
            ],
            "gate_verification_passed": verification["verification_passed"],
            "recommended_next_safe_action": (
                "Review-only: walk Stage 7 org/applicant profile gate verification "
                "rollup and demo fixture corpus; pursue live profile ingestion only "
                "after separate human authorization."
            ),
        }
    )


def render_org_applicant_profile_stage7_closeout_packet_markdown(
    packet: dict[str, Any] | None = None,
) -> str:
    pkt = packet or build_org_applicant_profile_stage7_closeout_packet()
    lines = [
        "# Org/Applicant Profile Stage 7 Closeout",
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
            "## Profile schema fields",
        ]
    )
    for field in pkt["profile_schema_fields"]:
        lines.append(f"- {field}")
    lines.extend(
        [
            "",
            "## Recommended next safe action",
            pkt["recommended_next_safe_action"],
        ]
    )
    return "\n".join(lines)
