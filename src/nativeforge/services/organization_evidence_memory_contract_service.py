"""Organization evidence memory contract (Campaign Block 08).

Durable org evidence profile from fixture/public sources only.
No fact treated as approved without evidence/review. No customer persistence claim.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_organization_evidence_memory_contract_v1"

EVIDENCE_STATUSES: frozenset[str] = frozenset(
    {
        "known",
        "public_inferred",
        "needs_confirmation",
        "missing",
        "not_in_source",
        "not_supported",
        "blocked",
        "approved_for_reuse",
    }
)

RECOGNITION_TIERS: frozenset[str] = frozenset(
    {
        "federal",
        "state_only",
        "native_serving_nonprofit",
        "tribal_college",
        "alaska_native",
        "native_hawaiian",
        "consortium",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_organization_evidence_profile_id(organization_profile_id: str) -> str:
    raw = f"oem::{organization_profile_id}".encode()
    return f"oem_{hashlib.sha256(raw).hexdigest()[:16]}"


def make_evidence_fact(
    *,
    fact_id: str,
    label: str,
    value: Any,
    evidence_status: str,
    source: str | None = None,
    human_review_required: bool = True,
    approved: bool = False,
) -> dict[str, Any]:
    status = evidence_status if evidence_status in EVIDENCE_STATUSES else "missing"
    if status in {"missing", "not_in_source", "not_supported", "blocked"}:
        value = None
    # Approved requires known/public_inferred + review acknowledgment path;
    # builders must pass approved=True only when explicitly reviewed.
    if approved and status not in {"known", "public_inferred", "approved_for_reuse"}:
        approved = False
        status = "needs_confirmation"
    if approved:
        status = "approved_for_reuse"
        human_review_required = False
    return _json_safe(
        {
            "fact_id": fact_id,
            "label": label,
            "value": value,
            "evidence_status": status,
            "source": source,
            "human_review_required": human_review_required,
            "approved": approved,
            "fabricated": False,
        }
    )


def build_organization_evidence_profile(
    *,
    organization_profile_id: str,
    organization_name: str,
    organization_type: str,
    recognition_status: str,
    recognition_tier: str,
    recognition_source: str | None = None,
    uei_status: str = "missing",
    sam_status: str = "missing",
    service_geography: str | None = None,
    communities_served: list[str] | None = None,
    native_population_claims: list[dict[str, Any]] | None = None,
    approved_org_facts: list[dict[str, Any]] | None = None,
    prohibited_org_claims: list[str] | None = None,
    prior_awards: list[dict[str, Any]] | None = None,
    standard_attachments: list[dict[str, Any]] | None = None,
    governance_documents: list[dict[str, Any]] | None = None,
    tribal_resolution_requirements: list[dict[str, Any]] | None = None,
    fiscal_sponsor_relationships: list[dict[str, Any]] | None = None,
    partner_relationships: list[dict[str, Any]] | None = None,
    evidence_status: str = "needs_confirmation",
    missing_evidence: list[str] | None = None,
    human_review_required: bool = True,
    last_reviewed_at: str | None = None,
    data_mode: str = "curated_fixture",
) -> dict[str, Any]:
    tier = recognition_tier if recognition_tier in RECOGNITION_TIERS else "unknown"
    status = (
        evidence_status
        if evidence_status in EVIDENCE_STATUSES
        else "needs_confirmation"
    )
    approved = list(approved_org_facts or [])
    # Guard: strip unapproved facts claiming approved
    cleaned_approved = []
    for f in approved:
        if f.get("approved") is True and f.get("evidence_status") in {
            "known",
            "public_inferred",
            "approved_for_reuse",
        }:
            cleaned_approved.append(f)
    prohibited = list(
        prohibited_org_claims
        or [
            "Do not invent tribal history, population counts, or past performance",
            "Do not treat state recognition as federal recognition",
            "Do not claim final eligibility from organization memory alone",
            "Do not invent UEI/SAM, budgets, resolutions, or partner commitments",
        ]
    )
    missing = list(missing_evidence or [])
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_evidence_profile_id": make_organization_evidence_profile_id(
                organization_profile_id
            ),
            "organization_profile_id": organization_profile_id,
            "organization_name": organization_name,
            "organization_type": organization_type,
            "recognition_status": recognition_status,
            "recognition_tier": tier,
            "recognition_source": recognition_source,
            "uei_status": uei_status if uei_status in EVIDENCE_STATUSES else "missing",
            "sam_status": sam_status if sam_status in EVIDENCE_STATUSES else "missing",
            "service_geography": service_geography,
            "communities_served": list(communities_served or []),
            "native_population_claims": list(native_population_claims or []),
            "approved_org_facts": cleaned_approved,
            "prohibited_org_claims": prohibited,
            "prior_awards": list(prior_awards or []),
            "standard_attachments": list(standard_attachments or []),
            "governance_documents": list(governance_documents or []),
            "tribal_resolution_requirements": list(
                tribal_resolution_requirements or []
            ),
            "fiscal_sponsor_relationships": list(fiscal_sponsor_relationships or []),
            "partner_relationships": list(partner_relationships or []),
            "evidence_status": status,
            "missing_evidence": missing,
            "human_review_required": human_review_required,
            "last_reviewed_at": last_reviewed_at,
            "data_mode": data_mode,
            "customer_data_persistence_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "fabricated_org_facts": False,
            "federal_state_recognition_conflated": False,
        }
    )


def organization_evidence_invariant_failures(profile: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if profile.get("customer_data_persistence_claimed") is True:
        fails.append("customer_data_persistence_claimed")
    if profile.get("final_eligibility_claimed") is True:
        fails.append("final_eligibility_claimed")
    if profile.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if profile.get("fabricated_org_facts") is True:
        fails.append("fabricated_org_facts")
    if profile.get("federal_state_recognition_conflated") is True:
        fails.append("federal_state_recognition_conflated")
    if profile.get("recognition_tier") not in RECOGNITION_TIERS:
        fails.append("bad_recognition_tier")
    # State must never be labeled federal
    if (
        profile.get("recognition_status") == "state_only"
        and profile.get("recognition_tier") == "federal"
    ):
        fails.append("state_labeled_federal")
    if (
        profile.get("recognition_status") == "federal"
        and profile.get("recognition_tier") == "state_only"
    ):
        fails.append("federal_labeled_state")
    for f in profile.get("approved_org_facts") or []:
        if f.get("approved") is True and f.get("evidence_status") not in {
            "known",
            "public_inferred",
            "approved_for_reuse",
        }:
            fails.append(f"unapproved_fact:{f.get('fact_id')}")
        if f.get("fabricated") is True:
            fails.append(f"fabricated_fact:{f.get('fact_id')}")
    # Population claims must not invent numbers
    for claim in profile.get("native_population_claims") or []:
        if claim.get("value") is not None and claim.get("evidence_status") in {
            "missing",
            "not_in_source",
            "not_supported",
        }:
            fails.append(f"population_without_evidence:{claim.get('fact_id')}")
    if not profile.get("prohibited_org_claims"):
        fails.append("missing_prohibited_claims")
    return fails
