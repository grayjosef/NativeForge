"""Assemble organization evidence memory demo surface (Campaign Block 08)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
)
from nativeforge.services.organization_evidence_eligibility_integration_service import (
    integrate_org_memory_with_eligibility,
    org_eligibility_integration_invariant_failures,
)
from nativeforge.services.organization_evidence_memory_builder_service import (
    build_organization_evidence_memory_pack,
)
from nativeforge.services.organization_evidence_memory_contract_service import (
    organization_evidence_invariant_failures,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_organization_evidence_memory_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_organization_evidence_demo_surface(
    *,
    max_profiles: int = 4,
) -> dict[str, Any]:
    pack = build_organization_evidence_memory_pack(max_profiles=max_profiles)
    profiles = load_sc_tribal_profiles()[:max_profiles]
    grants_by_id = {
        str(g.get("grant_id") or g.get("opportunity_id")): g
        for g in grants_from_pack(load_sc_curated_opportunity_pack())
    }
    # Sample eligibility integrations for showcase opps × first two profiles
    integrations: list[dict[str, Any]] = []
    for oid in SHOWCASE_OPPORTUNITY_IDS[:2]:
        opp = grants_by_id.get(oid)
        if not opp:
            continue
        for profile in profiles[:2]:
            integrations.append(integrate_org_memory_with_eligibility(profile, opp))

    cards = []
    for oem in pack.get("profiles") or []:
        cards.append(
            {
                "organization_evidence_profile_id": oem.get(
                    "organization_evidence_profile_id"
                ),
                "organization_profile_id": oem.get("organization_profile_id"),
                "organization_name": oem.get("organization_name"),
                "recognition_status": oem.get("recognition_status"),
                "recognition_tier": oem.get("recognition_tier"),
                "recognition_source": oem.get("recognition_source"),
                "uei_status": oem.get("uei_status"),
                "sam_status": oem.get("sam_status"),
                "service_geography": oem.get("service_geography"),
                "evidence_status": oem.get("evidence_status"),
                "missing_evidence": oem.get("missing_evidence") or [],
                "missing_evidence_prompts": oem.get("missing_evidence_prompts") or [],
                "approved_org_facts": oem.get("approved_org_facts") or [],
                "prohibited_org_claims": oem.get("prohibited_org_claims") or [],
                "candidate_facts_needing_review": oem.get(
                    "candidate_facts_needing_review"
                )
                or [],
                "standard_attachments": oem.get("standard_attachments") or [],
                "governance_documents": oem.get("governance_documents") or [],
                "tribal_resolution_requirements": oem.get(
                    "tribal_resolution_requirements"
                )
                or [],
                "prior_awards": oem.get("prior_awards") or [],
                "fiscal_sponsor_relationships": oem.get("fiscal_sponsor_relationships")
                or [],
                "how_memory_helps_readiness": oem.get("how_memory_helps_readiness")
                or [],
                "human_review_required": oem.get("human_review_required"),
                "customer_data_persistence_claimed": False,
                "final_eligibility_claimed": False,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 8,
            "title": "Organization evidence memory",
            "profile_count": pack.get("profile_count"),
            "federal_count": pack.get("federal_count"),
            "state_only_count": pack.get("state_only_count"),
            "cards": cards,
            "eligibility_integrations": integrations,
            "customer_data_persistence_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "fabricated_org_facts": False,
            "federal_state_recognition_conflated": False,
            "binary_upload_persistence_supported": False,
            "buyer_summary": [
                "What NativeForge knows about the organization from curated fixture evidence",
                "Recognition status stays evidence-backed; federal and state stay distinct",
                "UEI/SAM, population, prior awards, and resolutions remain missing until verified",
                "No customer data persistence claimed; no final eligibility from memory alone",
            ],
        }
    )


def organization_evidence_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "customer_data_persistence_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
        "fabricated_org_facts",
        "federal_state_recognition_conflated",
        "binary_upload_persistence_supported",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("profile_count") or 0) < 1:
        fails.append("no_profiles")
    if (surface.get("federal_count") or 0) < 1:
        fails.append("need_federal_profile")
    if (surface.get("state_only_count") or 0) < 1:
        fails.append("need_state_profile")
    for card in surface.get("cards") or []:
        # Rebuild minimal profile for invariant check
        pseudo = {
            **card,
            "organization_type": "tribal_government",
            "native_population_claims": [],
            "partner_relationships": [],
            "data_mode": "curated_fixture",
            "human_review_required": True,
            "evidence_status": card.get("evidence_status") or "needs_confirmation",
            "customer_data_persistence_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "fabricated_org_facts": False,
            "federal_state_recognition_conflated": False,
        }
        fails.extend(organization_evidence_invariant_failures(pseudo))
        if (
            card.get("recognition_status") == "state_only"
            and card.get("recognition_tier") == "federal"
        ):
            fails.append("card_state_as_federal")
        if not card.get("prohibited_org_claims"):
            fails.append("card_missing_prohibited")
        if card.get("customer_data_persistence_claimed") is True:
            fails.append("card_persistence")
    for integ in surface.get("eligibility_integrations") or []:
        fails.extend(org_eligibility_integration_invariant_failures(integ))
    return fails
