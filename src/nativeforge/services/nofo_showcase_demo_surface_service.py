"""Assemble NOFO showcase surface for SC Monday customer demo (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_showcase_application_plan_service import (
    application_plan_invariant_failures,
    build_application_plans_for_pack,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    load_selected_intelligence_pack,
    pack_invariant_failures,
    write_selected_intelligence_pack,
)

SCHEMA_VERSION = "nf_nofo_showcase_demo_surface_v1"
DEFAULT_PLANS_PATH = Path(
    "fixtures/nofo_showcase/selected_opportunity_application_plans.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_nofo_showcase_demo_surface(
    *,
    write_fixtures: bool = False,
) -> dict[str, Any]:
    """Build buyer-facing showcase payload for selected opportunities."""
    if write_fixtures:
        write_selected_intelligence_pack()
    pack = load_selected_intelligence_pack(require_file=False)
    plans_bundle = build_application_plans_for_pack(pack)
    if write_fixtures:
        DEFAULT_PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_PLANS_PATH.write_text(
            json.dumps(plans_bundle, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    by_id = {o["opportunity_id"]: o for o in pack.get("opportunities") or []}
    cards: list[dict[str, Any]] = []
    for plan in plans_bundle.get("plans") or []:
        oid = plan.get("opportunity_id")
        intel = by_id.get(str(oid)) or {}
        fields = intel.get("fields") or {}
        status_summary: dict[str, int] = {}
        for f in fields.values():
            st = str(f.get("status") or "unknown")
            status_summary[st] = status_summary.get(st, 0) + 1
        cards.append(
            {
                "opportunity_id": oid,
                "source_layer": intel.get("source_layer") or plan.get("source_layer"),
                "source_name": intel.get("source_name"),
                "title": (fields.get("title") or {}).get("value"),
                "data_mode": intel.get("data_mode"),
                "live_ingest_claimed": False,
                "synopsis_availability": intel.get("synopsis_availability"),
                "nofo_document_availability": intel.get("nofo_document_availability"),
                "extraction_method": intel.get("extraction_method"),
                "extraction_confidence": intel.get("extraction_confidence"),
                "human_review_required": True,
                "field_status_counts": status_summary,
                "unresolved_fields": intel.get("unresolved_fields") or [],
                "what_nativeforge_found": {
                    "purpose": (fields.get("purpose") or {}).get("value"),
                    "eligibility": (fields.get("eligibility") or {}).get("value"),
                    "tribal_native_relevance": (
                        fields.get("tribal_native_relevance") or {}
                    ).get("value"),
                    "deadline": (fields.get("deadline") or {}).get("value"),
                    "deadline_status": (fields.get("deadline") or {}).get("status"),
                },
                "what_this_means": plan.get("why_worth_review"),
                "what_is_missing": [
                    {
                        "field": name,
                        "status": (fields.get(name) or {}).get("status"),
                        "evidence_note": (fields.get(name) or {}).get("evidence_note"),
                    }
                    for name in (intel.get("unresolved_fields") or [])
                ],
                "what_needs_human_review": plan.get("human_approval_gates") or [],
                "what_to_do_next": plan.get("required_decisions") or [],
                "application_plan": {
                    "recommendation_label": plan.get("recommendation_label"),
                    "application_checklist": plan.get("application_checklist"),
                    "narrative_section_scaffold": plan.get(
                        "narrative_section_scaffold"
                    ),
                    "forms_checklist": plan.get("forms_checklist"),
                    "attachment_checklist": plan.get("attachment_checklist"),
                    "missing_information_questions": plan.get(
                        "missing_information_questions"
                    ),
                    "completeness": plan.get("completeness"),
                    "proposal_drafting_claimed": False,
                    "nofo_pdf_extraction_claimed": False,
                },
                "evidence_provenance": {
                    "source_reference": intel.get("source_reference"),
                    "captured_at": intel.get("captured_at"),
                    "retrieved_at": intel.get("retrieved_at"),
                    "demo_real_isolation_label": intel.get("demo_real_isolation_label"),
                },
                "limitations": [
                    "Curated-current / synopsis intelligence only",
                    "Full NOFO PDF extraction is not_supported",
                    "Proposal narrative drafting is not_supported",
                    "No fabricated org facts, budgets, resolutions, or past performance",
                ],
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "NOFO / synopsis intelligence + application plan skeleton",
            "pack_id": pack.get("pack_id"),
            "selected_count": len(cards),
            "sc_selected_count": sum(
                1 for c in cards if c.get("source_layer") == "sc_state"
            ),
            "federal_selected_count": sum(
                1 for c in cards if c.get("source_layer") == "federal"
            ),
            "live_ingest_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "proposal_drafting_claimed": False,
            "buyer_sections": [
                "What NativeForge found",
                "What this means",
                "What is missing",
                "What needs human review",
                "What to do next",
            ],
            "cards": cards,
        }
    )


def nofo_showcase_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if surface.get("nofo_pdf_extraction_claimed") is True:
        fails.append("pdf_claimed")
    if surface.get("proposal_drafting_claimed") is True:
        fails.append("proposal_claimed")
    if (surface.get("sc_selected_count") or 0) < 1:
        fails.append("missing_sc_card")
    if (surface.get("federal_selected_count") or 0) < 1:
        fails.append("missing_federal_card")
    for card in surface.get("cards") or []:
        if not card.get("human_review_required"):
            fails.append(f"human_review_false:{card.get('opportunity_id')}")
        plan = card.get("application_plan") or {}
        if plan.get("proposal_drafting_claimed") is True:
            fails.append("card_proposal_claimed")
        if plan.get("nofo_pdf_extraction_claimed") is True:
            fails.append("card_pdf_claimed")
        for section in plan.get("narrative_section_scaffold") or []:
            if section.get("content") not in (None, ""):
                fails.append("narrative_fabricated")
        # Re-check plan completeness invariants via rebuild shape
        fake_plan = {
            "proposal_drafting_claimed": plan.get("proposal_drafting_claimed"),
            "nofo_pdf_extraction_claimed": plan.get("nofo_pdf_extraction_claimed"),
            "completeness": plan.get("completeness"),
            "narrative_section_scaffold": plan.get("narrative_section_scaffold"),
            "missing_information_questions": plan.get("missing_information_questions"),
        }
        fails.extend(application_plan_invariant_failures(fake_plan))
    pack = load_selected_intelligence_pack(require_file=False)
    fails.extend(pack_invariant_failures(pack))
    return fails
