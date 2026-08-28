"""Tenant / customer org resolution guard (Gate 109C).

Whether a surface may resolve or join tenant-scoped and org-scoped records, and
what it may do once it has.

## The question this answers

Gate 109A found the isolation that actually exists is org-scoped: Postgres RLS
keys on `app.current_org_id`, and `tenant_id` has no column and no enforcement.
Every tenant-scoped surface built since Gate 103 will eventually need to read or
write org-scoped storage, and the moment it does, something has to decide whether
the pair in hand is safe to join.

That decision is this service. It is the checkpoint between a product-lane label
and a security boundary.

## Deny by default, per operation

Permission is derived affirmatively from the binding status. There is no
permissive default to subtract from, and no caller-supplied flag can grant
anything:

```text
verified_binding   operational reads and writes
demo_fixture       demo reads and writes only - never an operational surface
pending_review     safe inspection only; writes blocked
unbound            operational reads and writes blocked
conflict           everything blocked
revoked            everything blocked
unknown            everything blocked
```

The asymmetry between `pending_review` and `unbound` is deliberate. Pending means
somebody asserted a relationship and it has not been checked - inspection is how
it gets checked, so inspection is allowed. Unbound means nobody has asserted
anything, and there is nothing to inspect.

## Cross-tenant risk is the headline, not a footnote

`cross_tenant_risk` is true whenever an operational operation is attempted
without a verified binding, or whenever the binding is in conflict. It is
reported even when the operation is refused, because the useful signal is *that
somebody tried*, not merely that it failed.

A demo operation on a demo binding carries no such risk and says so.

## Demo is not a lesser production

A `demo_fixture` binding does not grant a weaker version of operational access.
It grants access to demo operations and nothing else. The distinction matters
because the tempting shortcut - "let the demo binding through, it is only a
read" - is exactly how a demo tenant ends up reading a real organization's
awarded grants.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.tenant_customer_org_identity_binding_service import (
    BINDING_STATUSES,
    BLOCKING_BINDING_STATUSES,
    OPERATIONAL_BINDING_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_customer_org_resolution_guard_v1"

OPERATIONS = frozenset(
    {
        "tenant_digest_read",
        "tenant_digest_write",
        "awarded_grants_read",
        "awarded_grants_write",
        "document_library_read",
        "document_library_write",
        "source_watchlist_read",
        "source_watchlist_write",
        "beta_onboarding",
        "unknown",
    }
)

WRITE_OPERATIONS = frozenset(
    {
        "tenant_digest_write",
        "awarded_grants_write",
        "document_library_write",
        "source_watchlist_write",
        "beta_onboarding",
    }
)

READ_OPERATIONS = frozenset(
    {
        "tenant_digest_read",
        "awarded_grants_read",
        "document_library_read",
        "source_watchlist_read",
    }
)

# Every operation here touches customer data. There is no "harmless" one.
OPERATIONAL_OPERATIONS = READ_OPERATIONS | WRITE_OPERATIONS

# Statuses under which only demo surfaces may be reached.
DEMO_ONLY_BINDING_STATUSES = frozenset({"demo_fixture"})

# Statuses permitting inspection but never a write.
INSPECTION_ONLY_BINDING_STATUSES = frozenset({"pending_review"})

RESULT_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "customer_org_id",
    "binding_status",
    "operation",
    "resolution_allowed",
    "read_allowed",
    "write_allowed",
    "cross_tenant_risk",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_resolution(
    *,
    binding: dict[str, Any] | None = None,
    operation: Any = None,
    demo_context: bool = False,
) -> dict[str, Any]:
    """May this surface join these records, and what may it then do?"""
    op = str(operation).strip() if operation else "unknown"
    if op not in OPERATIONS:
        op = "unknown"

    binding = binding or {}
    status = binding.get("binding_status")
    if status not in BINDING_STATUSES:
        status = "unknown"

    tenant_id = binding.get("tenant_id")
    customer_org_id = binding.get("customer_org_id")

    blocked_reasons: list[str] = []

    if op == "unknown":
        blocked_reasons.append("unrecognised_operation")
    if not binding:
        blocked_reasons.append("no_binding_supplied")

    is_write = op in WRITE_OPERATIONS
    is_read = op in READ_OPERATIONS

    # Derived affirmatively. Each branch grants; nothing is subtracted from a
    # permissive default, and no caller flag appears anywhere in this decision.
    resolution_allowed = False
    read_allowed = False
    write_allowed = False

    if status in BLOCKING_BINDING_STATUSES:
        blocked_reasons.append(f"binding_{status}_blocks_all_access")
    elif status == "unknown":
        blocked_reasons.append("binding_status_unknown")
    elif status == "unbound":
        blocked_reasons.append("no_binding_between_these_identities")
    elif status in DEMO_ONLY_BINDING_STATUSES:
        if demo_context:
            resolution_allowed = True
            read_allowed = is_read
            write_allowed = is_write
        else:
            blocked_reasons.append("demo_binding_cannot_reach_an_operational_surface")
    elif status in INSPECTION_ONLY_BINDING_STATUSES:
        if is_write:
            blocked_reasons.append("pending_review_binding_cannot_write")
        else:
            # Inspection is how a pending binding gets checked.
            resolution_allowed = True
            read_allowed = is_read
    elif status in OPERATIONAL_BINDING_STATUSES:
        if demo_context:
            # A verified binding is not a demo binding; running it in a demo
            # context is a mistake worth naming rather than quietly allowing.
            blocked_reasons.append("verified_binding_used_in_a_demo_context")
        else:
            resolution_allowed = True
            read_allowed = is_read
            write_allowed = is_write

    if op == "unknown":
        resolution_allowed = False
        read_allowed = False
        write_allowed = False

    # Risk is reported on the attempt, not only on the outcome.
    cross_tenant_risk = bool(
        (op in OPERATIONAL_OPERATIONS and not demo_context and status not in
         OPERATIONAL_BINDING_STATUSES)
        or status in BLOCKING_BINDING_STATUSES
    )
    if cross_tenant_risk and status != "conflict":
        blocked_reasons.append(
            f"operational_operation_without_a_verified_binding:{op}"
        )

    human_review_required = bool(
        cross_tenant_risk
        or status in {"pending_review", "conflict", "unknown"}
        or binding.get("human_review_required")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "binding_status": status,
            "binding_source": binding.get("binding_source"),
            "operation": op,
            "demo_context": bool(demo_context),
            "resolution_allowed": resolution_allowed,
            "read_allowed": read_allowed,
            "write_allowed": write_allowed,
            "cross_tenant_risk": cross_tenant_risk,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: the guard decides, it does not join or fetch anything.
            "records_joined": False,
            "identities_assumed_equivalent": False,
            "persisted": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def build_guard_matrix(
    *, bindings: list[dict[str, Any]], demo_context: bool = False
) -> dict[str, Any]:
    """Every binding against every operation. The whole decision surface."""
    rows: list[dict[str, Any]] = []
    for binding in bindings:
        for operation in sorted(OPERATIONS):
            rows.append(
                evaluate_resolution(
                    binding=binding, operation=operation, demo_context=demo_context
                )
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "demo_context": bool(demo_context),
            "rows": rows,
            "row_count": len(rows),
            "operations_allowed": sum(1 for r in rows if r["resolution_allowed"]),
            "operations_blocked": sum(
                1 for r in rows if not r["resolution_allowed"]
            ),
            "cross_tenant_risk_rows": sum(1 for r in rows if r["cross_tenant_risk"]),
            "writes_allowed": sum(1 for r in rows if r["write_allowed"]),
            "identities_assumed_equivalent": False,
            "fabricated": False,
        }
    )


def resolution_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"resolution_missing_field:{field}")

    for constant in (
        "records_joined",
        "identities_assumed_equivalent",
        "persisted",
        "fabricated",
        "live_fetch_performed",
    ):
        if result.get(constant) is not False:
            fails.append(f"resolution_claimed:{constant}")

    if result.get("operation") not in OPERATIONS:
        fails.append("operation_out_of_vocabulary")
    if result.get("binding_status") not in BINDING_STATUSES:
        fails.append("binding_status_out_of_vocabulary")

    status = result.get("binding_status")
    operation = result.get("operation")

    # Blocking statuses permit nothing, ever.
    if status in BLOCKING_BINDING_STATUSES:
        if result.get("resolution_allowed") or result.get("read_allowed") or (
            result.get("write_allowed")
        ):
            fails.append(f"binding_{status}_permitted_access")

    # Unbound permits no operational access.
    if status == "unbound" and (
        result.get("read_allowed") or result.get("write_allowed")
    ):
        fails.append("unbound_binding_permitted_access")

    # Pending review never writes.
    if status == "pending_review" and result.get("write_allowed"):
        fails.append("pending_review_binding_permitted_a_write")

    # A demo binding never reaches an operational surface.
    if (
        status == "demo_fixture"
        and not result.get("demo_context")
        and (result.get("read_allowed") or result.get("write_allowed"))
    ):
        fails.append("demo_binding_permitted_operational_access")

    # An operational write requires a verified binding.
    if result.get("write_allowed") and not result.get("demo_context"):
        if status not in OPERATIONAL_BINDING_STATUSES:
            fails.append("write_permitted_without_a_verified_binding")

    # Risk must be flagged on an operational attempt without verification.
    expected_risk = bool(
        (
            operation in OPERATIONAL_OPERATIONS
            and not result.get("demo_context")
            and status not in OPERATIONAL_BINDING_STATUSES
        )
        or status in BLOCKING_BINDING_STATUSES
    )
    if result.get("cross_tenant_risk") is not expected_risk:
        fails.append("cross_tenant_risk_disagrees_with_the_measurements")

    # Risk always routes to a person.
    if result.get("cross_tenant_risk") and not result.get("human_review_required"):
        fails.append("cross_tenant_risk_without_human_review")

    # A refusal must name itself.
    if not result.get("resolution_allowed") and not result.get("blocked_reasons"):
        fails.append("resolution_refused_without_a_reason")

    return fails
