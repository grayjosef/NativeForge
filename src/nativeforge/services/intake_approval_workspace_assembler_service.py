"""Assemble intake + approval workspace for showcase opportunities (Block 05)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_plan_workspace_assembler_service import (
    build_application_plan_workspace_for_pair,
)
from nativeforge.services.attachment_form_intake_planner_service import (
    intake_plan_invariant_failures,
    plan_intake_from_gaps,
)
from nativeforge.services.human_approval_workflow_service import (
    approval_workflow_invariant_failures,
    build_human_approval_workflow,
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

SCHEMA_VERSION = "nf_intake_approval_workspace_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_intake_approval_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_ws = build_application_plan_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    # Binder from pursuit packet (plan_ws does not embed full binder)
    pursuit_packet = build_pursuit_workspace_for_pair(
        profile, opportunity, nofo_intelligence=nofo_intelligence
    )
    aw = plan_ws["application_workspace"]
    pursuit_id = plan_ws["pursuit_workspace_id"]
    intake_plan = plan_intake_from_gaps(
        application_workspace=aw,
        pursuit_workspace_id=pursuit_id,
        evidence_binder=pursuit_packet.get("evidence_binder") or {},
        questionnaire=plan_ws.get("questionnaire") or {},
    )
    approvals = build_human_approval_workflow(
        intake_plan=intake_plan,
        application_workspace_id=aw["application_workspace_id"],
        pursuit_workspace_id=pursuit_id,
    )
    return _json_safe(
        {
            "application_workspace_id": aw["application_workspace_id"],
            "pursuit_workspace_id": pursuit_id,
            "opportunity_id": plan_ws["opportunity_id"],
            "organization_profile_id": plan_ws["organization_profile_id"],
            "opportunity_source_layer": plan_ws.get("opportunity_source_layer"),
            "intake_plan": intake_plan,
            "approval_workflow": approvals,
            "intake_item_count": intake_plan.get("intake_item_count"),
            "approval_count": approvals.get("approval_count"),
            "open_approval_count": approvals.get("open_approval_count"),
            "customer_must_provide": intake_plan.get("customer_must_provide") or [],
            "operator_must_verify": intake_plan.get("operator_must_verify") or [],
            "required_reviewer_roles": sorted(
                {
                    a.get("required_reviewer_role")
                    for a in (approvals.get("approvals") or [])
                    if a.get("required_reviewer_role")
                }
            ),
            "what_remains_blocked": approvals.get("package_blocked_reasons") or [],
            "why_package_not_ready": (
                "Intake gaps and human approvals remain open; "
                "binary upload and approval persistence are not implemented; "
                "submission is not allowed."
            ),
            "binary_upload_persistence_supported": False,
            "binary_upload_persistence_claimed": False,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "package_readiness_unlocked": False,
        }
    )


def build_intake_approval_demo_surface(*, max_profiles: int = 2) -> dict[str, Any]:
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
                build_intake_approval_workspace_for_pair(
                    profile, opp, nofo_intelligence=intel_by_id.get(oid)
                )
            )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 5,
            "title": "Intake & approvals / package gaps",
            "workspace_count": len(workspaces),
            "showcase_opportunity_ids": list(SHOWCASE_OPPORTUNITY_IDS),
            "binary_upload_persistence_supported": False,
            "binary_upload_persistence_claimed": False,
            "approval_persistence_supported": False,
            "approval_persistence_claimed": False,
            "submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "package_readiness_unlocked": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "workspaces": workspaces,
            "buyer_summary": [
                "Here are the files, confirmations, and approvals needed to close package gaps",
                "Intake requests are planned from checklist and binder gaps — specific, not vague",
                "Binary upload and approval persistence are not claimed in this layer",
                "Package readiness and submission remain locked until evidence + human review",
            ],
        }
    )


def intake_approval_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "binary_upload_persistence_claimed",
        "binary_upload_persistence_supported",
        "approval_persistence_claimed",
        "approval_persistence_supported",
        "submission_allowed",
        "submission_ready_claimed",
        "proposal_drafting_claimed",
        "package_readiness_unlocked",
        "live_ingest_claimed",
        "scoring_math_changed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    layers: set[str] = set()
    for item in surface.get("workspaces") or []:
        fails.extend(intake_plan_invariant_failures(item.get("intake_plan") or {}))
        fails.extend(
            approval_workflow_invariant_failures(item.get("approval_workflow") or {})
        )
        layers.add(str(item.get("opportunity_source_layer")))
        if item.get("submission_ready_claimed") is True:
            fails.append("ws_submission_ready")
        if item.get("binary_upload_persistence_claimed") is True:
            fails.append("ws_upload_claimed")
        if item.get("approval_persistence_claimed") is True:
            fails.append("ws_approval_persist_claimed")
        if item.get("package_readiness_unlocked") is True:
            fails.append("ws_package_unlocked")
        if not item.get("why_package_not_ready"):
            fails.append("missing_why_not_ready")
    if "sc_state" not in layers or "federal" not in layers:
        fails.append("need_sc_and_federal_workspaces")
    return fails
