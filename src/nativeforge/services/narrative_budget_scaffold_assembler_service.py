"""Assemble narrative + budget/match scaffold workspace (Campaign Block 06)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_plan_workspace_assembler_service import (
    build_application_plan_workspace_for_pair,
)
from nativeforge.services.budget_match_evidence_capture_service import (
    budget_match_invariant_failures,
    build_budget_match_evidence_capture,
)
from nativeforge.services.intake_approval_workspace_assembler_service import (
    build_intake_approval_workspace_for_pair,
)
from nativeforge.services.narrative_scaffold_builder_service import (
    build_narrative_scaffold_from_evidence,
)
from nativeforge.services.narrative_scaffold_contract_service import (
    narrative_scaffold_packet_invariant_failures,
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

SCHEMA_VERSION = "nf_narrative_budget_scaffold_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_narrative_budget_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_ws = build_application_plan_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    intake_ws = build_intake_approval_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    pursuit = build_pursuit_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    aw = plan_ws["application_workspace"]
    oid = plan_ws["opportunity_id"]
    pid = plan_ws["organization_profile_id"]
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
    plan = build_application_plan_skeleton(intel) if intel else {}
    scaffold = build_narrative_scaffold_from_evidence(
        application_workspace_id=aw["application_workspace_id"],
        pursuit_workspace_id=plan_ws["pursuit_workspace_id"],
        opportunity_id=oid,
        organization_profile_id=pid,
        source_layer=str(plan_ws.get("opportunity_source_layer") or ""),
        nofo_intelligence=intel or {},
        application_plan=plan,
        evidence_binder=pursuit.get("evidence_binder") or {},
        checklist_items=aw.get("checklist_items") or [],
        questionnaire=plan_ws.get("questionnaire") or {},
        intake_plan=intake_ws.get("intake_plan") or {},
    )
    budget = build_budget_match_evidence_capture(
        application_workspace_id=aw["application_workspace_id"],
        pursuit_workspace_id=plan_ws["pursuit_workspace_id"],
        opportunity_id=oid,
        nofo_intelligence=intel or {},
        evidence_binder=pursuit.get("evidence_binder") or {},
        checklist_items=aw.get("checklist_items") or [],
        intake_plan=intake_ws.get("intake_plan") or {},
    )
    return _json_safe(
        {
            "application_workspace_id": aw["application_workspace_id"],
            "pursuit_workspace_id": plan_ws["pursuit_workspace_id"],
            "opportunity_id": oid,
            "organization_profile_id": pid,
            "opportunity_source_layer": plan_ws.get("opportunity_source_layer"),
            "narrative_scaffold": scaffold,
            "budget_match_evidence": budget,
            "section_count": scaffold.get("section_count"),
            "customer_questions": scaffold.get("customer_questions") or [],
            "operator_checks": list(
                dict.fromkeys(
                    (scaffold.get("operator_checks") or [])
                    + (budget.get("operator_checks") or [])
                )
            ),
            "budget_customer_questions": budget.get("customer_questions") or [],
            "drafting_supported": False,
            "generated_prose_produced": False,
            "proposal_drafting_claimed": False,
            "budget_claimed_complete": False,
            "match_claimed_complete": False,
            "why_drafting_not_supported": (
                "Narrative scaffold provides section labels and evidence gaps only. "
                "NativeForge does not generate proposal prose or invent budget/match values."
            ),
        }
    )


def build_narrative_budget_demo_surface(*, max_profiles: int = 2) -> dict[str, Any]:
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
                build_narrative_budget_workspace_for_pair(
                    profile, opp, nofo_intelligence=intel_by_id.get(oid)
                )
            )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 6,
            "title": "Narrative & budget scaffold",
            "workspace_count": len(workspaces),
            "showcase_opportunity_ids": list(SHOWCASE_OPPORTUNITY_IDS),
            "drafting_supported": False,
            "generated_prose_produced": False,
            "proposal_drafting_claimed": False,
            "budget_claimed_complete": False,
            "match_claimed_complete": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "nofo_pdf_extraction_claimed": False,
            "workspaces": workspaces,
            "buyer_summary": [
                "Here are the narrative and budget areas this package must support",
                "Evidence available vs missing stays visible — no invented prose or amounts",
                "Budget and match/cost-share completeness are never claimed without evidence",
                "Proposal drafting is not supported in this layer",
            ],
        }
    )


def narrative_budget_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "drafting_supported",
        "generated_prose_produced",
        "proposal_drafting_claimed",
        "budget_claimed_complete",
        "match_claimed_complete",
        "live_ingest_claimed",
        "scoring_math_changed",
        "nofo_pdf_extraction_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    layers: set[str] = set()
    for item in surface.get("workspaces") or []:
        fails.extend(
            narrative_scaffold_packet_invariant_failures(
                item.get("narrative_scaffold") or {}
            )
        )
        fails.extend(
            budget_match_invariant_failures(item.get("budget_match_evidence") or {})
        )
        layers.add(str(item.get("opportunity_source_layer")))
        if item.get("generated_prose_produced") is True:
            fails.append("ws_prose")
        if item.get("budget_claimed_complete") is True:
            fails.append("ws_budget_complete")
        if item.get("match_claimed_complete") is True:
            fails.append("ws_match_complete")
        if not item.get("why_drafting_not_supported"):
            fails.append("missing_why_no_drafting")
    if "sc_state" not in layers or "federal" not in layers:
        fails.append("need_sc_and_federal_workspaces")
    return fails
