"""Assemble package readiness + operator review queue demo surface (Block 07)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_plan_workspace_assembler_service import (
    build_application_plan_workspace_for_pair,
)
from nativeforge.services.intake_approval_workspace_assembler_service import (
    build_intake_approval_workspace_for_pair,
)
from nativeforge.services.narrative_budget_scaffold_assembler_service import (
    build_narrative_budget_workspace_for_pair,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    load_selected_intelligence_pack,
)
from nativeforge.services.operator_review_queue_service import (
    build_operator_review_queue,
    review_queue_invariant_failures,
)
from nativeforge.services.package_readiness_aggregation_service import (
    aggregate_package_readiness,
    aggregation_invariant_failures,
)
from nativeforge.services.package_readiness_rollup_contract_service import (
    package_readiness_invariant_failures,
)
from nativeforge.services.pursuit_workspace_assembler_service import (
    build_pursuit_workspace_for_pair,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_package_readiness_queue_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_package_readiness_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Reuse Block 06 assembler which already chains plan/intake/pursuit/narrative/budget
    nb = build_narrative_budget_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
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
    readiness_packet = aggregate_package_readiness(
        application_workspace=aw,
        pursuit_workspace=pursuit.get("workspace"),
        evidence_binder=pursuit.get("evidence_binder"),
        eligibility_evidence=pursuit.get("eligibility_evidence"),
        intake_plan=intake_ws.get("intake_plan"),
        approval_workflow=intake_ws.get("approval_workflow"),
        narrative_scaffold=nb.get("narrative_scaffold"),
        budget_match_evidence=nb.get("budget_match_evidence"),
        questionnaire=plan_ws.get("questionnaire"),
        opportunity_source_layer=str(nb.get("opportunity_source_layer") or ""),
    )
    queue = build_operator_review_queue(
        readiness_packet=readiness_packet,
        application_workspace=aw,
        intake_plan=intake_ws.get("intake_plan"),
        approval_workflow=intake_ws.get("approval_workflow"),
        narrative_scaffold=nb.get("narrative_scaffold"),
        budget_match_evidence=nb.get("budget_match_evidence"),
    )
    rollup = readiness_packet["rollup"]
    return _json_safe(
        {
            "package_readiness": rollup,
            "per_layer": readiness_packet.get("per_layer"),
            "operator_review_queue": queue,
            "application_workspace_id": aw["application_workspace_id"],
            "pursuit_workspace_id": plan_ws["pursuit_workspace_id"],
            "opportunity_id": nb["opportunity_id"],
            "organization_profile_id": nb["organization_profile_id"],
            "opportunity_source_layer": nb.get("opportunity_source_layer"),
            "overall_readiness_status": rollup.get("overall_readiness_status"),
            "blocked_reasons": rollup.get("blocked_reasons") or [],
            "missing_information_count": rollup.get("missing_information_count"),
            "human_review_count": rollup.get("human_review_count"),
            "unsupported_capability_count": rollup.get("unsupported_capability_count"),
            "next_safest_action": rollup.get("next_safest_action"),
            "customer_next_actions": rollup.get("customer_next_actions") or [],
            "operator_next_actions": rollup.get("operator_next_actions") or [],
            "review_item_count": queue.get("review_item_count"),
            "critical_count": queue.get("critical_count"),
            "submission_ready_claimed": False,
            "final_eligibility_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "not_submission_ready_label": True,
        }
    )


def build_package_readiness_demo_surface(*, max_profiles: int = 2) -> dict[str, Any]:
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
                build_package_readiness_workspace_for_pair(
                    profile, opp, nofo_intelligence=intel_by_id.get(oid)
                )
            )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 7,
            "title": "Readiness & review queue",
            "workspace_count": len(workspaces),
            "showcase_opportunity_ids": list(SHOWCASE_OPPORTUNITY_IDS),
            "submission_ready_claimed": False,
            "final_eligibility_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "nofo_pdf_extraction_claimed": False,
            "scoring_math_changed": False,
            "not_submission_ready_label": True,
            "workspaces": workspaces,
            "buyer_summary": [
                "Here is the current package readiness across every workflow layer",
                "Blockers, missing information, and human-review priorities stay visible",
                "Unsupported capabilities remain explicit blockers — not hidden",
                "Next safest action is human review — not drafting or submission",
            ],
        }
    )


def package_readiness_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "submission_ready_claimed",
        "final_eligibility_claimed",
        "proposal_drafting_claimed",
        "live_ingest_claimed",
        "nofo_pdf_extraction_claimed",
        "scoring_math_changed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("not_submission_ready_label") is not True:
        fails.append("not_submission_ready_label")
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    layers: set[str] = set()
    for item in surface.get("workspaces") or []:
        fails.extend(
            package_readiness_invariant_failures(item.get("package_readiness") or {})
        )
        fails.extend(
            review_queue_invariant_failures(item.get("operator_review_queue") or {})
        )
        fails.extend(
            aggregation_invariant_failures(
                {
                    "rollup": item.get("package_readiness") or {},
                    "invariant_failures": [],
                }
            )
        )
        layers.add(str(item.get("opportunity_source_layer")))
        if item.get("submission_ready_claimed") is True:
            fails.append("ws_submission_ready")
        if item.get("final_eligibility_claimed") is True:
            fails.append("ws_final_eligibility")
        if not item.get("next_safest_action"):
            fails.append("missing_next_action")
        if (item.get("unsupported_capability_count") or 0) < 1:
            fails.append("unsupported_count_zero")
    if "sc_state" not in layers or "federal" not in layers:
        fails.append("need_sc_and_federal_workspaces")
    return fails
