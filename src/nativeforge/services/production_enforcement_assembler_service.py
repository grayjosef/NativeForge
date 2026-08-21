"""Block 31 assembler: production storage + tenant enforcement panel."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.production_claim_resolver_service import (
    production_claim_resolver_invariant_failures,
    resolve_production_claims,
)
from nativeforge.services.tenant_boundary_enforcement_service import (
    run_tenant_isolation_suite,
    tenant_isolation_suite_invariant_failures,
)

SCHEMA_VERSION = "nf_production_enforcement_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_production_enforcement_demo_surface() -> dict[str, Any]:
    resolved = resolve_production_claims(
        pen_test_passed=False,
        sca_passed=False,
        operator_readiness_pass=False,
        login_live=False,
    )
    tenant = run_tenant_isolation_suite()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 31,
            "title": "Production storage / multi-tenant enforcement packet",
            "claim_resolver": resolved,
            "tenant_isolation_suite": tenant,
            "buyer_summary": [
                "Local/dev evidence persistence remains validated",
                "Production storage and customer data persistence remain false",
                "Tenant boundary enforcement model denies cross-org access",
                "Controlled customer pilot remains NO_GO until deps + pen-test/SCA + auth pass",
            ],
            "local_dev_persistence_validated": True,
            "production_storage_configured": False,
            "production_storage_validated": False,
            "customer_data_policy_validated": False,
            "tenant_isolation_status": "partial",
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_multi_tenant_claimed": False,
            "controlled_customer_pilot_storage_ready": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "blockers": resolved.get("blockers") or [],
            "next_safe_actions": resolved.get("next_safe_actions") or [],
        }
    )


def production_enforcement_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_multi_tenant_claimed",
        "controlled_customer_pilot_storage_ready",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if surface.get("production_rollout_status") == "GO":
        fails.append("production_go")
    fails.extend(
        production_claim_resolver_invariant_failures(
            surface.get("claim_resolver") or {}
        )
    )
    fails.extend(
        tenant_isolation_suite_invariant_failures(
            surface.get("tenant_isolation_suite") or {}
        )
    )
    return fails
