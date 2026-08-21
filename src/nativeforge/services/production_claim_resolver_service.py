"""Production claim resolver (Campaign Block 31)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.production_storage_readiness_contract_service import (
    build_production_storage_readiness_contract,
)
from nativeforge.services.tenant_boundary_enforcement_service import (
    run_tenant_isolation_suite,
)

SCHEMA_VERSION = "nf_production_claim_resolver_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_production_claims(
    *,
    pen_test_passed: bool = False,
    sca_passed: bool = False,
    operator_readiness_pass: bool = False,
    login_live: bool = False,
) -> dict[str, Any]:
    storage = build_production_storage_readiness_contract()
    tenant = run_tenant_isolation_suite()

    # No single local/dev flag unlocks production
    production_storage_ready = bool(
        storage.get("all_critical_dependencies_pass")
        and storage.get("local_dev_persistence_validated")
        and storage.get("production_storage_validated") == "pass"
    )
    # Explicitly keep false in Gate 13
    production_storage_claimed = False
    customer_data_persistence_claimed = False
    production_multi_tenant_claimed = False

    controlled_pilot_ready = bool(
        production_storage_ready
        and login_live
        and storage.get("auth_dependency_status") == "pass"
        and storage.get("rbac_dependency_status") == "pass"
        and storage.get("tenant_isolation_status") == "pass"
        and tenant.get("overall_status") == "PASS"
        and pen_test_passed
        and sca_passed
        and operator_readiness_pass
        and storage.get("customer_data_policy_validated") == "pass"
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_readiness": storage,
            "tenant_isolation": {
                "overall_status": tenant.get("overall_status"),
                "production_multi_tenant_claimed": False,
            },
            "production_storage_readiness": "blocked",
            "customer_data_persistence_readiness": "blocked",
            "controlled_customer_pilot_readiness": "blocked",
            "production_multi_tenant_readiness": "partial_model_only",
            "upload_rollout_readiness": "blocked",
            "external_pilot_readiness": "blocked",
            "production_storage_claimed": production_storage_claimed,
            "customer_data_persistence_claimed": customer_data_persistence_claimed,
            "production_multi_tenant_claimed": production_multi_tenant_claimed,
            "controlled_customer_pilot_go": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "pen_test_passed": bool(pen_test_passed),
            "sca_passed": bool(sca_passed),
            "login_live": bool(login_live),
            "controlled_pilot_ready_computed": bool(controlled_pilot_ready),
            "blockers": list(storage.get("blocker_reasons") or [])
            + [
                "login_not_live",
                "pen_test_not_passed",
                "sca_not_passed",
                "production_storage_not_validated",
            ],
            "next_safe_actions": list(storage.get("next_safe_actions") or []),
        }
    )


def production_claim_resolver_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_multi_tenant_claimed",
        "controlled_customer_pilot_go",
    ):
        if report.get(key) is True:
            fails.append(key)
    if report.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if report.get("production_rollout_status") == "GO":
        fails.append("production_go")
    # Local/dev alone must not unlock
    storage = report.get("storage_readiness") or {}
    if (
        storage.get("local_dev_persistence_validated") is True
        and report.get("production_storage_claimed") is True
        and not storage.get("all_critical_dependencies_pass")
    ):
        fails.append("local_dev_unlocked_production")
    return fails
