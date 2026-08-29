"""Identity persistence safety guard (Gate 110D).

The last check before customer data is written under some identity.

## What this is for

Gate 109's resolution guard answers "may these two records be joined". This one
answers a narrower and later question: **given this identifier, may a row be
written at all.**

They are different questions with different failure modes. A bad join shows
somebody the wrong data. A bad write puts a Tribe's compliance record in a row
the database cannot protect, where it will sit until an audit finds it.

## The rule, in one line

A write is permitted only under an identifier the row-level security boundary can
enforce, and only once any label has been bound to it.

```text
organization_id   UUID    RLS authority              may persist
org_id            UUID    alias of the authority     may persist
org_id            string  a label wearing the name   blocked
customer_org_id   any     surface name, 0 columns    blocked without a binding
tenant_id         any     product label, 0 columns   blocked, always
demo values       any     nf-demo- prefixed          blocked, always
```

`tenant_id` is blocked even when a verified binding exists. The binding says
which organization the tenant corresponds to; the write must then use *that
organization's id*. Writing under the label with the binding merely "on file"
would leave a row RLS cannot see.

## Any ambiguity blocks the write

Derived affirmatively - permission requires the identity role contract to allow
persistence, the value to be UUID-shaped, the value to be non-demo, and any
binding requirement to be satisfied. There is no permissive default, and a
caller cannot pass a flag that grants anything.

An unrecognised operation blocks. An absent value blocks. A UUID-shaped
`tenant_id` blocks, because the name governs the authority question and the
shape only governs whether an already-eligible name may act.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    describe_identity_role,
)

SCHEMA_VERSION = "nf_identity_persistence_safety_guard_v1"

PERSIST_OPERATIONS = frozenset(
    {
        "awarded_grants_persist",
        "tenant_digest_persist",
        "document_library_persist",
        "source_watchlist_persist",
        "tenant_profile_persist",
        "beta_onboarding_persist",
        "unknown",
    }
)

# Every operation here writes customer data. There is no harmless one.
CUSTOMER_DATA_OPERATIONS = PERSIST_OPERATIONS - {"unknown"}

# Binding statuses that satisfy a binding requirement for an operational write.
OPERATIONAL_BINDING_STATUSES = frozenset({"verified_binding"})

RESULT_FIELDS: tuple[str, ...] = (
    "operation",
    "supplied_identity_name",
    "supplied_identity_value",
    "identity_role",
    "persistence_allowed",
    "rls_compatible",
    "binding_required",
    "binding_present",
    "write_allowed",
    "cross_tenant_risk",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_persistence_safety(
    *,
    operation: Any = None,
    identity_name: Any = None,
    identity_value: Any = None,
    binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """May customer data be written under this identity? Deny by default."""
    op = str(operation).strip() if operation else "unknown"
    if op not in PERSIST_OPERATIONS:
        op = "unknown"

    role = describe_identity_role(
        identity_name=identity_name, identity_value=identity_value
    )

    blocked_reasons: list[str] = []

    if op == "unknown":
        blocked_reasons.append("unrecognised_persist_operation")

    name = role["identity_name"]
    shape = role["shape"]

    if shape == "absent":
        blocked_reasons.append("identity_value_absent")
    if role["demo_allowed"]:
        blocked_reasons.append("demo_identity_cannot_persist_customer_data")
    if not role["persistence_allowed"]:
        blocked_reasons.append(f"identity_role_forbids_persistence:{name}:{shape}")

    # An RLS-compatible value is one the policies can actually match. Every
    # policy casts to ::uuid, so anything else cannot be enforced.
    rls_compatible = bool(role["persistence_allowed"]) and shape == "uuid"

    binding_required = bool(role["requires_binding"])
    binding_status = (binding or {}).get("binding_status")
    binding_present = binding_status in OPERATIONAL_BINDING_STATUSES

    if binding_required and not binding_present:
        blocked_reasons.append(f"binding_required_for:{name}")

    # Even a satisfied binding does not let a label carry the write. The
    # binding names the organization; the write must use that organization's id.
    if binding_required and binding_present and not rls_compatible:
        blocked_reasons.append(
            f"binding_resolves_to_an_organization_id_write_must_use_it:{name}"
        )

    write_allowed = bool(
        op in CUSTOMER_DATA_OPERATIONS
        and rls_compatible
        and not binding_required
        and not blocked_reasons
    )

    # Risk is reported on the attempt, not only the refusal.
    cross_tenant_risk = bool(
        op in CUSTOMER_DATA_OPERATIONS and not write_allowed
    ) or bool(role["demo_allowed"] and op in CUSTOMER_DATA_OPERATIONS)

    human_review_required = bool(cross_tenant_risk or blocked_reasons)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": op,
            "supplied_identity_name": name,
            "supplied_identity_value": identity_value,
            "identity_role": role["role"],
            "identity_shape": shape,
            "persistence_allowed": bool(role["persistence_allowed"]),
            "rls_compatible": rls_compatible,
            "binding_required": binding_required,
            "binding_present": binding_present,
            "binding_status": binding_status,
            "write_allowed": write_allowed,
            "cross_tenant_risk": cross_tenant_risk,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: the guard decides. It writes nothing and reaches nothing.
            "rows_written": 0,
            "persisted": False,
            "identities_assumed_equivalent": False,
            "fabricated": False,
            "live_fetch_performed": False,
        }
    )


def build_persistence_safety_matrix(
    *, identities: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Every identity against every persist operation."""
    identities = identities or [
        {
            "identity_name": "organization_id",
            "identity_value": "11111111-2222-3333-4444-555555555555",
        },
        {
            "identity_name": "org_id",
            "identity_value": "11111111-2222-3333-4444-555555555555",
        },
        {"identity_name": "org_id", "identity_value": "operator-org-alpha"},
        {"identity_name": "customer_org_id", "identity_value": "nf-demo-org-01"},
        {"identity_name": "tenant_id", "identity_value": "nf-demo-tenant-01"},
        {
            "identity_name": "tenant_id",
            "identity_value": "11111111-2222-3333-4444-555555555555",
        },
    ]

    rows: list[dict[str, Any]] = []
    for identity in identities:
        for operation in sorted(CUSTOMER_DATA_OPERATIONS):
            rows.append(
                evaluate_persistence_safety(operation=operation, **identity)
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rows": rows,
            "row_count": len(rows),
            "writes_allowed": sum(1 for r in rows if r["write_allowed"]),
            "writes_blocked": sum(1 for r in rows if not r["write_allowed"]),
            "cross_tenant_risk_rows": sum(1 for r in rows if r["cross_tenant_risk"]),
            "names_permitted_to_write": sorted(
                {r["supplied_identity_name"] for r in rows if r["write_allowed"]}
            ),
            "tenant_id_writes_allowed": sum(
                1
                for r in rows
                if r["supplied_identity_name"] == "tenant_id" and r["write_allowed"]
            ),
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def persistence_safety_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"persistence_result_missing_field:{field}")

    for constant in (
        "persisted",
        "identities_assumed_equivalent",
        "fabricated",
        "live_fetch_performed",
    ):
        if result.get(constant) is not False:
            fails.append(f"persistence_result_claimed:{constant}")
    if result.get("rows_written") != 0:
        fails.append("persistence_guard_wrote_rows")

    if result.get("operation") not in PERSIST_OPERATIONS:
        fails.append("persist_operation_out_of_vocabulary")

    name = result.get("supplied_identity_name")

    # tenant_id alone never persists operational customer data.
    if name == "tenant_id" and result.get("write_allowed"):
        fails.append("tenant_id_permitted_a_customer_data_write")

    # customer_org_id never persists without resolving to the authority.
    if name == "customer_org_id" and result.get("write_allowed"):
        fails.append("customer_org_id_permitted_a_write_without_the_authority")

    # A write requires an RLS-compatible identity.
    if result.get("write_allowed") and not result.get("rls_compatible"):
        fails.append("write_permitted_without_an_rls_compatible_identity")

    # A demo identity never writes customer data.
    if result.get("write_allowed") and str(
        result.get("supplied_identity_value") or ""
    ).lower().startswith(("nf-demo-", "demo-")):
        fails.append("demo_identity_permitted_a_customer_data_write")

    # An outstanding binding requirement blocks the write.
    if result.get("binding_required") and result.get("write_allowed"):
        fails.append("write_permitted_with_an_outstanding_binding_requirement")

    # Any blocked reason blocks the write.
    if result.get("blocked_reasons") and result.get("write_allowed"):
        fails.append("write_permitted_despite_blocked_reasons")

    # Risk must be flagged whenever a customer-data write was refused.
    if (
        result.get("operation") in CUSTOMER_DATA_OPERATIONS
        and not result.get("write_allowed")
        and not result.get("cross_tenant_risk")
    ):
        fails.append("refused_customer_data_write_without_flagging_risk")

    # Risk always routes to a person.
    if result.get("cross_tenant_risk") and not result.get("human_review_required"):
        fails.append("cross_tenant_risk_without_human_review")

    # A refusal must name itself.
    if not result.get("write_allowed") and not result.get("blocked_reasons"):
        fails.append("write_refused_without_a_reason")

    return fails
