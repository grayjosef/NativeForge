"""Binding store readiness (Gate 113F).

Gate 113 created ``nf_tenant_customer_org_bindings``. This service answers the
question that immediately follows and is easy to get wrong: **what does the
table existing actually make possible?**

The answer is very little, and saying so precisely is the point.

## Four questions, four answers, deliberately not one

```text
store_schema_available      is there a migration in this repo that creates it?
store_contract_available    is there a service that decides what may go in it?
store_writable              has a database actually run that migration?
operational_binding_storage may a verified customer binding be written today?
```

The first two are true. The third and fourth are false, and they are false for
different reasons — a distinction that a single ``ready`` boolean would erase.
The third is false because no database is provisioned. The fourth is false for
Gate 110's three reasons, none of which a ``CREATE TABLE`` addresses: nobody can
authenticate, so nobody can be a verifier; there is no customer persistence to
write into; and no verified binding exists to store.

## Why this service exists at all

Because "the table is there" reads like progress, and progress is exactly what
somebody will quote out of a readiness report. A table under RLS containing zero
rows is a container, not a capability. This service is the place that refuses to
let the two be confused, and it does that by reporting them as separate detected
values rather than as one summary word.

## Everything detected, nothing declared

Schema availability is read off the migrations directory. Contract availability
is established by importing the service that owns the contract. The blocking
reasons are read from Gate 110's decision, not restated here — restating them
would let the two drift, and a readiness surface that disagrees with the
decision it summarises is worse than no readiness surface.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_customer_org_binding_store_readiness_v1"

BINDING_TABLE = "nf_tenant_customer_org_bindings"

# The services that make a binding store meaningful. Each is detected by import,
# so a missing one reports absent rather than being assumed present.
STORE_COMPONENT_MODULES: dict[str, str] = {
    "binding_contract_available": (
        "nativeforge.services.tenant_customer_org_identity_binding_service"
    ),
    "store_decision_available": (
        "nativeforge.services.tenant_customer_org_binding_store_decision_service"
    ),
    "store_contract_available": (
        "nativeforge.services.tenant_customer_org_binding_store_service"
    ),
    "persistence_guard_available": (
        "nativeforge.services.identity_persistence_safety_guard_service"
    ),
    "membership_verification_available": (
        "nativeforge.services.customer_org_membership_verification_service"
    ),
    "organization_id_resolution_available": (
        "nativeforge.services.oidc_organization_id_resolution_service"
    ),
}

# Reported on every result. Naming them individually means a report can say
# which capability is missing instead of only that readiness is false.
READINESS_FIELDS: tuple[str, ...] = (
    "store_schema_available",
    "store_contract_available",
    "store_writable",
    # Gate 120B. A schema is a container, a repository is something that can
    # address it, and a write path is both plus a contract that decides what
    # goes in. Three facts, reported separately, because a table with no
    # repository and a repository with no table fail in different ways.
    "repository_available",
    "write_path_available",
    "operational_verified_binding",
    "operational_binding_storage_ready",
    "demo_binding_storage_ready",
    "blocked_reasons",
)

# Claims this service is never allowed to make, whatever it detects. Each was a
# plausible-sounding sentence somebody could otherwise write from a green
# readiness line.
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "customer_bindings_stored",
    "customer_auth_live",
    "customer_persistence_live",
    "beta_onboarding_ready",
    "production_rollout_ready",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def build_binding_store_readiness(
    *,
    versions_dir: Path | None = None,
    database_revision: str | None = None,
) -> dict[str, Any]:
    """What the binding store makes possible today. Detected, never declared."""
    from nativeforge.services.tenant_customer_org_binding_store_decision_service import (  # noqa: E501
        build_binding_store_decision,
    )

    components = {
        key: _module_importable(module)
        for key, module in STORE_COMPONENT_MODULES.items()
    }

    decision = build_binding_store_decision(
        versions_dir=versions_dir, database_revision=database_revision
    )

    store_schema_available = bool(decision["migration_defined"])
    store_writable = bool(decision["migration_applied"])
    store_contract_available = bool(components["store_contract_available"])

    # Measured by import rather than asserted. Gate 120B's repository is the
    # first thing in this repository that can address the binding table.
    repository_available = _module_importable(
        "nativeforge.services.tenant_customer_org_binding_repository_service"
    )
    workflow_available = _module_importable(
        "nativeforge.services.verified_binding_workflow_service"
    )
    write_path_available = bool(
        store_schema_available and repository_available and store_contract_available
    )

    blocked_reasons: list[str] = list(decision.get("blocked_reasons") or [])

    if not store_schema_available:
        blocked_reasons.append("no_migration_defines_the_binding_store")
    if not store_contract_available:
        blocked_reasons.append("no_service_decides_what_may_enter_the_store")
    if not store_writable:
        # The most misreadable state in this whole service: the table is
        # specified and no database has it. Named so it cannot be summarised
        # away as "store available".
        blocked_reasons.append("no_database_has_applied_the_binding_store_migration")

    for key, present in sorted(components.items()):
        if not present:
            blocked_reasons.append(f"component_absent:{key}")

    # Derived affirmatively. Every conjunct must hold; the decision service's own
    # permission is one of them, so this surface can never outrun it.
    operational_ready = bool(
        store_schema_available
        and store_contract_available
        and store_writable
        and decision["operational_binding_storage_allowed"]
        and all(components.values())
        and not blocked_reasons
    )

    # Demo storage is a separate refusal with a separate reason. A demo fixture
    # is not a smaller version of a verified binding; it is a different thing
    # that must never be stored where verified bindings live.
    demo_ready = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "store_table": BINDING_TABLE,
            "store_schema_available": store_schema_available,
            "store_migration_revision": decision["migration_revision"],
            "store_contract_available": store_contract_available,
            "store_writable": store_writable,
            "repository_available": repository_available,
            "workflow_available": workflow_available,
            "write_path_available": write_path_available,
            # A repository existing moves the write path. It does not move
            # this: a binding binds nobody until somebody can be authenticated
            # as the person it names, and 11 of 16 activation gates are unmet.
            "operational_verified_binding": bool(
                write_path_available and decision["customer_auth_live"]
            ),
            "operational_binding_storage_ready": operational_ready,
            "demo_binding_storage_ready": demo_ready,
            "rls_anchor": decision["rls_enforced_by"],
            # Gate 114: where this lane sits in the persistence spine, and what
            # the spine says to build next. A readiness surface that reports a
            # refusal without saying what would lift it leaves the reader to
            # guess, and the guess is usually "build this one harder".
            "persistence_spine_position": _spine_position(),
            **components,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants. A readiness report reads nothing and writes nothing.
            "rows_stored": 0,
            "customer_bindings_stored": False,
            "customer_auth_live": bool(decision["customer_auth_live"]),
            "customer_persistence_live": bool(decision["customer_persistence_live"]),
            "beta_onboarding_ready": False,
            "production_rollout_ready": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def _spine_position() -> dict[str, Any]:
    """This lane's place in the Gate 114D sequence, read from that service.

    Imported inside the function because the spine decision reads the capability
    model, which reads this repository's schema - keeping the import local keeps
    the module graph acyclic and the cost off the import path.
    """
    try:
        from nativeforge.services.customer_persistence_spine_decision_service import (
            build_persistence_spine_decision,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return {
            "capability": "identity_binding_persistence",
            "position": None,
            "ready_to_build": False,
            "unmet_prerequisites": ["spine_decision_unavailable"],
            "next_recommended": None,
        }

    decision = build_persistence_spine_decision()
    entry = next(
        (
            row
            for row in decision["recommended_sequence"]
            if row["capability"] == "identity_binding_persistence"
        ),
        {},
    )
    return {
        "capability": "identity_binding_persistence",
        "position": entry.get("position"),
        "ready_to_build": bool(entry.get("ready_to_build")),
        "unmet_prerequisites": list(entry.get("unmet_prerequisites") or []),
        "next_recommended": decision.get("next_gate_recommendation", {}).get(
            "recommendation"
        ),
    }


def readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in READINESS_FIELDS:
        if field not in readiness:
            fails.append(f"readiness_missing_field:{field}")

    if readiness.get("rows_stored") != 0:
        fails.append("readiness_report_stored_rows")

    for claim in ("beta_onboarding_ready", "production_rollout_ready"):
        if readiness.get(claim) is not False:
            fails.append(f"readiness_claimed:{claim}")

    # The table existing is not the table being writable. This is the single
    # confusion this service was written to prevent, so it is also an invariant.
    if readiness.get("store_writable") and not readiness.get("store_schema_available"):
        fails.append("store_writable_without_a_defined_schema")

    # Storage readiness requires somewhere to store.
    if readiness.get("operational_binding_storage_ready"):
        for required in (
            "store_schema_available",
            "store_contract_available",
            "store_writable",
        ):
            if not readiness.get(required):
                fails.append(f"operational_ready_without:{required}")
        if readiness.get("blocked_reasons"):
            fails.append("operational_ready_with_blocked_reasons")
        if not readiness.get("customer_auth_live"):
            fails.append("operational_ready_without_anybody_who_could_verify")
        if not readiness.get("customer_persistence_live"):
            fails.append("operational_ready_without_customer_persistence")

    # Bindings claimed as stored while nothing may be stored.
    if readiness.get("customer_bindings_stored"):
        fails.append("readiness_claimed:customer_bindings_stored")

    # Demo storage is refused unconditionally at this surface.
    if readiness.get("demo_binding_storage_ready"):
        fails.append("demo_binding_storage_reported_ready")

    # RLS may only ever be anchored on the authority column.
    if readiness.get("rls_anchor") not in {"organization_id", None}:
        fails.append("readiness_reported_a_non_authority_rls_anchor")

    # A refusal must name itself.
    if not readiness.get("operational_binding_storage_ready") and not readiness.get(
        "blocked_reasons"
    ):
        fails.append("storage_refused_without_a_reason")

    # Gate 114: and it must say what would lift it. A blocked lane with no
    # place in the sequence is a dead end rather than a next step.
    spine = readiness.get("persistence_spine_position") or {}
    if not readiness.get("operational_binding_storage_ready"):
        if not spine:
            fails.append("readiness_refused_without_a_spine_position")
        elif spine.get("ready_to_build") and spine.get("unmet_prerequisites"):
            fails.append("spine_reports_ready_to_build_with_unmet_prerequisites")

    return fails
