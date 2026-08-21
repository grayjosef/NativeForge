"""Controlled customer pilot final gate resolver (Block 44)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.login_live_promotion_gate_service import (
    evaluate_login_live_promotion,
)
from nativeforge.services.storage_provisioning_execution_guard_service import (
    evaluate_storage_provisioning_guard,
)

SCHEMA_VERSION = "nf_controlled_customer_pilot_gate_resolver_v1"

STATUS_NO_GO = "NO_GO"
STATUS_CONDITIONAL_INTERNAL = "CONDITIONAL_INTERNAL_ONLY"
STATUS_READY_OWNER_REVIEW = "READY_FOR_OWNER_REVIEW"
STATUS_READY_LIMITED_EXT = "READY_FOR_LIMITED_EXTERNAL_VALIDATION"
STATUS_CONTROLLED_GO = "CONTROLLED_CUSTOMER_GO"
STATUS_PROD_ROLLOUT_NO_GO = "PRODUCTION_ROLLOUT_NO_GO"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_controlled_customer_pilot_gate(
    *,
    login_live: bool = False,
    production_auth: bool = False,
    rbac_scope_ready: bool = True,
    tenant_isolation_ready: bool = True,
    storage_ready: bool = False,
    customer_persistence_ready: bool = False,
    full_sca_passed: bool = True,
    pen_test_passed: bool = False,
    authority_live: bool = False,
    source_coverage_live: bool = False,
    operator_support_ready: bool = True,
    customer_invite_ready: bool = False,
    owner_approval_present: bool = False,
) -> dict[str, Any]:
    missing: list[str] = []
    if not login_live:
        missing.append("login_not_live")
    if not production_auth:
        missing.append("production_auth_incomplete")
    if not rbac_scope_ready:
        missing.append("rbac_scope")
    if not tenant_isolation_ready:
        missing.append("tenant_isolation")
    if not storage_ready:
        missing.append("storage_not_ready")
    if not customer_persistence_ready:
        missing.append("customer_persistence_not_ready")
    if not full_sca_passed:
        missing.append("full_sca_not_passed")
    if not pen_test_passed:
        missing.append("pen_test_not_passed")
    if not authority_live:
        missing.append("authority_not_live")
    if not source_coverage_live:
        missing.append("source_coverage_not_live")
    if not operator_support_ready:
        missing.append("operator_support")
    if not customer_invite_ready:
        missing.append("customer_invite_not_ready")
    if not owner_approval_present:
        missing.append("owner_approval_absent")

    # Default NO_GO; never CONTROLLED_CUSTOMER_GO in Mode A
    status = STATUS_NO_GO
    reason = "Required external and owner gates incomplete"
    if (
        full_sca_passed
        and rbac_scope_ready
        and operator_support_ready
        and not login_live
    ):
        status = STATUS_CONDITIONAL_INTERNAL
        reason = "Internal/demo path OK; external auth/storage/pen-test incomplete"
    if owner_approval_present and not login_live:
        status = STATUS_READY_OWNER_REVIEW
        reason = "Owner approval present for review — live gates still incomplete"

    # Hard: never emit CONTROLLED_CUSTOMER_GO unless every gate true
    if len(missing) == 0:
        status = STATUS_CONTROLLED_GO
        reason = "All gates passed"
    # Gate 19 Mode A safety: force NO_GO / conditional even if somehow empty missing
    # because login_live etc are false → missing non-empty. Keep production rollout NO_GO.
    if status == STATUS_CONTROLLED_GO and (
        not login_live or not pen_test_passed or not storage_ready
    ):
        status = STATUS_NO_GO
        reason = "Safety clamp — controlled GO requires live auth/storage/pen-test"

    production_rollout_status = STATUS_PROD_ROLLOUT_NO_GO

    allowed = [
        "Monday demo GO",
        "internal production-grade readiness ~95.9%",
        "full SCA passed (Gate 16 evidence)",
        "Auth0 live validation execution support exists",
        "storage approval/provisioning execution path exists",
        "controlled pilot gate resolver exists",
        "login_live=false",
        "production_storage=false",
        "customer_persistence=false",
    ]
    forbidden = [
        "production-ready",
        "customer login live",
        "production auth complete",
        "production storage approved/validated",
        "customer persistence live",
        "controlled customer pilot GO",
        "production rollout GO",
        "pen-test passed",
        "final eligibility",
        "submission-ready",
        "final export",
    ]

    # Cross-check login/storage resolvers for surface honesty
    login_promo = evaluate_login_live_promotion()
    storage_guard = evaluate_storage_provisioning_guard()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "controlled_customer_pilot_status": status,
            "production_rollout_status": production_rollout_status,
            "reason": reason,
            "missing_gates": missing,
            "next_safe_action": (
                "Complete Auth0 live validation and storage approval/validation; "
                "schedule and pass pen-test before any controlled customer GO"
            ),
            "allowed_claims": allowed,
            "forbidden_claims": forbidden,
            "login_live_claimed": bool(login_promo.get("login_live_claimed")),
            "production_storage_claimed": bool(
                storage_guard.get("production_storage_claimed")
            ),
            "customer_data_persistence_claimed": bool(
                storage_guard.get("customer_data_persistence_claimed")
            ),
            "human_review_required": True,
        }
    )


def controlled_customer_pilot_gate_resolver_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if result.get("controlled_customer_pilot_status") in {
        STATUS_CONTROLLED_GO,
        "GO",
    }:
        fails.append("pilot_go")
    if result.get("production_rollout_status") not in {
        STATUS_PROD_ROLLOUT_NO_GO,
        "NO_GO",
        "PRODUCTION_ROLLOUT_NO_GO",
    }:
        fails.append("production_rollout_not_nogo")
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails
