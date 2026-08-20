"""Integrate org evidence memory with eligibility / binder / readiness (Block 08)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_handoff_service import (
    build_eligibility_handoff_for_pair,
)
from nativeforge.services.organization_evidence_memory_builder_service import (
    build_organization_evidence_from_fixture,
)
from nativeforge.services.organization_evidence_memory_contract_service import (
    organization_evidence_invariant_failures,
)

SCHEMA_VERSION = "nf_organization_evidence_eligibility_integration_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def integrate_org_memory_with_eligibility(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
) -> dict[str, Any]:
    oem = build_organization_evidence_from_fixture(profile)
    handoff = build_eligibility_handoff_for_pair(profile, opportunity)
    elig = handoff.get("eligibility_evidence") or {}

    # Guardrails: never conflate recognition; never claim final eligibility from memory
    federal_state_ok = True
    if (
        oem.get("recognition_tier") == "state_only"
        and elig.get("recognition_tier") == "federal"
    ):
        # handoff may still classify pathway; memory must stay state_only
        federal_state_ok = oem.get("recognition_status") == "state_only"

    notes = [
        "Organization memory provides recognition evidence context for eligibility handoff",
        "Final eligibility is never claimed from organization memory alone",
        "Federally recognized remains distinct from state-recognized",
        "Native-serving nonprofit / fiscal sponsor pathways remain explicit when present",
    ]
    if oem.get("recognition_tier") == "state_only":
        notes.append(
            "State recognition must not be treated as federal recognition for federal-only pathways"
        )
    if oem.get("organization_type") not in {
        "tribal_government",
        "federally_recognized_tribe",
    }:
        notes.append(
            f"Organization type={oem.get('organization_type')} kept distinct from tribal government pathways"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_evidence_profile_id": oem.get(
                "organization_evidence_profile_id"
            ),
            "organization_profile_id": oem.get("organization_profile_id"),
            "opportunity_id": str(
                opportunity.get("opportunity_id") or opportunity.get("grant_id")
            ),
            "organization_evidence": oem,
            "eligibility_handoff_summary": {
                "applicant_category": elig.get("applicant_category"),
                "recognition_tier": elig.get("recognition_tier"),
                "evidence_status": elig.get("evidence_status"),
                "gate_outcome": elig.get("gate_outcome") or handoff.get("gate_outcome"),
                "final_eligibility_claimed": False,
                "missing_evidence": elig.get("missing_evidence") or [],
            },
            "memory_feeds_eligibility": True,
            "memory_feeds_binder": True,
            "memory_feeds_checklist": True,
            "memory_feeds_narrative_scaffold": True,
            "memory_feeds_readiness_queue": True,
            "memory_alone_sufficient_for_final_eligibility": False,
            "federal_state_recognition_kept_distinct": federal_state_ok,
            "integration_notes": notes
            + [
                "Missing UEI/SAM/governance/resolutions become binder and checklist gaps",
                "Prohibited claims remain visible for narrative scaffold guardrails",
                "Readiness rollup can cite org-memory missing counts without inventing facts",
            ],
            "final_eligibility_claimed": False,
            "customer_data_persistence_claimed": False,
        }
    )


def org_eligibility_integration_invariant_failures(
    packet: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if packet.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if packet.get("memory_alone_sufficient_for_final_eligibility") is True:
        fails.append("memory_sufficient_false_positive")
    if packet.get("federal_state_recognition_kept_distinct") is not True:
        fails.append("recognition_conflated")
    if packet.get("customer_data_persistence_claimed") is True:
        fails.append("persistence_claimed")
    oem = packet.get("organization_evidence") or {}
    fails.extend(organization_evidence_invariant_failures(oem))
    elig = packet.get("eligibility_handoff_summary") or {}
    if elig.get("final_eligibility_claimed") is True:
        fails.append("elig_final_claimed")
    return fails
