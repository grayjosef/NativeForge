"""Bridge SC Monday demo artifact → frontend static JSON (read-only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.applicant_authority_assembler_service import (
    applicant_authority_demo_surface_invariant_failures,
    build_applicant_authority_demo_surface,
)
from nativeforge.services.application_plan_workspace_assembler_service import (
    application_plan_demo_surface_invariant_failures,
    build_application_plan_workspace_demo_surface,
)
from nativeforge.services.audit_operator_storage_assembler_service import (
    audit_operator_storage_demo_surface_invariant_failures,
    build_audit_operator_storage_demo_surface,
)
from nativeforge.services.buyer_demo_flow_contract_service import (
    build_buyer_demo_flow_contract,
    buyer_flow_contract_invariant_failures,
)
from nativeforge.services.collaboration_dark_launch_assembler_service import (
    build_collaboration_dark_launch_demo_surface,
    collaboration_dark_launch_demo_surface_invariant_failures,
)
from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
    controlled_drafting_demo_surface_invariant_failures,
)
from nativeforge.services.customer_pilot_auth_assembler_service import (
    build_customer_pilot_auth_demo_surface,
    customer_pilot_auth_demo_surface_invariant_failures,
)
from nativeforge.services.draft_workspace_assembler_service import (
    build_draft_workspace_demo_surface,
    draft_workspace_demo_surface_invariant_failures,
)
from nativeforge.services.evidence_intake_assembler_service import (
    build_evidence_intake_demo_surface,
    evidence_intake_demo_surface_invariant_failures,
)
from nativeforge.services.evidence_lifecycle_assembler_service import (
    build_evidence_lifecycle_demo_surface,
    evidence_lifecycle_demo_surface_invariant_failures,
)
from nativeforge.services.feedback_loop_assembler_service import (
    build_feedback_loop_demo_surface,
    feedback_loop_demo_surface_invariant_failures,
)
from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
    forms_attachments_demo_surface_invariant_failures,
)
from nativeforge.services.gate10_closeout_assembler_service import (
    build_gate10_closeout_demo_surface,
    gate10_closeout_demo_surface_invariant_failures,
)
from nativeforge.services.gate13_pentest_pilot_assembler_service import (
    build_gate13_pentest_pilot_demo_surface,
    gate13_pentest_pilot_demo_surface_invariant_failures,
)
from nativeforge.services.intake_approval_workspace_assembler_service import (
    build_intake_approval_demo_surface,
    intake_approval_demo_surface_invariant_failures,
)
from nativeforge.services.live_authority_spike_assembler_service import (
    build_live_authority_spike_demo_surface,
    live_authority_spike_demo_surface_invariant_failures,
)
from nativeforge.services.multi_org_pilot_assembler_service import (
    build_multi_org_pilot_demo_surface,
    multi_org_pilot_demo_surface_invariant_failures,
)
from nativeforge.services.narrative_budget_scaffold_assembler_service import (
    build_narrative_budget_demo_surface,
    narrative_budget_demo_surface_invariant_failures,
)
from nativeforge.services.national_coverage_assembler_service import (
    build_national_coverage_demo_surface,
    national_coverage_demo_surface_invariant_failures,
)
from nativeforge.services.nofo_extraction_pilot_assembler_service import (
    build_nofo_extraction_demo_surface,
    nofo_extraction_demo_surface_invariant_failures,
)
from nativeforge.services.nofo_showcase_demo_surface_service import (
    build_nofo_showcase_demo_surface,
    nofo_showcase_surface_invariant_failures,
)
from nativeforge.services.operator_readiness_assembler_service import (
    build_operator_readiness_demo_surface,
    operator_readiness_demo_surface_invariant_failures,
)
from nativeforge.services.opportunity_engine_product_surface_service import (
    build_opportunity_engine_product_surface,
    opportunity_engine_surface_invariant_failures,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
    organization_evidence_demo_surface_invariant_failures,
)
from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
    package_export_preview_demo_surface_invariant_failures,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
    package_readiness_demo_surface_invariant_failures,
)
from nativeforge.services.persistence_approval_assembler_service import (
    build_persistence_approval_demo_surface,
    persistence_approval_demo_surface_invariant_failures,
)
from nativeforge.services.production_enforcement_assembler_service import (
    build_production_enforcement_demo_surface,
    production_enforcement_demo_surface_invariant_failures,
)
from nativeforge.services.proposal_qa_gate_service import (
    ai_governance_demo_surface_invariant_failures,
    build_ai_governance_demo_surface,
)
from nativeforge.services.pursuit_workspace_assembler_service import (
    build_pursuit_workspace_demo_surface,
    pursuit_demo_surface_invariant_failures,
)
from nativeforge.services.rbac_enforcement_assembler_service import (
    build_rbac_enforcement_demo_surface,
    rbac_enforcement_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_assembler_service import (
    build_sc_monday_demo_artifact,
    demo_artifact_invariant_failures,
)
from nativeforge.services.sca_security_loop_assembler_service import (
    build_sca_security_loop_demo_surface,
    sca_security_loop_demo_surface_invariant_failures,
)
from nativeforge.services.source_freshness_pilot_checker_service import (
    build_source_freshness_demo_surface,
    source_freshness_demo_surface_invariant_failures,
)
from nativeforge.services.top15_source_validation_assembler_service import (
    build_top15_source_validation_demo_surface,
    top15_source_validation_demo_surface_invariant_failures,
)

SCHEMA_VERSION = "nf_sc_monday_browser_demo_bridge_v1"
DEFAULT_FRONTEND_JSON = Path("frontend/src/demo/sc_customer_demo.json")
DEMO_ROUTE_PATH = "/?view=sc_customer_demo"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_sc_customer_demo_bridge_payload(
    *,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    art = artifact if artifact is not None else build_sc_monday_demo_artifact()
    fails = demo_artifact_invariant_failures(art)
    if fails:
        raise ValueError(f"SC Monday demo artifact invariants failed: {fails}")

    # Cap rows for static UI payload size while keeping both geographies.
    rows = list(art.get("rows") or [])
    sc = [r for r in rows if r.get("funding_geography") == "south_carolina"]
    fed = [r for r in rows if r.get("funding_geography") == "federal"]
    sample = sc[:40] + fed[:80]
    if len(sample) < 20:
        sample = rows[:120]

    nofo_surface = build_nofo_showcase_demo_surface(write_fixtures=False)
    nofo_fails = nofo_showcase_surface_invariant_failures(nofo_surface)
    if nofo_fails:
        raise ValueError(f"NOFO showcase surface invariants failed: {nofo_fails}")

    buyer_flow = build_buyer_demo_flow_contract()
    buyer_fails = buyer_flow_contract_invariant_failures(buyer_flow)
    if buyer_fails:
        raise ValueError(f"Buyer demo flow contract invariants failed: {buyer_fails}")

    engine_surface = build_opportunity_engine_product_surface(write_config=True)
    engine_fails = opportunity_engine_surface_invariant_failures(engine_surface)
    if engine_fails:
        raise ValueError(
            f"Opportunity engine surface invariants failed: {engine_fails}"
        )

    pursuit_surface = build_pursuit_workspace_demo_surface()
    pursuit_fails = pursuit_demo_surface_invariant_failures(pursuit_surface)
    if pursuit_fails:
        raise ValueError(
            f"Pursuit workspace surface invariants failed: {pursuit_fails}"
        )

    plan_surface = build_application_plan_workspace_demo_surface()
    plan_fails = application_plan_demo_surface_invariant_failures(plan_surface)
    if plan_fails:
        raise ValueError(
            f"Application plan workspace surface invariants failed: {plan_fails}"
        )

    intake_surface = build_intake_approval_demo_surface()
    intake_fails = intake_approval_demo_surface_invariant_failures(intake_surface)
    if intake_fails:
        raise ValueError(
            f"Intake approval workspace surface invariants failed: {intake_fails}"
        )

    narrative_surface = build_narrative_budget_demo_surface()
    narrative_fails = narrative_budget_demo_surface_invariant_failures(
        narrative_surface
    )
    if narrative_fails:
        raise ValueError(
            f"Narrative budget scaffold surface invariants failed: {narrative_fails}"
        )

    readiness_surface = build_package_readiness_demo_surface()
    readiness_fails = package_readiness_demo_surface_invariant_failures(
        readiness_surface
    )
    if readiness_fails:
        raise ValueError(
            f"Package readiness queue surface invariants failed: {readiness_fails}"
        )

    org_memory_surface = build_organization_evidence_demo_surface()
    org_memory_fails = organization_evidence_demo_surface_invariant_failures(
        org_memory_surface
    )
    if org_memory_fails:
        raise ValueError(
            f"Organization evidence memory surface invariants failed: {org_memory_fails}"
        )

    nofo_extraction_surface = build_nofo_extraction_demo_surface()
    nofo_extraction_fails = nofo_extraction_demo_surface_invariant_failures(
        nofo_extraction_surface
    )
    if nofo_extraction_fails:
        raise ValueError(
            f"NOFO extraction pilot surface invariants failed: {nofo_extraction_fails}"
        )

    freshness_surface = build_source_freshness_demo_surface()
    freshness_fails = source_freshness_demo_surface_invariant_failures(
        freshness_surface
    )
    if freshness_fails:
        raise ValueError(
            f"Source freshness pilot surface invariants failed: {freshness_fails}"
        )

    draft_ws_surface = build_draft_workspace_demo_surface()
    draft_ws_fails = draft_workspace_demo_surface_invariant_failures(draft_ws_surface)
    if draft_ws_fails:
        raise ValueError(f"Draft workspace surface invariants failed: {draft_ws_fails}")

    controlled_draft_surface = build_controlled_drafting_demo_surface()
    controlled_draft_fails = controlled_drafting_demo_surface_invariant_failures(
        controlled_draft_surface
    )
    if controlled_draft_fails:
        raise ValueError(
            f"Controlled drafting surface invariants failed: {controlled_draft_fails}"
        )

    ai_gov_surface = build_ai_governance_demo_surface()
    ai_gov_fails = ai_governance_demo_surface_invariant_failures(ai_gov_surface)
    if ai_gov_fails:
        raise ValueError(f"AI governance surface invariants failed: {ai_gov_fails}")

    feedback_surface = build_feedback_loop_demo_surface()
    feedback_fails = feedback_loop_demo_surface_invariant_failures(feedback_surface)
    if feedback_fails:
        raise ValueError(f"Feedback loop surface invariants failed: {feedback_fails}")

    export_preview_surface = build_package_export_preview_demo_surface()
    export_preview_fails = package_export_preview_demo_surface_invariant_failures(
        export_preview_surface
    )
    if export_preview_fails:
        raise ValueError(
            f"Package export preview surface invariants failed: {export_preview_fails}"
        )

    forms_map_surface = build_forms_attachments_demo_surface()
    forms_map_fails = forms_attachments_demo_surface_invariant_failures(
        forms_map_surface
    )
    if forms_map_fails:
        raise ValueError(
            f"Forms/attachments map surface invariants failed: {forms_map_fails}"
        )

    multi_org_surface = build_multi_org_pilot_demo_surface()
    multi_org_fails = multi_org_pilot_demo_surface_invariant_failures(multi_org_surface)
    if multi_org_fails:
        raise ValueError(
            f"Multi-org pilot surface invariants failed: {multi_org_fails}"
        )

    collab_dark_surface = build_collaboration_dark_launch_demo_surface()
    collab_dark_fails = collaboration_dark_launch_demo_surface_invariant_failures(
        collab_dark_surface
    )
    if collab_dark_fails:
        raise ValueError(
            f"Collaboration dark-launch surface invariants failed: {collab_dark_fails}"
        )

    evidence_intake_surface = build_evidence_intake_demo_surface()
    evidence_intake_fails = evidence_intake_demo_surface_invariant_failures(
        evidence_intake_surface
    )
    if evidence_intake_fails:
        raise ValueError(
            f"Evidence intake surface invariants failed: {evidence_intake_fails}"
        )

    operator_readiness_surface = build_operator_readiness_demo_surface()
    operator_readiness_fails = operator_readiness_demo_surface_invariant_failures(
        operator_readiness_surface
    )
    if operator_readiness_fails:
        raise ValueError(
            f"Operator readiness surface invariants failed: {operator_readiness_fails}"
        )

    persistence_approval_surface = build_persistence_approval_demo_surface()
    persistence_approval_fails = persistence_approval_demo_surface_invariant_failures(
        persistence_approval_surface
    )
    if persistence_approval_fails:
        raise ValueError(
            "Persistence approval surface invariants failed: "
            f"{persistence_approval_fails}"
        )

    customer_pilot_auth_surface = build_customer_pilot_auth_demo_surface()
    customer_pilot_auth_fails = customer_pilot_auth_demo_surface_invariant_failures(
        customer_pilot_auth_surface
    )
    if customer_pilot_auth_fails:
        raise ValueError(
            "Customer pilot auth surface invariants failed: "
            f"{customer_pilot_auth_fails}"
        )

    gate10_closeout_surface = build_gate10_closeout_demo_surface()
    gate10_closeout_fails = gate10_closeout_demo_surface_invariant_failures(
        gate10_closeout_surface
    )
    if gate10_closeout_fails:
        raise ValueError(
            f"Gate 10 closeout surface invariants failed: {gate10_closeout_fails}"
        )

    national_coverage_surface = build_national_coverage_demo_surface()
    national_coverage_fails = national_coverage_demo_surface_invariant_failures(
        national_coverage_surface
    )
    if national_coverage_fails:
        raise ValueError(
            f"National coverage surface invariants failed: {national_coverage_fails}"
        )

    applicant_authority_surface = build_applicant_authority_demo_surface()
    applicant_authority_fails = applicant_authority_demo_surface_invariant_failures(
        applicant_authority_surface
    )
    if applicant_authority_fails:
        raise ValueError(
            "Applicant authority surface invariants failed: "
            f"{applicant_authority_fails}"
        )

    evidence_lifecycle_surface = build_evidence_lifecycle_demo_surface()
    evidence_lifecycle_fails = evidence_lifecycle_demo_surface_invariant_failures(
        evidence_lifecycle_surface
    )
    if evidence_lifecycle_fails:
        raise ValueError(
            f"Evidence lifecycle surface invariants failed: {evidence_lifecycle_fails}"
        )

    top15_source_validation_surface = build_top15_source_validation_demo_surface()
    top15_source_validation_fails = (
        top15_source_validation_demo_surface_invariant_failures(
            top15_source_validation_surface
        )
    )
    if top15_source_validation_fails:
        raise ValueError(
            "Top-15 source validation surface invariants failed: "
            f"{top15_source_validation_fails}"
        )

    production_enforcement_surface = build_production_enforcement_demo_surface()
    production_enforcement_fails = (
        production_enforcement_demo_surface_invariant_failures(
            production_enforcement_surface
        )
    )
    if production_enforcement_fails:
        raise ValueError(
            "Production enforcement surface invariants failed: "
            f"{production_enforcement_fails}"
        )

    gate13_pentest_pilot_surface = build_gate13_pentest_pilot_demo_surface()
    gate13_pentest_pilot_fails = gate13_pentest_pilot_demo_surface_invariant_failures(
        gate13_pentest_pilot_surface
    )
    if gate13_pentest_pilot_fails:
        raise ValueError(
            "Gate 13 pentest/pilot surface invariants failed: "
            f"{gate13_pentest_pilot_fails}"
        )

    live_authority_spike_surface = build_live_authority_spike_demo_surface()
    live_authority_spike_fails = live_authority_spike_demo_surface_invariant_failures(
        live_authority_spike_surface
    )
    if live_authority_spike_fails:
        raise ValueError(
            "Live authority spike surface invariants failed: "
            f"{live_authority_spike_fails}"
        )

    sca_security_loop_surface = build_sca_security_loop_demo_surface(run_checks=False)
    sca_security_loop_fails = sca_security_loop_demo_surface_invariant_failures(
        sca_security_loop_surface
    )
    if sca_security_loop_fails:
        raise ValueError(
            f"SCA security loop surface invariants failed: {sca_security_loop_fails}"
        )

    rbac_enforcement_surface = build_rbac_enforcement_demo_surface()
    rbac_enforcement_fails = rbac_enforcement_demo_surface_invariant_failures(
        rbac_enforcement_surface
    )
    if rbac_enforcement_fails:
        raise ValueError(
            f"RBAC enforcement surface invariants failed: {rbac_enforcement_fails}"
        )

    audit_operator_storage_surface = build_audit_operator_storage_demo_surface()
    audit_operator_storage_fails = (
        audit_operator_storage_demo_surface_invariant_failures(
            audit_operator_storage_surface
        )
    )
    if audit_operator_storage_fails:
        raise ValueError(
            "Audit/operator/storage surface invariants failed: "
            f"{audit_operator_storage_fails}"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": art.get("title"),
            "demo_route_path": DEMO_ROUTE_PATH,
            "demo_dev_only": True,
            "offline_only": True,
            "read_only_advisory": True,
            "live_ingestion": False,
            "source_activation": False,
            "external_urls_used": False,
            "auth_required": False,
            "final_eligibility_claim_allowed": False,
            "pack_id": art.get("pack_id"),
            "capture_date": art.get("capture_date"),
            "content_digest": art.get("content_digest"),
            "claim_matrix": art.get("claim_matrix"),
            "profiles": art.get("profiles"),
            "opportunities": art.get("opportunities"),
            "classify_match": art.get("classify_match"),
            "combined_summary": art.get("combined_summary"),
            "missing_data_summary": art.get("missing_data_summary"),
            "provenance_evidence_summary": art.get("provenance_evidence_summary"),
            "what_nativeforge_did": art.get("what_nativeforge_did"),
            "what_requires_attention": art.get("what_requires_attention"),
            "why_this_matters": art.get("why_this_matters"),
            "workload_reduction_statement": art.get("workload_reduction_statement"),
            "next_actions": art.get("next_actions"),
            "rows": sample,
            "row_sample_note": (
                f"UI sample {len(sample)} of {len(rows)} profile×opportunity rows; "
                "full artifact available from assembler."
            ),
            "ui_flags": art.get("ui_flags"),
            "nofo_showcase": nofo_surface,
            "buyer_demo": buyer_flow,
            "opportunity_engine": engine_surface,
            "pursuit_workspace": pursuit_surface,
            "application_plan_workspace": plan_surface,
            "intake_approval_workspace": intake_surface,
            "narrative_budget_scaffold": narrative_surface,
            "package_readiness_queue": readiness_surface,
            "organization_evidence_memory": org_memory_surface,
            "nofo_extraction_pilot": nofo_extraction_surface,
            "source_freshness_pilot": freshness_surface,
            "draft_workspace": draft_ws_surface,
            "controlled_drafting": controlled_draft_surface,
            "ai_governance": ai_gov_surface,
            "feedback_loop": feedback_surface,
            "package_export_preview": export_preview_surface,
            "forms_attachments_map": forms_map_surface,
            "multi_org_pilot": multi_org_surface,
            "collaboration_dark_launch": collab_dark_surface,
            "evidence_intake": evidence_intake_surface,
            "operator_readiness": operator_readiness_surface,
            "persistence_approval_gate": persistence_approval_surface,
            "customer_pilot_auth": customer_pilot_auth_surface,
            "gate10_closeout": gate10_closeout_surface,
            "national_coverage": national_coverage_surface,
            "applicant_authority": applicant_authority_surface,
            "evidence_lifecycle": evidence_lifecycle_surface,
            "top15_source_validation": top15_source_validation_surface,
            "production_enforcement": production_enforcement_surface,
            "gate13_pentest_pilot": gate13_pentest_pilot_surface,
            "live_authority_spike": live_authority_spike_surface,
            "sca_security_loop": sca_security_loop_surface,
            "rbac_enforcement": rbac_enforcement_surface,
            "audit_operator_storage": audit_operator_storage_surface,
        }
    )


def write_sc_customer_demo_bridge_json(
    payload: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = payload if payload is not None else build_sc_customer_demo_bridge_payload()
    out = path or DEFAULT_FRONTEND_JSON
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def bridge_payload_invariant_failures(payload: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if payload.get("live_ingestion") is not False:
        fails.append("live_ingestion")
    if payload.get("source_activation") is not False:
        fails.append("source_activation")
    if payload.get("final_eligibility_claim_allowed") is not False:
        fails.append("final_claim")
    if not payload.get("rows"):
        fails.append("rows")
    opps = payload.get("opportunities") or {}
    if opps.get("south_carolina_count", 0) < 1:
        fails.append("sc_opps")
    if opps.get("federal_count", 0) < 1:
        fails.append("fed_opps")
    nofo = payload.get("nofo_showcase") or {}
    if not nofo:
        fails.append("nofo_showcase_missing")
    else:
        fails.extend(nofo_showcase_surface_invariant_failures(nofo))
    buyer = payload.get("buyer_demo") or {}
    if not buyer:
        fails.append("buyer_demo_missing")
    else:
        fails.extend(buyer_flow_contract_invariant_failures(buyer))
    engine = payload.get("opportunity_engine") or {}
    if not engine:
        fails.append("opportunity_engine_missing")
    else:
        fails.extend(opportunity_engine_surface_invariant_failures(engine))
    pursuit = payload.get("pursuit_workspace") or {}
    if not pursuit:
        fails.append("pursuit_workspace_missing")
    else:
        fails.extend(pursuit_demo_surface_invariant_failures(pursuit))
    plan = payload.get("application_plan_workspace") or {}
    if not plan:
        fails.append("application_plan_workspace_missing")
    else:
        fails.extend(application_plan_demo_surface_invariant_failures(plan))
    intake = payload.get("intake_approval_workspace") or {}
    if not intake:
        fails.append("intake_approval_workspace_missing")
    else:
        fails.extend(intake_approval_demo_surface_invariant_failures(intake))
    narrative = payload.get("narrative_budget_scaffold") or {}
    if not narrative:
        fails.append("narrative_budget_scaffold_missing")
    else:
        fails.extend(narrative_budget_demo_surface_invariant_failures(narrative))
    readiness = payload.get("package_readiness_queue") or {}
    if not readiness:
        fails.append("package_readiness_queue_missing")
    else:
        fails.extend(package_readiness_demo_surface_invariant_failures(readiness))
    org_memory = payload.get("organization_evidence_memory") or {}
    if not org_memory:
        fails.append("organization_evidence_memory_missing")
    else:
        fails.extend(organization_evidence_demo_surface_invariant_failures(org_memory))
    nofo_x = payload.get("nofo_extraction_pilot") or {}
    if not nofo_x:
        fails.append("nofo_extraction_pilot_missing")
    else:
        fails.extend(nofo_extraction_demo_surface_invariant_failures(nofo_x))
    freshness = payload.get("source_freshness_pilot") or {}
    if not freshness:
        fails.append("source_freshness_pilot_missing")
    else:
        fails.extend(source_freshness_demo_surface_invariant_failures(freshness))
    draft_ws = payload.get("draft_workspace") or {}
    if not draft_ws:
        fails.append("draft_workspace_missing")
    else:
        fails.extend(draft_workspace_demo_surface_invariant_failures(draft_ws))
    controlled = payload.get("controlled_drafting") or {}
    if not controlled:
        fails.append("controlled_drafting_missing")
    else:
        fails.extend(controlled_drafting_demo_surface_invariant_failures(controlled))
    ai_gov = payload.get("ai_governance") or {}
    if not ai_gov:
        fails.append("ai_governance_missing")
    else:
        fails.extend(ai_governance_demo_surface_invariant_failures(ai_gov))
    feedback = payload.get("feedback_loop") or {}
    if not feedback:
        fails.append("feedback_loop_missing")
    else:
        fails.extend(feedback_loop_demo_surface_invariant_failures(feedback))
    export_preview = payload.get("package_export_preview") or {}
    if not export_preview:
        fails.append("package_export_preview_missing")
    else:
        fails.extend(
            package_export_preview_demo_surface_invariant_failures(export_preview)
        )
    forms_map = payload.get("forms_attachments_map") or {}
    if not forms_map:
        fails.append("forms_attachments_map_missing")
    else:
        fails.extend(forms_attachments_demo_surface_invariant_failures(forms_map))
    multi_org = payload.get("multi_org_pilot") or {}
    if not multi_org:
        fails.append("multi_org_pilot_missing")
    else:
        fails.extend(multi_org_pilot_demo_surface_invariant_failures(multi_org))
    collab_dark = payload.get("collaboration_dark_launch") or {}
    if not collab_dark:
        fails.append("collaboration_dark_launch_missing")
    else:
        fails.extend(
            collaboration_dark_launch_demo_surface_invariant_failures(collab_dark)
        )
    evidence_intake = payload.get("evidence_intake") or {}
    if not evidence_intake:
        fails.append("evidence_intake_missing")
    else:
        fails.extend(evidence_intake_demo_surface_invariant_failures(evidence_intake))
    operator_readiness = payload.get("operator_readiness") or {}
    if not operator_readiness:
        fails.append("operator_readiness_missing")
    else:
        fails.extend(
            operator_readiness_demo_surface_invariant_failures(operator_readiness)
        )
    persistence_approval = payload.get("persistence_approval_gate") or {}
    if not persistence_approval:
        fails.append("persistence_approval_gate_missing")
    else:
        fails.extend(
            persistence_approval_demo_surface_invariant_failures(persistence_approval)
        )
    customer_pilot_auth = payload.get("customer_pilot_auth") or {}
    if not customer_pilot_auth:
        fails.append("customer_pilot_auth_missing")
    else:
        fails.extend(
            customer_pilot_auth_demo_surface_invariant_failures(customer_pilot_auth)
        )
    gate10_closeout = payload.get("gate10_closeout") or {}
    if not gate10_closeout:
        fails.append("gate10_closeout_missing")
    else:
        fails.extend(gate10_closeout_demo_surface_invariant_failures(gate10_closeout))
    national_coverage = payload.get("national_coverage") or {}
    if not national_coverage:
        fails.append("national_coverage_missing")
    else:
        fails.extend(
            national_coverage_demo_surface_invariant_failures(national_coverage)
        )
    applicant_authority = payload.get("applicant_authority") or {}
    if not applicant_authority:
        fails.append("applicant_authority_missing")
    else:
        fails.extend(
            applicant_authority_demo_surface_invariant_failures(applicant_authority)
        )
    evidence_lifecycle = payload.get("evidence_lifecycle") or {}
    if not evidence_lifecycle:
        fails.append("evidence_lifecycle_missing")
    else:
        fails.extend(
            evidence_lifecycle_demo_surface_invariant_failures(evidence_lifecycle)
        )
    top15_source_validation = payload.get("top15_source_validation") or {}
    if not top15_source_validation:
        fails.append("top15_source_validation_missing")
    else:
        fails.extend(
            top15_source_validation_demo_surface_invariant_failures(
                top15_source_validation
            )
        )
    production_enforcement = payload.get("production_enforcement") or {}
    if not production_enforcement:
        fails.append("production_enforcement_missing")
    else:
        fails.extend(
            production_enforcement_demo_surface_invariant_failures(
                production_enforcement
            )
        )
    gate13_pentest_pilot = payload.get("gate13_pentest_pilot") or {}
    if not gate13_pentest_pilot:
        fails.append("gate13_pentest_pilot_missing")
    else:
        fails.extend(
            gate13_pentest_pilot_demo_surface_invariant_failures(gate13_pentest_pilot)
        )
    live_authority_spike = payload.get("live_authority_spike") or {}
    if not live_authority_spike:
        fails.append("live_authority_spike_missing")
    else:
        fails.extend(
            live_authority_spike_demo_surface_invariant_failures(live_authority_spike)
        )
    sca_security_loop = payload.get("sca_security_loop") or {}
    if not sca_security_loop:
        fails.append("sca_security_loop_missing")
    else:
        fails.extend(
            sca_security_loop_demo_surface_invariant_failures(sca_security_loop)
        )
    rbac_enforcement = payload.get("rbac_enforcement") or {}
    if not rbac_enforcement:
        fails.append("rbac_enforcement_missing")
    else:
        fails.extend(rbac_enforcement_demo_surface_invariant_failures(rbac_enforcement))
    audit_operator_storage = payload.get("audit_operator_storage") or {}
    if not audit_operator_storage:
        fails.append("audit_operator_storage_missing")
    else:
        fails.extend(
            audit_operator_storage_demo_surface_invariant_failures(
                audit_operator_storage
            )
        )
    return fails
