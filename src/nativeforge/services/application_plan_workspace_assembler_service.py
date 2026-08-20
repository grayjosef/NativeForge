"""Assemble application checklist execution workspace for showcase opportunities.

Campaign Block 04 — package build plan on top of pursuit + evidence binder.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_checklist_execution_contract_service import (
    build_application_checklist_execution_contract,
    checklist_execution_invariant_failures,
)
from nativeforge.services.application_checklist_section_builder_service import (
    build_checklist_sections_from_evidence,
)
from nativeforge.services.missing_information_questionnaire_service import (
    build_missing_information_questionnaire,
    questionnaire_invariant_failures,
)
from nativeforge.services.nofo_showcase_application_plan_service import (
    build_application_plan_skeleton,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    load_selected_intelligence_pack,
)
from nativeforge.services.pursuit_workspace_assembler_service import (
    build_pursuit_workspace_for_pair,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_application_plan_workspace_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_application_plan_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pursuit_packet = build_pursuit_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    ws = pursuit_packet["workspace"]
    binder = pursuit_packet["evidence_binder"]
    eligibility = pursuit_packet.get("eligibility_evidence") or {}
    oid = ws["opportunity_id"]
    pid = ws["organization_profile_id"]
    intel = nofo_intelligence
    if intel is None:
        pack = load_selected_intelligence_pack(require_file=False)
        intel = next(
            (
                o
                for o in (pack.get("opportunities") or [])
                if o.get("opportunity_id") == oid
            ),
            None,
        )
    plan = (
        build_application_plan_skeleton(intel)
        if intel
        else {
            "forms_checklist": [],
            "attachment_checklist": [],
            "narrative_section_scaffold": [],
            "human_approval_gates": ["Operator review of package completeness"],
            "missing_information_questions": [],
        }
    )
    sections, items = build_checklist_sections_from_evidence(
        opportunity=opportunity,
        profile=profile,
        evidence_binder=binder,
        application_plan=plan,
        nofo_intelligence=intel or {},
        eligibility_evidence=eligibility,
    )
    contract = build_application_checklist_execution_contract(
        pursuit_workspace_id=ws["pursuit_workspace_id"],
        opportunity_id=oid,
        organization_profile_id=pid,
        checklist_sections=sections,
        checklist_items=items,
        evidence_binder_reference=binder.get("binder_id"),
        eligibility_evidence_reference=ws.get("eligibility_evidence_reference"),
        nofo_intelligence_reference=ws.get("nofo_intelligence_reference"),
    )
    questionnaire = build_missing_information_questionnaire(
        checklist_items=items,
        opportunity_id=oid,
        organization_profile_id=pid,
        evidence_binder_reference=binder.get("binder_id"),
    )
    status_counts: dict[str, int] = {}
    for item in items:
        s = str(item.get("item_status"))
        status_counts[s] = status_counts.get(s, 0) + 1
    incomplete = [i for i in items if i.get("item_status") not in {"complete"}]
    return _json_safe(
        {
            "application_workspace": contract,
            "questionnaire": questionnaire,
            "pursuit_workspace_id": ws["pursuit_workspace_id"],
            "opportunity_id": oid,
            "organization_profile_id": pid,
            "opportunity_source_layer": ws.get("opportunity_source_layer"),
            "item_status_counts": status_counts,
            "incomplete_item_count": len(incomplete),
            "question_count": questionnaire.get("question_count"),
            "what_nativeforge_knows": [
                "Checklist sections derived from binder + plan + intelligence",
                "Missing-information questions from checklist gaps only",
                "Unsupported proposal/PDF/submit capabilities labeled explicitly",
            ],
            "what_customer_must_provide": questionnaire.get("customer_next_actions")
            or [],
            "what_requires_human_review": [
                i["label"]
                for i in items
                if i.get("required_human_review")
                and i.get("item_status") != "not_supported"
            ][:8],
            "why_submission_not_allowed": contract.get("why_submission_not_allowed"),
            "unsupported_claims": [
                i["label"]
                for i in items
                if i.get("unsupported_claim_guard")
                or i.get("item_status") == "not_supported"
            ],
            "submission_allowed": False,
            "proposal_drafting_claimed": False,
            "application_complete_claimed": False,
        }
    )


def build_application_plan_workspace_demo_surface(
    *,
    max_profiles: int = 2,
) -> dict[str, Any]:
    profiles = load_sc_tribal_profiles()[:max_profiles]
    grants_by_id = {
        str(g.get("grant_id") or g.get("opportunity_id")): g
        for g in grants_from_pack(load_sc_curated_opportunity_pack())
    }
    intel_pack = load_selected_intelligence_pack(require_file=False)
    intel_by_id = {
        o["opportunity_id"]: o for o in (intel_pack.get("opportunities") or [])
    }
    workspaces: list[dict[str, Any]] = []
    for oid in SHOWCASE_OPPORTUNITY_IDS:
        opp = grants_by_id.get(oid)
        if not opp:
            continue
        for profile in profiles:
            workspaces.append(
                build_application_plan_workspace_for_pair(
                    profile, opp, nofo_intelligence=intel_by_id.get(oid)
                )
            )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 4,
            "title": "Application checklist / package build plan",
            "workspace_count": len(workspaces),
            "showcase_opportunity_ids": list(SHOWCASE_OPPORTUNITY_IDS),
            "submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "application_complete_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "workspaces": workspaces,
            "buyer_summary": [
                "Here is the package we need to assemble for selected opportunities",
                "Checklist shows what NativeForge already knows vs what is missing",
                "Missing-information questions are evidence-backed — no invented answers",
                "Submission is not allowed; proposal drafting remains unsupported",
            ],
        }
    )


def application_plan_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "submission_allowed",
        "submission_ready_claimed",
        "proposal_drafting_claimed",
        "application_complete_claimed",
        "nofo_pdf_extraction_claimed",
        "live_ingest_claimed",
        "scoring_math_changed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    layers: set[str] = set()
    for item in surface.get("workspaces") or []:
        aw = item.get("application_workspace") or {}
        fails.extend(checklist_execution_invariant_failures(aw))
        fails.extend(questionnaire_invariant_failures(item.get("questionnaire") or {}))
        layers.add(str(item.get("opportunity_source_layer")))
        if item.get("submission_allowed") is True:
            fails.append("ws_submission_allowed")
        if item.get("proposal_drafting_claimed") is True:
            fails.append("ws_proposal_claimed")
        if item.get("application_complete_claimed") is True:
            fails.append("ws_complete_claimed")
        if not (item.get("why_submission_not_allowed")):
            fails.append("missing_why_submission_blocked")
    if "sc_state" not in layers or "federal" not in layers:
        fails.append("need_sc_and_federal_workspaces")
    return fails
