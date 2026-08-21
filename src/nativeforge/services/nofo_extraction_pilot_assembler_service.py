"""Integrate NOFO extraction pilot with package chain (Campaign Block 09).

Parallel pilot panel — does not replace curated-current NOFO showcase logic.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nofo_extraction_pilot_contract_service import (
    nofo_extraction_invariant_failures,
)
from nativeforge.services.nofo_extraction_pilot_extractor_service import (
    PILOT_OPPORTUNITY_ID,
    run_controlled_nofo_extraction,
)

SCHEMA_VERSION = "nf_nofo_extraction_pilot_integration_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nofo_extraction_package_integration(
    extraction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nx = extraction or run_controlled_nofo_extraction()
    reqs = nx.get("requirements_map") or []
    extracted_reqs = [r for r in reqs if r.get("status") in {"extracted", "partial"}]
    missing_reqs = [
        r
        for r in reqs
        if r.get("status")
        in {"not_in_source", "not_supported", "missing", "needs_confirmation"}
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunity_id": nx.get("opportunity_id") or PILOT_OPPORTUNITY_ID,
            "nofo_extraction_id": nx.get("nofo_extraction_id"),
            "feeds_nofo_synopsis_intelligence": True,
            "feeds_application_checklist": True,
            "feeds_evidence_binder": True,
            "feeds_narrative_scaffold": True,
            "feeds_budget_match_capture": True,
            "feeds_package_readiness": True,
            "feeds_operator_review_queue": True,
            "replaces_curated_showcase": False,
            "extracted_requirement_count": len(extracted_reqs),
            "missing_or_unconfirmed_requirement_count": len(missing_reqs),
            "checklist_hints": [
                f"Confirm extracted: {r.get('label')}" for r in extracted_reqs[:6]
            ]
            + [
                f"Still missing / needs confirmation: {r.get('label')}"
                for r in missing_reqs[:6]
            ],
            "readiness_blockers_from_extraction": [
                r.get("label")
                for r in missing_reqs
                if r.get("requirement_id")
                in {
                    "narrative_section_requirements",
                    "budget_narrative_requirements",
                    "evaluation_scoring_criteria",
                    "required_forms",
                }
            ],
            "operator_review_hints": [
                "Review controlled NOFO extraction for la-real-006 before customer reliance",
                "Do not treat extracted eligibility language as final eligibility",
                "Full PDF bytes not parsed — forms/scoring/narrative remain incomplete",
            ],
            "human_review_required": True,
            "full_pdf_extraction_claimed": False,
            "broad_pdf_support_claimed": False,
            "proposal_drafting_claimed": False,
            "final_eligibility_claimed": False,
            "extraction": nx,
        }
    )


def nofo_extraction_integration_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "full_pdf_extraction_claimed",
        "broad_pdf_support_claimed",
        "proposal_drafting_claimed",
        "final_eligibility_claimed",
    ):
        if packet.get(key) is True:
            fails.append(key)
    if packet.get("replaces_curated_showcase") is True:
        fails.append("replaced_curated_showcase")
    nx = packet.get("extraction") or {}
    fails.extend(nofo_extraction_invariant_failures(nx))
    return fails


def build_nofo_extraction_demo_surface() -> dict[str, Any]:
    integration = build_nofo_extraction_package_integration()
    nx = integration.get("extraction") or {}
    return _json_safe(
        {
            "schema_version": "nf_nofo_extraction_pilot_assembler_v1",
            "campaign_block": 9,
            "title": "NOFO extraction pilot",
            "pilot_opportunity_id": PILOT_OPPORTUNITY_ID,
            "extraction_status": nx.get("extraction_status"),
            "extraction_scope": nx.get("extraction_scope"),
            "extraction_mode": nx.get("extraction_mode"),
            "data_mode": nx.get("data_mode"),
            "source_document_label": nx.get("source_document_label"),
            "document_url_or_fixture_reference": nx.get(
                "document_url_or_fixture_reference"
            ),
            "named_pdf_attachment_referenced": nx.get(
                "named_pdf_attachment_referenced"
            ),
            "section_extracted_count": nx.get("section_extracted_count"),
            "section_missing_count": nx.get("section_missing_count"),
            "sections": nx.get("sections") or [],
            "requirements_map": nx.get("requirements_map") or [],
            "integration": {
                k: integration[k] for k in integration if k != "extraction"
            },
            "honesty_notes": nx.get("honesty_notes") or [],
            "buyer_summary": [
                "Controlled NOFO/PDF extraction pilot for one showcase opportunity (TEDC / la-real-006)",
                "Extracted from Grants.gov synopsis fixture text — PDF bytes not parsed",
                "Eligibility, deadline, funding, and contact fields extracted with confidence labels",
                "Narrative, scoring, detailed forms remain not_in_source / needs confirmation",
                "Human review required; not generalized; not proposal drafting",
            ],
            "full_pdf_extraction_claimed": False,
            "broad_pdf_support_claimed": False,
            "proposal_drafting_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "pdf_bytes_parsed": False,
            "human_review_required": True,
        }
    )


def nofo_extraction_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "full_pdf_extraction_claimed",
        "broad_pdf_support_claimed",
        "proposal_drafting_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
        "pdf_bytes_parsed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("pilot_opportunity_id") != PILOT_OPPORTUNITY_ID:
        fails.append("wrong_pilot_opportunity")
    if surface.get("extraction_scope") not in {
        "one_showcase_opportunity",
        "controlled_fixture",
        "not_generalized",
    }:
        fails.append("bad_scope")
    if not surface.get("sections"):
        fails.append("no_sections")
    if not surface.get("requirements_map"):
        fails.append("no_requirements")
    integ = surface.get("integration") or {}
    fails.extend(
        nofo_extraction_integration_invariant_failures(
            {
                **integ,
                "extraction": {
                    "full_pdf_extraction_claimed": False,
                    "broad_pdf_support_claimed": False,
                    "proposal_drafting_claimed": False,
                    "final_eligibility_claimed": False,
                    "live_ingest_claimed": False,
                    "pdf_bytes_parsed": False,
                    "extraction_scope": surface.get("extraction_scope"),
                    "extraction_status": surface.get("extraction_status"),
                    "requirements_map": surface.get("requirements_map"),
                },
            }
        )
    )
    return fails
