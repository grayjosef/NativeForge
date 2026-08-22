"""Post-input pilot resolver (Block 86). Default Mode A: CONDITIONAL_INTERNAL_ONLY."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate35_auth0_ingest_service import run_auth0_real_ingest
from nativeforge.services.gate35_pentest_ingest_service import run_pentest_ingest
from nativeforge.services.gate35_storage_ingest_service import run_storage_real_ingest

SCHEMA_VERSION = "nf_gate35_pilot_resolver_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_post_input_pilot(
    *,
    login_live: bool = False,
    production_auth: bool = False,
    production_storage: bool = False,
    customer_persistence: bool = False,
    customer_data_policy_ready: bool = False,
    tenant_boundary_validated: bool = False,
    audit_validated: bool = False,
    pen_test_passed: bool = False,
    limited_external_validation_policy: bool = False,
    support_owner_assigned: bool = False,
    incident_escalation_owner_assigned: bool = False,
    authority_live_submit: bool = False,
    source_coverage_scope: bool = False,
    invite_readiness: bool = False,
    operator_approval: bool = False,
    claim_freeze_verified: bool = True,
    production_rollout_gates: bool = False,
) -> dict[str, Any]:
    hard = all(
        [
            login_live,
            production_auth,
            production_storage,
            customer_persistence,
            customer_data_policy_ready,
            tenant_boundary_validated,
            audit_validated,
            pen_test_passed,
            support_owner_assigned,
            incident_escalation_owner_assigned,
            invite_readiness,
            operator_approval,
            claim_freeze_verified,
        ]
    )
    limited = bool(
        limited_external_validation_policy
        and login_live
        and production_auth
        and not hard
    )
    if hard:
        pilot = "CONTROLLED_CUSTOMER_GO"
    elif limited:
        pilot = "READY_FOR_LIMITED_EXTERNAL_VALIDATION"
    elif login_live or production_storage or pen_test_passed:
        pilot = "READY_FOR_OWNER_REVIEW"
    else:
        pilot = "CONDITIONAL_INTERNAL_ONLY"
    if not hard and pilot == "CONTROLLED_CUSTOMER_GO":
        pilot = "NO_GO"
    rollout = (
        "PRODUCTION_ROLLOUT_READY_FOR_OWNER_REVIEW"
        if production_rollout_gates and hard
        else "PRODUCTION_ROLLOUT_NO_GO"
    )
    blockers: list[str] = []
    if not login_live:
        blockers.append("login_live")
    if not production_storage:
        blockers.append("production_storage")
    if not pen_test_passed:
        blockers.append("pen_test")
    if not customer_persistence:
        blockers.append("customer_persistence")
    allowed = ["monday_demo_go", "conditional_internal_only", "owner_blocked_mode_a"]
    forbidden = [
        "controlled_customer_pilot_go",
        "production_rollout_go",
        "production-ready",
        "login live",
        "pen-test passed",
    ]
    if pilot == "CONTROLLED_CUSTOMER_GO":
        allowed = ["monday_demo_go", "controlled_customer_pilot_go"]
        forbidden = ["production_rollout_go", "production-ready"]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "resolver_rerun": True,
            "claim_freeze_rerun": True,
            "controlled_customer_pilot_status": pilot
            if pilot != "CONTROLLED_CUSTOMER_GO" or hard
            else "NO_GO",
            "limited_external_validation_status": (
                "READY_FOR_LIMITED_EXTERNAL_VALIDATION" if limited else "not_applicable"
            ),
            "production_rollout_status": rollout,
            "allowed_claims": allowed,
            "forbidden_claims": forbidden,
            "remaining_blockers": blockers,
            "next_owner_action": (
                "Provide OIDC_*, storage approval/config, pen-test package"
            ),
            "authority_live_submit": authority_live_submit,
            "source_coverage_scope": source_coverage_scope,
        }
    )


def run_gate35_bundle() -> dict[str, Any]:
    auth = run_auth0_real_ingest()
    storage = run_storage_real_ingest()
    pentest = run_pentest_ingest()
    pilot = resolve_post_input_pilot(
        login_live=bool(auth["login_live_claim"]),
        production_auth=bool(auth["production_auth_claim"]),
        production_storage=bool(storage["production_storage_claim"]),
        customer_persistence=bool(storage["customer_persistence_claim"]),
        pen_test_passed=bool(pentest["pen_test_pass_claim"]),
    )
    return _json_safe(
        {"auth": auth, "storage": storage, "pentest": pentest, "pilot": pilot}
    )


def pilot_resolver_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get(
        "controlled_customer_pilot_status"
    ) == "CONTROLLED_CUSTOMER_GO" and result.get("remaining_blockers"):
        fails.append("go_with_blockers")
    if result.get("production_rollout_status") not in {
        "PRODUCTION_ROLLOUT_NO_GO",
        "PRODUCTION_ROLLOUT_READY_FOR_OWNER_REVIEW",
    }:
        fails.append("rollout_unexpected")
    return fails
