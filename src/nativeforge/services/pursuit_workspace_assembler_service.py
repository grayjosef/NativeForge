"""Assemble pursuit workspaces for showcase SC + federal opportunities."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.application_package_evidence_binder_service import (
    build_application_package_evidence_binder,
    evidence_binder_invariant_failures,
)
from nativeforge.services.eligibility_handoff_service import (
    build_eligibility_handoff_for_pair,
)
from nativeforge.services.nofo_showcase_application_plan_service import (
    build_application_plan_skeleton,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    load_selected_intelligence_pack,
)
from nativeforge.services.pursuit_readiness_next_action_service import (
    build_readiness_packet,
    readiness_packet_invariant_failures,
)
from nativeforge.services.pursuit_workspace_contract_service import (
    build_pursuit_workspace_contract,
    pursuit_workspace_invariant_failures,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_pursuit_workspace_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pursuit_workspace_for_pair(
    profile: dict[str, Any],
    opportunity: dict[str, Any],
    *,
    nofo_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    oid = str(opportunity.get("opportunity_id") or opportunity.get("grant_id"))
    pid = str(profile.get("fixture_key") or profile.get("profile_fixture_key"))
    handoff = build_eligibility_handoff_for_pair(profile, opportunity)
    eligibility = handoff.get("eligibility_evidence") or {}
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
            "application_checklist": [],
            "narrative_section_scaffold": [],
            "missing_information_questions": [],
            "why_worth_review": "Worth human review; intelligence pack missing",
        }
    )
    binder = build_application_package_evidence_binder(
        opportunity=opportunity,
        profile=profile,
        eligibility_evidence=eligibility,
        nofo_intelligence=intel or {},
        application_plan=plan,
    )
    readiness = build_readiness_packet(binder=binder, eligibility_evidence=eligibility)
    missing_summary = sorted(
        {
            f
            for item in [
                i
                for sec in (binder.get("sections") or {}).values()
                for i in (sec or [])
            ]
            for f in (item.get("missing_fields") or [])
        }
    )
    ws = build_pursuit_workspace_contract(
        opportunity_id=oid,
        organization_profile_id=pid,
        opportunity_source_layer=str(
            opportunity.get("source_layer")
            or (
                "sc_state"
                if opportunity.get("funding_geography") == "south_carolina"
                else "federal"
            )
        ),
        eligibility_evidence_reference=f"eligibility:{oid}:{pid}",
        nofo_intelligence_reference=f"nofo:{oid}",
        application_plan_reference=f"plan:{oid}",
        evidence_binder_reference=binder.get("binder_id"),
        pursuit_status="under_review",
        readiness_status=readiness.get("readiness_status") or "not_submission_ready",
        missing_information_summary=missing_summary,
        operator_next_actions=readiness.get("operator_next_actions"),
        customer_next_actions=readiness.get("customer_next_actions"),
        why_worth_review=plan.get("why_worth_review"),
    )
    # Force not_submission_ready label for demo honesty even if ready_for_review
    ws["not_submission_ready_label"] = True
    ws["what_nativeforge_prebuilt"] = [
        "Pursuit workspace shell",
        "Eligibility evidence linkage",
        "NOFO/synopsis intelligence linkage (curated)",
        "Application-plan skeleton checklist",
        "Evidence binder with honesty statuses",
        "Deterministic next actions",
    ]
    ws["what_customer_must_provide"] = [
        "Verified organization facts only when available",
        "Human confirmation of active round and eligibility language",
        "Official attachments/forms when located",
        "Human-approved resolution/budget inputs if required — never invent",
    ]
    return _json_safe(
        {
            "workspace": ws,
            "evidence_binder": binder,
            "readiness": readiness,
            "eligibility_evidence": eligibility,
            "application_plan_summary": {
                "recommendation_label": plan.get("recommendation_label"),
                "checklist_count": len(plan.get("application_checklist") or []),
                "missing_question_count": len(
                    plan.get("missing_information_questions") or []
                ),
                "proposal_drafting_claimed": False,
            },
            "nofo_intelligence_present": bool(intel),
        }
    )


def build_pursuit_workspace_demo_surface(
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
        # Prefer one federal and one state_only profile when available
        for profile in profiles:
            workspaces.append(
                build_pursuit_workspace_for_pair(
                    profile, opp, nofo_intelligence=intel_by_id.get(oid)
                )
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 3,
            "title": "Pursuit workspace + application-package evidence binder",
            "workspace_count": len(workspaces),
            "showcase_opportunity_ids": list(SHOWCASE_OPPORTUNITY_IDS),
            "final_submission_allowed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "scoring_math_changed": False,
            "workspaces": workspaces,
            "buyer_summary": [
                "After you pick an opportunity, NativeForge opens a pursuit workspace",
                "Evidence binder groups known vs missing package items honestly",
                "Readiness is never submission-ready without complete evidence + human review",
                "Proposal drafting and auto-submit are not supported",
            ],
        }
    )


def pursuit_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("final_submission_allowed") is True:
        fails.append("final_submission_allowed")
    if surface.get("submission_ready_claimed") is True:
        fails.append("submission_ready_claimed")
    if surface.get("proposal_drafting_claimed") is True:
        fails.append("proposal_drafting_claimed")
    if surface.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if surface.get("scoring_math_changed") is True:
        fails.append("scoring_math_changed")
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    layers = set()
    for item in surface.get("workspaces") or []:
        ws = item.get("workspace") or {}
        fails.extend(pursuit_workspace_invariant_failures(ws))
        fails.extend(
            evidence_binder_invariant_failures(item.get("evidence_binder") or {})
        )
        fails.extend(readiness_packet_invariant_failures(item.get("readiness") or {}))
        layers.add(ws.get("opportunity_source_layer"))
        if ws.get("final_submission_allowed") is True:
            fails.append("ws_submit_allowed")
        if (item.get("application_plan_summary") or {}).get(
            "proposal_drafting_claimed"
        ):
            fails.append("plan_proposal_claimed")
    if "sc_state" not in layers or "federal" not in layers:
        fails.append("need_sc_and_federal_workspaces")
    return fails
