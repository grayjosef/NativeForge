"""Build organization evidence memory from SC pilot fixtures (Block 08).

Honest mapping only — no invented population, awards, UEI/SAM, or resolutions.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.organization_evidence_memory_contract_service import (
    build_organization_evidence_profile,
    make_evidence_fact,
    organization_evidence_invariant_failures,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_organization_evidence_memory_builder_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _recognition_tier(recognition_type: str) -> str:
    if recognition_type == "federal":
        return "federal"
    if recognition_type == "state_only":
        return "state_only"
    return "unknown"


def _recognition_source(profile: dict[str, Any]) -> str | None:
    prov = profile.get("provenance") or {}
    field_sources = prov.get("field_sources") or {}
    rec = field_sources.get("recognition_type") or {}
    return rec.get("source") or None


def build_organization_evidence_from_fixture(
    profile: dict[str, Any],
) -> dict[str, Any]:
    pid = str(profile.get("fixture_key") or "")
    name = str(profile.get("organization_name") or pid)
    rec = str(profile.get("recognition_type") or "unknown")
    tier = _recognition_tier(rec)
    org_type = str(profile.get("applicant_type") or "unknown")
    geo = profile.get("service_geography")
    missing: list[str] = [
        "uei_confirmation",
        "sam_registration",
        "native_population_verified",
        "prior_awards_verified",
        "tribal_resolution_inventory",
        "governance_documents",
        "standard_attachments_inventory",
    ]
    if profile.get("fiscal_sponsor_available") is None:
        missing.append("fiscal_sponsor_status")

    approved: list[dict[str, Any]] = []
    # Name + recognition from fixture public sources may be known but still need review
    # — not auto-approved for reuse without human review path.
    name_fact = make_evidence_fact(
        fact_id=f"{pid}:name",
        label="Organization name",
        value=name,
        evidence_status="public_inferred",
        source=_recognition_source(profile) or "sc_tribal_profiles_fixture",
        human_review_required=True,
        approved=False,
    )
    rec_fact = make_evidence_fact(
        fact_id=f"{pid}:recognition",
        label="Recognition type",
        value=rec,
        evidence_status="public_inferred",
        source=_recognition_source(profile),
        human_review_required=True,
        approved=False,
    )

    attachments = [
        {
            "attachment_id": f"{pid}:uei_sam",
            "label": "UEI / SAM confirmation",
            "status": "missing",
            "binary_upload_persistence_supported": False,
        },
        {
            "attachment_id": f"{pid}:irs_501c3",
            "label": "IRS determination letter (if applicable)",
            "status": "not_applicable" if not profile.get("has_501c3") else "missing",
            "binary_upload_persistence_supported": False,
        },
        {
            "attachment_id": f"{pid}:board_governance",
            "label": "Board / governance documents",
            "status": "missing",
            "binary_upload_persistence_supported": False,
        },
    ]
    governance = [
        {
            "document_id": f"{pid}:governance",
            "label": "Governance documentation",
            "status": "missing",
            "note": "Do not invent governance text",
        }
    ]
    resolutions = [
        {
            "requirement_id": f"{pid}:tribal_resolution",
            "label": "Tribal resolution if required by opportunity",
            "status": "needs_confirmation",
            "note": "Do not fabricate resolution text",
        }
    ]
    fiscal = []
    if profile.get("fiscal_sponsor_available") is True:
        fiscal.append(
            {
                "relationship_id": f"{pid}:fiscal",
                "label": "Fiscal sponsor available (fixture flag)",
                "status": "needs_confirmation",
                "note": "Confirm with customer; do not invent agreement terms",
            }
        )
    elif profile.get("fiscal_sponsor_available") is False:
        fiscal.append(
            {
                "relationship_id": f"{pid}:fiscal",
                "label": "Fiscal sponsor not indicated",
                "status": "not_in_source",
                "note": "Do not invent a fiscal sponsor",
            }
        )
    else:
        fiscal.append(
            {
                "relationship_id": f"{pid}:fiscal",
                "label": "Fiscal sponsor status unknown",
                "status": "missing",
                "note": "Confirm with customer",
            }
        )

    # Population claims: never invent numbers
    population_claims = [
        make_evidence_fact(
            fact_id=f"{pid}:population",
            label="Native population / community count",
            value=None,
            evidence_status="not_supported",
            source=None,
            human_review_required=True,
            approved=False,
        )
    ]

    prior_awards: list[dict[str, Any]] = [
        {
            "award_id": f"{pid}:prior_awards",
            "label": "Prior awards inventory",
            "status": "missing",
            "value": None,
            "note": "Do not invent past performance",
        }
    ]

    program_areas = list(profile.get("program_areas") or [])
    communities = program_areas  # service themes only — not demographic invention

    missing_prompts = [
        f"What verified evidence exists for '{m}' for {name}? Do not invent."
        for m in missing
    ]

    oem = build_organization_evidence_profile(
        organization_profile_id=pid,
        organization_name=name,
        organization_type=org_type,
        recognition_status=rec,
        recognition_tier=tier,
        recognition_source=_recognition_source(profile),
        uei_status="missing",
        sam_status="missing",
        service_geography=str(geo) if geo else None,
        communities_served=communities,
        native_population_claims=population_claims,
        approved_org_facts=approved,  # empty — none auto-approved
        prohibited_org_claims=None,
        prior_awards=prior_awards,
        standard_attachments=attachments,
        governance_documents=governance,
        tribal_resolution_requirements=resolutions,
        fiscal_sponsor_relationships=fiscal,
        partner_relationships=[
            {
                "relationship_id": f"{pid}:partners",
                "label": "Partner relationships",
                "status": "missing",
                "note": "Do not invent partners",
            }
        ],
        evidence_status="needs_confirmation",
        missing_evidence=missing,
        human_review_required=True,
        last_reviewed_at=None,
        data_mode="curated_fixture",
    )
    oem["candidate_facts_needing_review"] = [name_fact, rec_fact]
    oem["missing_evidence_prompts"] = missing_prompts
    oem["how_memory_helps_readiness"] = [
        "Recognition tier memory feeds eligibility explanations without re-deriving from scratch",
        "Missing UEI/SAM/governance items become checklist and intake gaps",
        "Prohibited claims stay visible so packages do not invent tribal facts",
        "Prior awards remain missing until customer provides verified evidence",
    ]
    return _json_safe(oem)


def build_organization_evidence_memory_pack(
    *,
    max_profiles: int | None = None,
) -> dict[str, Any]:
    profiles = load_sc_tribal_profiles()
    if max_profiles is not None:
        profiles = profiles[:max_profiles]
    items = [build_organization_evidence_from_fixture(p) for p in profiles]
    fails: list[str] = []
    for item in items:
        fails.extend(organization_evidence_invariant_failures(item))
    federal = sum(1 for i in items if i.get("recognition_tier") == "federal")
    state = sum(1 for i in items if i.get("recognition_tier") == "state_only")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_count": len(items),
            "federal_count": federal,
            "state_only_count": state,
            "profiles": items,
            "customer_data_persistence_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "builder_invariant_failures": fails,
        }
    )
