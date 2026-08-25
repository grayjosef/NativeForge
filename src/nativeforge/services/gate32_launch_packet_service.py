"""Controlled-pilot launch packet + remaining non-owner blockers (Block 74)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)

SCHEMA_VERSION = "nf_gate32_launch_packet_v1"

LAUNCH_STATUSES = (
    "internal_demo_go",
    "conditional_internal_only",
    "ready_for_owner_review",
    "ready_for_limited_external_validation",
    "controlled_customer_go",
    "no_go",
    "blocked_owner_inputs",
    "blocked_security",
    "blocked_auth",
    "blocked_storage",
    "blocked_source_authority",
    "unknown",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_launch_packet(
    *,
    login_live: bool = False,
    production_auth: bool = False,
    production_storage: bool = False,
    pen_test_passed: bool = False,
    ready_for_owner_review: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    owner = [
        "Auth0/OIDC OOB + live validation",
        "storage approval + production config",
        "pen-test report/evidence",
    ]
    non_owner = [
        "source freshness probes where safe",
        "observability healthchecks beyond smoke",
        "support owner assignment staffing",
        "non-prod restore evidence ref",
    ]
    external = ["pen-test vendor report", "optional live SAM/UEI vendor path"]
    go_checklist = [
        "login_live",
        "production_auth",
        "production_storage",
        "customer_persistence",
        "pen_test_passed",
        "authority_live_submit",
        "top15_or_scoped_coverage",
        "invite_readiness",
        "support_ready",
    ]
    blocked = not (
        login_live and production_auth and production_storage and pen_test_passed
    )
    status = "conditional_internal_only"
    if ready_for_owner_review and blocked:
        status = "ready_for_owner_review"
    if blocked:
        if not login_live:
            status = "blocked_auth" if not ready_for_owner_review else status
        status = "conditional_internal_only"
        if ready_for_owner_review:
            status = "ready_for_owner_review"
    if status == "controlled_customer_go" and blocked:
        status = "no_go"
    if blocked:
        pilot = "CONDITIONAL_INTERNAL_ONLY"
    else:
        pilot = "CONTROLLED_CUSTOMER_GO"
    if blocked:
        pilot = "CONDITIONAL_INTERNAL_ONLY"
    next_seq = [
        "Continue non-owner freshness/observability/restore evidence",
        "Owner: provide OIDC_* OOB",
        "Owner: storage approval + config",
        "Owner: pen-test evidence",
        "Re-run Gate 29 ingest + Gate 30 resolver",
    ]
    allowed = [
        "monday_demo_go",
        "conditional_internal_only",
        "launch_packet_exists",
        "non_prod_backup_manifest",
    ]
    forbidden = [
        "controlled_customer_pilot_go",
        "production_rollout_go",
        "production_ready",
        "login_live",
        "production_storage",
        "pen_test_passed",
        "invite_sent",
        "top15_live",
    ]
    collector.add({"event": "launch_packet"})
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "launch_packet_contract": True,
            "launch_statuses": list(LAUNCH_STATUSES),
            "launch_status": status,
            "internal_pilot_checklist": [
                "monday_demo_go",
                "claim_freeze",
                "internal_review_routes",
            ],
            "limited_external_validation_checklist": [
                "explicit_limited_policy",
                "login_live",
                "production_auth",
            ],
            "controlled_customer_go_checklist": go_checklist,
            "non_owner_blockers": non_owner,
            "owner_gated_blockers": owner,
            "external_vendor_blockers": external,
            "customer_feedback_required": [
                "SC feedback customers after invite allowed"
            ],
            "post_pilot_work": ["authority live submit", "source live extraction"],
            "production_rollout_work": ["production backup/restore", "rollout review"],
            "next_action_sequence": next_seq,
            "controlled_customer_pilot_status": pilot,
            "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
            "allowed_claims": allowed,
            "forbidden_claims": forbidden,
            "ready_for_owner_review_is_not_go": True,
            "limited_external_is_not_go": True,
            "internal_demo_is_not_production": True,
        }
    )


def launch_packet_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    if result.get("production_rollout_status") == "GO":
        fails.append("rollout_go")
    if result.get("launch_status") == "controlled_customer_go":
        fails.append("launch_go")
    if not result.get("next_action_sequence"):
        fails.append("no_next_actions")
    if not result.get("owner_gated_blockers") or not result.get("non_owner_blockers"):
        fails.append("blockers_not_separated")
    return fails
