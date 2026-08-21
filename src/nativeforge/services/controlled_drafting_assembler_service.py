"""Assemble controlled drafting v0 demo surface (Campaign Block 12)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.controlled_drafting_contract_service import (
    controlled_draft_invariant_failures,
)
from nativeforge.services.evidence_cited_drafting_service import (
    build_controlled_drafts_for_pair,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    load_selected_intelligence_pack,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_controlled_drafting_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_controlled_drafting_demo_surface(
    *, max_workspaces: int = 2
) -> dict[str, Any]:
    profiles = load_sc_tribal_profiles()
    grants_by_id = {
        str(g.get("grant_id") or g.get("opportunity_id")): g
        for g in grants_from_pack(load_sc_curated_opportunity_pack())
    }
    pack = load_selected_intelligence_pack(require_file=False)
    intel_by_id = {
        o.get("opportunity_id"): o for o in (pack.get("opportunities") or [])
    }
    workspaces: list[dict[str, Any]] = []
    for oid in SHOWCASE_OPPORTUNITY_IDS[:max_workspaces]:
        opp = grants_by_id.get(oid)
        if not opp:
            continue
        packet = build_controlled_drafts_for_pair(
            profiles[0], opp, nofo_intelligence=intel_by_id.get(oid)
        )
        # Compact card for UI
        drafts = packet.get("drafts") or []
        workspaces.append(
            {
                "opportunity_id": packet.get("opportunity_id"),
                "organization_profile_id": packet.get("organization_profile_id"),
                "draft_workspace_id": packet.get("draft_workspace_id"),
                "draft_count": packet.get("draft_count"),
                "generated_from_evidence_count": packet.get(
                    "generated_from_evidence_count"
                ),
                "placeholder_or_blocked_count": packet.get(
                    "placeholder_or_blocked_count"
                ),
                "drafts": [
                    {
                        "section_id": d.get("section_id"),
                        "drafting_mode": d.get("drafting_mode"),
                        "generation_status": d.get("generation_status"),
                        "generated_text": d.get("generated_text"),
                        "placeholders": d.get("placeholders") or [],
                        "question_prompts": (d.get("question_prompts") or [])[:3],
                        "evidence_inputs": d.get("evidence_inputs") or [],
                        "citation_requirements": d.get("citation_requirements") or [],
                        "generated_draft_warning": d.get("generated_draft_warning"),
                        "human_review_required": d.get("human_review_required"),
                        "final_text_claimed": False,
                        "submission_ready_claimed": False,
                        "complete_proposal_claimed": False,
                        "prohibited_claim_scan": d.get("prohibited_claim_scan"),
                    }
                    for d in drafts[:8]
                ],
                "complete_proposal_claimed": False,
                "submission_ready_claimed": False,
                "final_text_claimed": False,
                "human_review_required": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 12,
            "title": "Controlled draft v0",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Evidence-cited controlled drafting v0 — only from linked evidence",
                "Missing facts become placeholders and questions, not invented prose",
                "Budget/match/tribal/community fabrication blocked",
                "Every generated section is labeled DRAFT and requires human review",
                "Not a complete proposal; not submission-ready; not final",
            ],
            "complete_proposal_claimed": False,
            "submission_ready_claimed": False,
            "final_text_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "human_review_required": True,
        }
    )


def controlled_drafting_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "complete_proposal_claimed",
        "submission_ready_claimed",
        "final_text_claimed",
        "proposal_drafting_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        for d in ws.get("drafts") or []:
            fails.extend(
                controlled_draft_invariant_failures(
                    {
                        **d,
                        "drafting_mode": d.get("drafting_mode"),
                        "generated_text": d.get("generated_text"),
                        "evidence_inputs": d.get("evidence_inputs"),
                        "human_review_required": d.get("human_review_required"),
                        "final_text_claimed": False,
                        "submission_ready_claimed": False,
                        "complete_proposal_claimed": False,
                        "proposal_drafting_claimed": False,
                        "live_ingest_claimed": False,
                    }
                )
            )
    return fails
