"""Gate 10 approval lane resolver for local/dev-only persistent storage.

OWNER_APPROVED_MIGRATIONS=true with APPROVED_ENVIRONMENT=local_dev_only.
Production and customer-data mutation remain forbidden.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_persistence_approval_resolver_v1"

# Gate 10 Mayhem approval (current chat)
OWNER_APPROVED_MIGRATIONS = True
APPROVED_ENVIRONMENT = "local_dev_only"
APPROVAL_SOURCE = "current_chat_mayhem_gate10"
PRODUCTION_DATA_MUTATION_ALLOWED = False
CUSTOMER_DATA_MUTATION_ALLOWED = False

APPROVAL_SCOPES = frozenset({"local_dev_only", "not_approved", "production_not_allowed"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_persistence_approval_lane(
    *,
    owner_approved_migrations: bool = OWNER_APPROVED_MIGRATIONS,
    approved_environment: str = APPROVED_ENVIRONMENT,
    approval_source: str = APPROVAL_SOURCE,
    production_data_mutation_allowed: bool = PRODUCTION_DATA_MUTATION_ALLOWED,
    customer_data_mutation_allowed: bool = CUSTOMER_DATA_MUTATION_ALLOWED,
) -> dict[str, Any]:
    env = approved_environment if approved_environment else "not_approved"
    approved = bool(owner_approved_migrations) and env == "local_dev_only"
    if production_data_mutation_allowed or customer_data_mutation_allowed:
        # Hard stop — Gate 10 forbids these even if misconfigured
        approved = False

    scope = "local_dev_only" if approved else "not_approved"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "owner_approval_status": "approved" if approved else "blocked",
            "approval_source": approval_source,
            "approval_scope": scope,
            "approved_environment": env if approved else "not_approved",
            "migration_allowed": bool(approved),
            "storage_validation_allowed": bool(approved),
            "production_data_mutation_allowed": False,
            "customer_data_mutation_allowed": False,
            "validated_persistent_claim_allowed": (
                "true_only_for_local_dev" if approved else "false"
            ),
            "production_storage_claim_allowed": False,
            "customer_data_persistence_claim_allowed": False,
            "owner_approved_migrations_flag": bool(owner_approved_migrations),
            "gate10_local_dev_lane": bool(approved),
        }
    )


def persistence_approval_lane_invariant_failures(lane: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if lane.get("production_data_mutation_allowed") is True:
        fails.append("production_data_mutation_allowed")
    if lane.get("customer_data_mutation_allowed") is True:
        fails.append("customer_data_mutation_allowed")
    if lane.get("production_storage_claim_allowed") is True:
        fails.append("production_storage_claim_allowed")
    if lane.get("customer_data_persistence_claim_allowed") is True:
        fails.append("customer_data_persistence_claim_allowed")
    if lane.get("approval_scope") == "local_dev_only":
        if lane.get("approved_environment") != "local_dev_only":
            fails.append("scope_env_mismatch")
        if lane.get("validated_persistent_claim_allowed") != "true_only_for_local_dev":
            fails.append("validated_claim_not_local_dev_scoped")
    if (
        lane.get("migration_allowed") is True
        and lane.get("approval_scope") != "local_dev_only"
    ):
        fails.append("migration_allowed_outside_local_dev")
    return fails
