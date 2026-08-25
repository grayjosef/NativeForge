"""Block 36 assembler: audit trail + operator review + storage decision."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.operator_review_trail_service import (
    build_operator_review_trail,
    operator_review_trail_invariant_failures,
)
from nativeforge.services.production_storage_owner_decision_service import (
    build_production_storage_owner_decision_path,
    production_storage_owner_decision_invariant_failures,
)
from nativeforge.services.unified_audit_event_service import (
    EVENT_TYPES,
    build_unified_audit_event,
    unified_audit_event_invariant_failures,
)

SCHEMA_VERSION = "nf_audit_operator_storage_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_audit_operator_storage_demo_surface() -> dict[str, Any]:
    trail = build_operator_review_trail()
    storage = build_production_storage_owner_decision_path()
    sample_events = [
        build_unified_audit_event(
            event_type="auth_context_resolved",
            actor_type="system",
            actor_id="auth_resolver",
            organization_profile_id="org_demo_sc",
            action="resolve",
            decision="fixture_internal",
            reason="fixture auth context",
        ),
        build_unified_audit_event(
            event_type="storage_claim_evaluated",
            actor_type="operator",
            actor_id="owner",
            action="evaluate",
            decision="deny_claim",
            reason="production storage not configured",
            sensitive_payload={"api_key": "should_redact", "note": "ok"},
        ),
        *(trail.get("rbac_denial_samples") or []),
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 36,
            "title": "Audit trail + operator review + production storage decision",
            "audit_event_types": sorted(EVENT_TYPES),
            "sample_audit_events": sample_events,
            "sensitive_fields_redacted": True,
            "operator_review_trail": trail,
            "operator_queue_count": trail.get("queue_count"),
            "rbac_denial_aggregation": True,
            "production_storage_decision": storage,
            "owner_approval_needed": True,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "pilot_blocker_matrix": [
                "login_not_live",
                "production_storage_not_configured",
                "customer_data_policy_not_validated",
                "pen_test_not_passed",
                "full_sca_not_passed",
                "live_authority_not_verified",
            ],
            "production_blocker_matrix": [
                "production_auth_incomplete",
                "production_multi_tenant_incomplete",
                "production_storage_not_validated",
                "pen_test_not_passed",
                "incident_response_not_validated",
            ],
            "buyer_summary": [
                "Unified audit event contract covers RBAC denials and storage claims",
                "Operator review trail aggregates evidence, authority, QA, and pilot blockers",
                "Production storage owner decision path is explicit — claims remain false",
                "Controlled customer pilot and production rollout remain NO_GO",
            ],
            # dict.fromkeys, not a set literal: set iteration order for strings
            # is randomised per process, so `list({...})` reordered this list on
            # every run. Order-preserving dedupe keeps the required action first
            # and makes the payload reproducible.
            "next_safe_actions": list(
                dict.fromkeys(
                    [
                        storage.get("required_next_action"),
                        "Keep RBAC denial audits operator-visible",
                        "Do not claim customer data persistence",
                    ]
                )
            ),
            "human_review_required": True,
            "login_live_claimed": False,
            "audit_compliance_complete_claimed": False,
        }
    )


def audit_operator_storage_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "login_live_claimed",
        "audit_compliance_complete_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if surface.get("owner_approval_needed") is not True:
        fails.append("owner_approval")
    fails.extend(
        operator_review_trail_invariant_failures(
            surface.get("operator_review_trail") or {}
        )
    )
    fails.extend(
        production_storage_owner_decision_invariant_failures(
            surface.get("production_storage_decision") or {}
        )
    )
    for ev in surface.get("sample_audit_events") or []:
        fails.extend(unified_audit_event_invariant_failures(ev))
    return fails
