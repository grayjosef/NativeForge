"""Top-15 state coverage seed + assembler (Campaign Block 27).

Provisional, evidence-backed, updateable — not permanent 'best states' truth.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.coverage_ranking_contract_service import (
    build_coverage_ranking_record,
    coverage_ranking_invariant_failures,
)
from nativeforge.services.recognition_routing_contract_service import (
    build_recognition_routing_record,
    recognition_routing_invariant_failures,
)

SCHEMA_VERSION = "nf_national_coverage_assembler_v1"

# Provisional seed — each requires evidence refs + human review for top_15_claimed
_TOP15_SEED: list[dict[str, Any]] = [
    {
        "state_code": "SC",
        "state_name": "South Carolina",
        "score": 92.0,
        "reasons": [
            "Active customer/demo lane",
            "Known state-recognized tribes (Catawba federal; others state/unknown)",
            "Existing SC demo fixture coverage",
        ],
        "native_relevance": 90.0,
        "density": 70.0,
        "federal_presence": "present",
        "state_presence": "present",
        "accessibility": 75.0,
        "freshness": "curated_current_demo",
        "reliability": "medium",
        "portal": "partially_known",
        "known": 12,
        "estimated": 40,
        "refs": [
            "fixtures/sc_monday_demo",
            "docs/operations/99_MONDAY_BUYER_DEMO_RUNBOOK.md",
        ],
        "confidence": "medium",
        "categories": ["community_development", "education", "health", "housing"],
        "active_lane": True,
        "tier": "top_15_selected",
    },
    {
        "state_code": "OK",
        "state_name": "Oklahoma",
        "score": 91.0,
        "reasons": [
            "High federally recognized tribe density",
            "Strong Native-relevant federal+state opportunity landscape (modeled)",
        ],
        "native_relevance": 95.0,
        "density": 88.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 60.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 120,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["infrastructure", "workforce", "education", "health"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "AZ",
        "state_name": "Arizona",
        "score": 89.0,
        "reasons": ["Large tribal lands footprint", "Federal opportunity relevance"],
        "native_relevance": 93.0,
        "density": 80.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 100,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["water", "infrastructure", "health", "housing"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "NM",
        "state_name": "New Mexico",
        "score": 88.0,
        "reasons": ["High tribal nation count", "State+federal program relevance"],
        "native_relevance": 94.0,
        "density": 82.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 95,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["education", "health", "housing", "environment"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "AK",
        "state_name": "Alaska",
        "score": 87.0,
        "reasons": ["Alaska Native entities", "Distinct federal eligibility pathways"],
        "native_relevance": 96.0,
        "density": 78.0,
        "federal_presence": "present",
        "state_presence": "n/a_distinct",
        "accessibility": 50.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 90,
        "refs": ["seed:provisional_alaska_native_entity_model"],
        "confidence": "low",
        "categories": ["community_development", "infrastructure", "health"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "CA",
        "state_name": "California",
        "score": 86.0,
        "reasons": [
            "Many federally recognized tribes",
            "State recognition landscape needs careful routing",
        ],
        "native_relevance": 90.0,
        "density": 85.0,
        "federal_presence": "present",
        "state_presence": "present_needs_verification",
        "accessibility": 65.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 110,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["environment", "workforce", "housing", "education"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "WA",
        "state_name": "Washington",
        "score": 84.0,
        "reasons": ["Multiple federally recognized tribes", "State program relevance"],
        "native_relevance": 88.0,
        "density": 72.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 60.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 70,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["fisheries", "environment", "health", "education"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "OR",
        "state_name": "Oregon",
        "score": 82.0,
        "reasons": ["Tribal nations present", "State grant portal research needed"],
        "native_relevance": 85.0,
        "density": 68.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 55,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["environment", "workforce", "community_development"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "MT",
        "state_name": "Montana",
        "score": 81.0,
        "reasons": ["Reservation footprint", "Rural development relevance"],
        "native_relevance": 87.0,
        "density": 65.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 50.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 50,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["infrastructure", "education", "health"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "SD",
        "state_name": "South Dakota",
        "score": 80.0,
        "reasons": ["Multiple federally recognized tribes", "Native-relevant funding"],
        "native_relevance": 90.0,
        "density": 70.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 50.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 60,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["housing", "health", "education", "infrastructure"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "ND",
        "state_name": "North Dakota",
        "score": 78.0,
        "reasons": ["Tribal nations present", "Energy/infrastructure relevance"],
        "native_relevance": 84.0,
        "density": 60.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 45.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 45,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["energy", "infrastructure", "education"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "MN",
        "state_name": "Minnesota",
        "score": 77.0,
        "reasons": [
            "Tribal nations + urban Native orgs",
            "State program research needed",
        ],
        "native_relevance": 83.0,
        "density": 62.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 55,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["health", "education", "workforce"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "WI",
        "state_name": "Wisconsin",
        "score": 76.0,
        "reasons": ["Tribal nations present", "State grant density needs validation"],
        "native_relevance": 82.0,
        "density": 58.0,
        "federal_presence": "present",
        "state_presence": "unknown",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 50,
        "refs": ["seed:provisional_native_opportunity_density_model"],
        "confidence": "low",
        "categories": ["education", "environment", "health"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "NC",
        "state_name": "North Carolina",
        "score": 75.0,
        "reasons": [
            "Federally recognized + state-recognized landscape",
            "Southeast adjacency to SC active lane",
        ],
        "native_relevance": 80.0,
        "density": 60.0,
        "federal_presence": "present",
        "state_presence": "present_needs_verification",
        "accessibility": 55.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 55,
        "refs": ["seed:provisional_southeast_native_coverage_model"],
        "confidence": "low",
        "categories": ["education", "community_development", "health"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
    {
        "state_code": "HI",
        "state_name": "Hawaii",
        "score": 74.0,
        "reasons": [
            "Native Hawaiian organization pathways",
            "Distinct from continental tribal recognition",
        ],
        "native_relevance": 92.0,
        "density": 55.0,
        "federal_presence": "distinct_native_hawaiian_pathways",
        "state_presence": "distinct",
        "accessibility": 50.0,
        "freshness": "unknown",
        "reliability": "unknown",
        "portal": "needs_research",
        "known": None,
        "estimated": 40,
        "refs": ["seed:provisional_native_hawaiian_org_model"],
        "confidence": "low",
        "categories": ["housing", "education", "health", "culture"],
        "active_lane": False,
        "tier": "top_15_selected",
    },
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_top15_coverage_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for seed in _TOP15_SEED:
        rec = build_coverage_ranking_record(
            state_code=seed["state_code"],
            state_name=seed["state_name"],
            coverage_tier=seed["tier"],
            ranking_score=seed["score"],
            ranking_reasons=seed["reasons"],
            native_relevance_score=seed["native_relevance"],
            state_grant_density_score=seed["density"],
            federal_tribe_presence=seed["federal_presence"],
            state_recognized_tribe_presence=seed["state_presence"],
            source_accessibility_score=seed["accessibility"],
            source_freshness_status=seed["freshness"],
            source_reliability_status=seed["reliability"],
            state_portal_status=seed["portal"],
            opportunity_count_known=seed["known"],
            opportunity_count_estimated=seed["estimated"],
            ranking_evidence_refs=seed["refs"],
            ranking_confidence=seed["confidence"],
            human_review_required=True,
            top_15_claimed=True,
        )
        rec["known_opportunity_categories"] = list(seed["categories"])
        rec["active_customer_lane"] = bool(seed["active_lane"])
        rec["next_source_validation_action"] = (
            "Validate state portal + Native-relevant opportunity inventory"
            if seed["state_code"] != "SC"
            else "Maintain SC curated-current demo lane; expand inventory carefully"
        )
        rec["modeled_only"] = seed["state_code"] != "SC"
        records.append(rec)
    return records


def build_recognition_routing_examples() -> list[dict[str, Any]]:
    """Deterministic examples proving federal-only gate blocks state-recognized."""
    examples = [
        build_recognition_routing_record(
            organization_profile_id="sc_pilot_catawba_indian_nation",
            entity_type="federally_recognized_tribe",
            opportunity_id="fed_ana_seds_example",
            opportunity_jurisdiction="federal",
            opportunity_requires_federal_recognition=True,
            federal_recognition_evidence_refs=["bia_federal_register:placeholder_ref"],
            federal_recognition_source="BIA/Federal_Register_placeholder",
        ),
        build_recognition_routing_record(
            organization_profile_id="sc_state_recognized_example_org",
            entity_type="state_recognized_tribe",
            opportunity_id="fed_ana_seds_example",
            opportunity_jurisdiction="federal",
            opportunity_requires_federal_recognition=True,
            state_recognition_evidence_refs=["sc_state_recognition:placeholder"],
            state_recognition_source="SC_state_list_placeholder",
        ),
        build_recognition_routing_record(
            organization_profile_id="sc_state_recognized_example_org",
            entity_type="state_recognized_tribe",
            opportunity_id="sc_state_community_dev_example",
            opportunity_jurisdiction="state",
            opportunity_allows_state_recognized=True,
            state_recognition_evidence_refs=["sc_state_recognition:placeholder"],
            state_recognition_source="SC_state_list_placeholder",
        ),
    ]
    return examples


def build_national_coverage_demo_surface() -> dict[str, Any]:
    records = build_top15_coverage_records()
    routing = build_recognition_routing_examples()
    selected = [r for r in records if r.get("coverage_tier") == "top_15_selected"]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 27,
            "title": "National coverage + recognition routing",
            "coverage_records": records,
            "top_15_states": [
                {"state_code": r["state_code"], "state_name": r["state_name"]}
                for r in selected
            ],
            "top_15_count": len(selected),
            "active_customer_lane": "SC",
            "recognition_routing_examples": routing,
            "buyer_summary": [
                "Top-15 state coverage model is provisional and evidence-backed",
                "SC remains the active customer/demo lane; other states are modeled",
                "Federal recognition routing cites BIA/Federal Register placeholders",
                "State-recognized tribes do not pass federal-recognition-only gates",
                "Live multi-state coverage is not claimed",
            ],
            "live_coverage_claimed": False,
            "permanent_best_states_claimed": False,
            "all_state_recognized_verified_claimed": False,
            "all_federal_tribes_onboarded_claimed": False,
            "final_eligibility_claimed": False,
            "ranking_confidence_summary": "mostly_low_except_SC_medium",
            "what_is_live": ["SC curated-current demo lane"],
            "what_is_modeled_only": [
                r["state_code"] for r in selected if r["state_code"] != "SC"
            ],
            "what_needs_research": [
                "State portals for non-SC top-15",
                "Per-state recognition evidence packs",
                "Native-relevant opportunity inventories",
            ],
            "what_cannot_be_claimed_yet": [
                "Live top-15 coverage",
                "Final eligibility",
                "All recognition statuses verified",
            ],
            "federally_recognized_tribe_source": "BIA/Federal_Register_placeholder",
            "human_review_required": True,
        }
    )


def national_coverage_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "live_coverage_claimed",
        "permanent_best_states_claimed",
        "all_state_recognized_verified_claimed",
        "all_federal_tribes_onboarded_claimed",
        "final_eligibility_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("top_15_count") != 15:
        fails.append(f"top_15_count:{surface.get('top_15_count')}")
    for rec in surface.get("coverage_records") or []:
        fails.extend(coverage_ranking_invariant_failures(rec))
    for rr in surface.get("recognition_routing_examples") or []:
        fails.extend(recognition_routing_invariant_failures(rr))
    return fails
