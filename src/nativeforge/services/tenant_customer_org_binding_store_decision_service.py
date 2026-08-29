"""Binding store decision (Gate 110C).

Where a verified tenant/customer binding should eventually live, and what would
have to be true before writing it. Applies nothing.

## The recommendation, and why it is forced

A binding is a record the database must be able to protect. The only thing this
database protects is `organization_id`: 21 columns, 21 row-level security
policies, every one reading
`organization_id = current_setting('app.current_org_id', true)::uuid`.

So the binding anchors to `organization_id`. That is not a preference between
reasonable options - a binding keyed on `tenant_id` would be a record RLS cannot
see, sitting in a table whose whole purpose is to make cross-tenant access
impossible.

```text
recommended_store         new_identity_binding_table
recommended_primary_key   organization_id (UUID, FK organizations.id)
tenant_id                 a label column on that row, never the key
rls_enforced_by           organization_id
```

## Why a table rather than a column on organizations

A binding has a lifecycle: pending, verified, revoked. It has a verifier, a
verification time, and a history that must survive revocation. Gate 109 built
those statuses for a reason.

A `tenant_label` column on `organizations` would hold the current value and
nothing else - no verifier, no revocation history, no way to distinguish "never
bound" from "bound then withdrawn". The first audit question after an incident is
*when did this binding change and who approved it*, and a column cannot answer it.

## migration_safe_now is false, and that is the interesting part

The recommendation is clear. Acting on it is not safe yet, and the reasons are
specific rather than general caution:

```text
no verified binding exists to store        Gate 109's own readiness says so
customer auth is not live                  nobody can be the verifier
customer persistence is not live           no write path exists to use it
org_id is overloaded across ~70 services   an alias in routes, a free-form
                                           string elsewhere; a migration that
                                           assumes the first would be wrong
                                           wherever the second is true
```

A recommendation can be right while the migration remains wrong to apply. Those
are separate questions and this service answers both, separately.

## What is deliberately not recommended

```text
tenant_id as RLS authority     it has no column, no route, no repository, and
                               cannot be cast to uuid
demo ids as persistence keys   nf-demo- values must never reach a real table
organization_profile_id        String(128), no FK, on a table with no RLS and a
                               check constraint forbidding production use
```
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_customer_org_binding_store_decision_v1"

STORE_OPTIONS = frozenset(
    {
        "no_store_yet",
        "organization_profile_extension",
        "new_identity_binding_table",
        "existing_membership_table_extension",
        "unknown",
    }
)

# The only column the database enforces isolation on.
RLS_AUTHORITY_COLUMN = "organization_id"

# Identity names that may never key a binding store.
FORBIDDEN_STORE_KEYS = frozenset(
    {"tenant_id", "customer_org_id", "organization_profile_id"}
)

DECISION_FIELDS: tuple[str, ...] = (
    "recommended_store",
    "recommended_primary_key",
    "recommended_foreign_keys",
    "requires_migration",
    "migration_safe_now",
    "rls_enforced_by",
    "binding_lookup_key",
    "demo_binding_storage_allowed",
    "operational_binding_storage_allowed",
    "blocked_reasons",
    "next_required_actions",
)

NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "stand_up_customer_auth",
        "a verified binding needs a verifier, and nobody can be one until a "
        "person can authenticate. Gate 111 built the contracts that decide who "
        "may verify - the auth principal, the binder authorization and the RLS "
        "claim guard - but the login promotion gate still reports seven of ten "
        "gates missing, so no provider is attached",
    ),
    (
        "map_oidc_claims_to_organization_id",
        "the OIDC identity mapper resolves a claim to organization_profile_id, "
        "a String(128) with no foreign key on a table with no RLS. Even a live "
        "login would not produce the UUID the policies enforce on",
    ),
    (
        "resolve_org_id_overloading_in_persistence_paths",
        "org_id is a uuid.UUID in routes and a free-form string in most of the "
        "~70 services using it; a migration assuming the first is wrong "
        "wherever the second holds",
    ),
    (
        "create_the_identity_binding_table_under_rls",
        "organization_id primary anchor, tenant label column, the Gate 109 "
        "statuses, a verifier and a verified_at",
    ),
    (
        "backfill_nothing",
        "there is no verified binding to migrate; the table starts empty and "
        "fills as bindings are verified",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_binding_store_decision(
    *,
    rls_authority_confirmed: bool | None = None,
    customer_auth_live: bool | None = None,
    customer_persistence_live: bool | None = None,
    verified_binding_available: bool | None = None,
) -> dict[str, Any]:
    """Recommend a store and say whether acting on it is safe. Applies nothing."""
    from nativeforge.services.awarded_grants_requirements_readiness_service import (
        build_awarded_requirements_readiness,
    )
    from nativeforge.services.org_identity_role_contract_service import (
        build_identity_role_matrix,
    )
    from nativeforge.services.tenant_beta_readiness_service import (
        build_tenant_beta_readiness,
    )

    # Detected, not declared. Each override exists so a test can force the
    # opposite state; none of them is read from a caller in normal operation.
    matrix = build_identity_role_matrix()
    if rls_authority_confirmed is None:
        rls_authority_confirmed = bool(matrix["organization_id_is_rls_authority"])

    awarded = build_awarded_requirements_readiness()
    beta = build_tenant_beta_readiness()
    if customer_persistence_live is None:
        customer_persistence_live = bool(awarded.get("customer_persistence_live"))
    if customer_auth_live is None:
        customer_auth_live = bool(beta.get("customer_auth_live"))
    if verified_binding_available is None:
        verified_binding_available = bool(
            awarded.get("verified_operational_identity_binding")
        )

    blocked_reasons: list[str] = []

    if not rls_authority_confirmed:
        blocked_reasons.append("rls_authority_not_confirmed")
    if not customer_auth_live:
        blocked_reasons.append("no_customer_auth_so_nobody_can_verify_a_binding")
    if not customer_persistence_live:
        blocked_reasons.append("no_customer_persistence_to_write_a_binding_into")
    if not verified_binding_available:
        blocked_reasons.append("no_verified_binding_exists_to_store")

    # The recommendation follows from where isolation is enforced. It does not
    # depend on whether acting on it is safe yet - those are separate questions.
    if rls_authority_confirmed:
        recommended_store = "new_identity_binding_table"
        recommended_primary_key = RLS_AUTHORITY_COLUMN
        recommended_foreign_keys = ["organizations.id"]
        rls_enforced_by = RLS_AUTHORITY_COLUMN
        binding_lookup_key = RLS_AUTHORITY_COLUMN
    else:
        recommended_store = "unknown"
        recommended_primary_key = None
        recommended_foreign_keys = []
        rls_enforced_by = None
        binding_lookup_key = None
        blocked_reasons.append("cannot_recommend_a_store_without_an_rls_authority")

    requires_migration = recommended_store not in {"no_store_yet", "unknown"}

    # Derived affirmatively: every precondition must hold.
    migration_safe_now = bool(
        rls_authority_confirmed
        and customer_auth_live
        and customer_persistence_live
        and verified_binding_available
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "recommended_store": recommended_store,
            "recommended_primary_key": recommended_primary_key,
            "recommended_foreign_keys": recommended_foreign_keys,
            "recommended_label_columns": ["tenant_id", "customer_org_id"],
            "requires_migration": requires_migration,
            "migration_safe_now": migration_safe_now,
            "migration_applied": False,
            "rls_enforced_by": rls_enforced_by,
            "binding_lookup_key": binding_lookup_key,
            "demo_binding_storage_allowed": False,
            "operational_binding_storage_allowed": migration_safe_now,
            "rls_authority_confirmed": rls_authority_confirmed,
            "customer_auth_live": customer_auth_live,
            "customer_persistence_live": customer_persistence_live,
            "verified_binding_available": verified_binding_available,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": [
                {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
            ],
            # Constants: a decision changes no schema.
            "tenant_id_recommended_as_rls_authority": False,
            "demo_ids_recommended_as_persistence_keys": False,
            "schema_changed": False,
            "rows_written": 0,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in DECISION_FIELDS:
        if field not in decision:
            fails.append(f"decision_missing_field:{field}")

    for constant in (
        "tenant_id_recommended_as_rls_authority",
        "demo_ids_recommended_as_persistence_keys",
        "migration_applied",
        "schema_changed",
        "demo_binding_storage_allowed",
        "fabricated",
        "live_fetch_performed",
    ):
        if decision.get(constant) is not False:
            fails.append(f"decision_claimed:{constant}")

    if decision.get("rows_written") != 0:
        fails.append("decision_wrote_rows")

    if decision.get("recommended_store") not in STORE_OPTIONS:
        fails.append("recommended_store_out_of_vocabulary")

    # The store may never be keyed on a label.
    for key in ("recommended_primary_key", "binding_lookup_key"):
        if decision.get(key) in FORBIDDEN_STORE_KEYS:
            fails.append(f"{key}_is_a_label_not_an_authority:{decision.get(key)}")

    # RLS enforcement may only be the authority column.
    if decision.get("rls_enforced_by") not in {RLS_AUTHORITY_COLUMN, None}:
        fails.append("rls_enforced_by_is_not_the_authority_column")

    # A recommended store must anchor to the authority.
    if decision.get("recommended_store") == "new_identity_binding_table":
        if decision.get("recommended_primary_key") != RLS_AUTHORITY_COLUMN:
            fails.append("recommended_table_not_anchored_to_the_rls_authority")
        if "organizations.id" not in (decision.get("recommended_foreign_keys") or []):
            fails.append("recommended_table_without_a_foreign_key_to_organizations")

    # Safety must agree with the measurements.
    expected_safe = bool(
        decision.get("rls_authority_confirmed")
        and decision.get("customer_auth_live")
        and decision.get("customer_persistence_live")
        and decision.get("verified_binding_available")
        and not decision.get("blocked_reasons")
    )
    if decision.get("migration_safe_now") is not expected_safe:
        fails.append("migration_safe_now_disagrees_with_the_measurements")

    # Operational storage may not outrun migration safety.
    if decision.get("operational_binding_storage_allowed") and not decision.get(
        "migration_safe_now"
    ):
        fails.append("operational_storage_permitted_before_migration_is_safe")

    # A refusal must name itself.
    if not decision.get("migration_safe_now") and not decision.get("blocked_reasons"):
        fails.append("migration_refused_without_a_reason")

    return fails
