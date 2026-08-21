"""Operator review trail aggregator (Block 36)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.rbac_enforcement_service import run_rbac_enforcement_suite
from nativeforge.services.unified_audit_event_service import build_unified_audit_event

SCHEMA_VERSION = "nf_operator_review_trail_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_operator_review_trail() -> dict[str, Any]:
    suite = run_rbac_enforcement_suite()
    denial_samples = [
        build_unified_audit_event(
            event_type="rbac_deny",
            actor_type="customer",
            actor_id="fixture_customer_demo",
            organization_profile_id="org_demo_sc",
            object_type="package_workspace",
            object_id="pkg_demo",
            action="submit",
            decision="deny",
            reason="action_hard_denied:submit",
        ),
        build_unified_audit_event(
            event_type="cross_org_access_denied",
            actor_type="customer",
            actor_id="fixture_customer_demo",
            organization_profile_id="org_a_demo",
            object_type="evidence_intake",
            object_id="ev_other",
            action="view",
            decision="deny",
            reason="cross_org_access_denied",
        ),
    ]
    queue = [
        {
            "item_id": "ort_evidence_pending",
            "category": "pending_evidence_reviews",
            "severity": "medium",
            "owner_action_role": "operator_reviewer",
            "next_safe_action": "Review uploaded evidence packets before unlock",
            "customer_impact": "Draft may remain limited until reviewed",
            "pilot_readiness_impact": "blocks controlled pilot GO",
        },
        {
            "item_id": "ort_authority_pending",
            "category": "pending_authority_reviews",
            "severity": "high",
            "owner_action_role": "operator_reviewer",
            "next_safe_action": "Manual authority evidence review (no live SAM/AOR)",
            "customer_impact": "Submit authority remains false",
            "pilot_readiness_impact": "blocks controlled pilot GO",
        },
        {
            "item_id": "ort_rbac_denials",
            "category": "rbac_denials",
            "severity": "low",
            "owner_action_role": "operator_admin",
            "next_safe_action": "Monitor denial audit stream; no override without role",
            "customer_impact": "Sensitive actions remain blocked",
            "pilot_readiness_impact": "expected; not a GO unlock",
            "sample_events": denial_samples,
        },
        {
            "item_id": "ort_package_blockers",
            "category": "package_blockers",
            "severity": "medium",
            "owner_action_role": "grant_manager",
            "next_safe_action": "Resolve checklist gaps; keep export as preview only",
            "customer_impact": "Final export denied",
            "pilot_readiness_impact": "blocks submission path",
        },
        {
            "item_id": "ort_qa_blockers",
            "category": "qa_blockers",
            "severity": "medium",
            "owner_action_role": "operator_reviewer",
            "next_safe_action": "Keep AI governance hard gates on",
            "customer_impact": "Unsupported claims blocked",
            "pilot_readiness_impact": "required for trust",
        },
        {
            "item_id": "ort_feedback",
            "category": "feedback_reports",
            "severity": "low",
            "owner_action_role": "operator_admin",
            "next_safe_action": "Triage customer feedback hooks",
            "customer_impact": "Reporting available in demo",
            "pilot_readiness_impact": "informational",
        },
        {
            "item_id": "ort_storage",
            "category": "storage_decision_blockers",
            "severity": "critical",
            "owner_action_role": "owner",
            "next_safe_action": "Owner decision on production storage backend",
            "customer_impact": "Customer uploads not durable in production",
            "pilot_readiness_impact": "blocks controlled pilot GO",
        },
        {
            "item_id": "ort_source",
            "category": "source_validation_blockers",
            "severity": "medium",
            "owner_action_role": "operator_admin",
            "next_safe_action": "Keep non-SC Top-15 packeted, not live",
            "customer_impact": "National coverage model only",
            "pilot_readiness_impact": "limits multi-state pilot claims",
        },
        {
            "item_id": "ort_pilot",
            "category": "controlled_pilot_blockers",
            "severity": "critical",
            "owner_action_role": "owner",
            "next_safe_action": "Complete auth live path + storage + pen-test/SCA",
            "customer_impact": "Invites not issued",
            "pilot_readiness_impact": "NO_GO",
        },
        {
            "item_id": "ort_prod",
            "category": "production_rollout_blockers",
            "severity": "critical",
            "owner_action_role": "owner",
            "next_safe_action": "Do not claim production rollout",
            "customer_impact": "Production rollout NO_GO",
            "pilot_readiness_impact": "NO_GO",
        },
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operator_queue": queue,
            "queue_count": len(queue),
            "rbac_enforcement_suite_status": suite.get("overall_status"),
            "rbac_denial_samples": denial_samples,
            "stale_unreviewed_items": [
                "pending_authority_reviews",
                "storage_decision_blockers",
            ],
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "human_review_required": True,
        }
    )


def operator_review_trail_invariant_failures(trail: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if trail.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if trail.get("production_rollout_status") == "GO":
        fails.append("prod_go")
    if not (trail.get("operator_queue") or []):
        fails.append("empty_queue")
    cats = {i.get("category") for i in trail.get("operator_queue") or []}
    for required in (
        "rbac_denials",
        "storage_decision_blockers",
        "controlled_pilot_blockers",
    ):
        if required not in cats:
            fails.append(f"missing:{required}")
    return fails
