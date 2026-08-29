"""Tenant / customer org binding store (Gate 113C).

Turning a Gate 109 binding into a row the database can protect — or refusing.

## Anchored on organization_id, because that is what RLS enforces

```text
organization_id   UUID FK organizations.id   the anchor, and the RLS key
tenant_id         text                        a label
customer_org_id   text                        a label
```

Gate 110 proved `organization_id` is the only identity this database enforces on.
A binding keyed on a label would be a record row-level security cannot see, in a
table whose entire purpose is preventing cross-tenant access.

So a write needs an `organization_id` and nothing else will substitute:

```text
tenant_id alone            refused
customer_org_id alone      refused
organization_profile_id    refused outright - it is not an organization id
a non-UUID organization_id refused; it cannot survive the ::uuid cast
```

## The store never verifies; it records what a verifier decided

`verified_binding` requires both `verified_by_identity_id` and `verified_at`, and
the schema enforces it too (`ck_nf_binding_verified_needs_verifier`). A binding
that says "verified" without naming who and when is an assertion wearing the
word.

Gate 111's `verified_binder_authorization_service` decides *whether* somebody may
verify. This records the outcome. Neither does the other's job.

## Demo bindings never carry a verifier

`ck_nf_binding_demo_has_no_verifier` in the schema, and refused here before it
gets that far. A demo binding is not production verification, and the cheapest
way to keep that true is to make the verifier columns unreachable for it.

## Revocation preserves

`revoke_binding` sets `revoked_at` and a revoking identity. It deletes nothing.
The unique index is partial — `WHERE revoked_at IS NULL` — so a revoked row stays
for the audit trail without blocking a replacement.

## Reads are anchored too

`read_bindings_for_organization` takes an `organization_id`. Reading *by* a
tenant label is supported only alongside the anchor, because a label is not
unique across organizations and a lookup that ignores the anchor is a
cross-tenant read waiting to happen.

## Nothing here writes

This service builds and validates records. It performs no INSERT, and
`rows_written` is a constant `0`. Persistence is not live; when it becomes live,
this is the shape the rows must already have.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    classify_identity_value_shape,
    is_demo_identity_value,
)
from nativeforge.services.tenant_customer_org_identity_binding_service import (
    BINDING_CONFIDENCES,
    BINDING_SOURCES,
    BINDING_STATUSES,
    DEMO_LABEL,
    VERIFYING_SOURCES,
)

SCHEMA_VERSION = "nf_tenant_customer_org_binding_store_v1"

STORE_TABLE = "nf_tenant_customer_org_bindings"

# The only column the store may be anchored or scoped on.
RLS_ANCHOR_COLUMN = "organization_id"

# Identity names that may never anchor a stored binding.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {"tenant_id", "customer_org_id", "organization_profile_id"}
)

# Statuses that may be written at all. `unbound` and `unknown` describe the
# absence of a binding; storing one would be storing a non-fact.
STORABLE_BINDING_STATUSES = frozenset(
    {"pending_review", "demo_fixture", "verified_binding", "conflict", "revoked"}
)

# The only status requiring a verifier, and the only one that may carry one.
VERIFIER_REQUIRED_STATUSES = frozenset({"verified_binding"})

RECORD_FIELDS: tuple[str, ...] = (
    "binding_id",
    "organization_id",
    "tenant_id",
    "customer_org_id",
    "binding_status",
    "binding_source",
    "verified_by_identity_id",
    "verified_at",
    "storage_allowed",
    "read_allowed",
    "write_allowed",
    "rls_anchor",
    "human_review_required",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_stored_binding_id(
    *, organization_id: Any, tenant_id: Any, customer_org_id: Any
) -> str:
    """Deterministic, and anchored by construction."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (organization_id, tenant_id, customer_org_id)
        ).encode()
    ).hexdigest()


def build_binding_record(
    *,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    organization_profile_id: Any = None,
    binding_status: Any = None,
    binding_source: Any = None,
    binding_confidence: Any = None,
    verified_by_identity_id: Any = None,
    verified_at: Any = None,
    revoked_at: Any = None,
    revoked_by_identity_id: Any = None,
    is_demo: bool = False,
    demo_label: Any = None,
    created_at: Any = None,
    updated_at: Any = None,
) -> dict[str, Any]:
    """A binding shaped for the store, or a refusal saying why not."""
    status = _norm(binding_status, BINDING_STATUSES, fallback="unknown")
    source = _norm(binding_source, BINDING_SOURCES, fallback="unknown")
    confidence = _norm(binding_confidence, BINDING_CONFIDENCES, fallback="none")

    blocked_reasons: list[str] = []

    anchor_shape = classify_identity_value_shape(organization_id)
    anchor_is_demo = is_demo_identity_value(organization_id)

    # The anchor, and nothing else, decides whether this row can be protected.
    if anchor_shape == "absent":
        blocked_reasons.append("binding_without_an_organization_id_anchor")
    elif anchor_shape != "uuid":
        blocked_reasons.append(
            f"organization_id_anchor_is_not_a_uuid:{anchor_shape}"
        )
    if anchor_is_demo:
        blocked_reasons.append("demo_identity_cannot_anchor_a_stored_binding")

    # A profile id is not an organization id, and offering one as the anchor is
    # the specific substitution this store exists to refuse.
    if organization_profile_id:
        blocked_reasons.append(
            "organization_profile_id_is_not_an_organization_id_anchor"
        )

    if not str(tenant_id or "").strip():
        blocked_reasons.append("binding_without_a_tenant_label")
    if not str(customer_org_id or "").strip():
        blocked_reasons.append("binding_without_a_customer_org_label")

    if status not in STORABLE_BINDING_STATUSES:
        blocked_reasons.append(f"binding_status_is_not_storable:{status}")

    # A verified binding names its verifier and when.
    has_verifier = bool(
        str(verified_by_identity_id or "").strip()
        and str(verified_at or "").strip()
    )
    if status in VERIFIER_REQUIRED_STATUSES:
        if not has_verifier:
            blocked_reasons.append("verified_binding_without_a_verifier_identity")
        if source not in VERIFYING_SOURCES:
            blocked_reasons.append(f"source_cannot_verify_a_binding:{source}")

    # A demo binding never carries one.
    demo_binding = status == "demo_fixture" or source == "demo_fixture" or is_demo
    if demo_binding:
        if has_verifier:
            blocked_reasons.append("demo_binding_cannot_carry_a_verifier")
        if str(demo_label or "").strip() != DEMO_LABEL:
            blocked_reasons.append("demo_binding_without_its_label")

    revoked = bool(str(revoked_at or "").strip())

    # A conflict blocks both directions: a pair that cannot be right must not be
    # read as though it were. Recorded *before* permission is derived, so the
    # reason is part of what the derivation sees rather than appended after it.
    if status == "conflict":
        blocked_reasons.append("conflict_binding_blocks_reads_and_writes")

    # Derived affirmatively. Every condition must hold; nothing is subtracted
    # from a permissive default and no caller flag grants anything.
    storage_allowed = bool(
        anchor_shape == "uuid"
        and not anchor_is_demo
        and not organization_profile_id
        and status in STORABLE_BINDING_STATUSES
        and str(tenant_id or "").strip()
        and str(customer_org_id or "").strip()
        and not blocked_reasons
    )
    write_allowed = storage_allowed and not revoked
    read_allowed = bool(anchor_shape == "uuid" and not blocked_reasons)

    human_review_required = bool(
        blocked_reasons or status in {"pending_review", "conflict"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "store_table": STORE_TABLE,
            "binding_id": build_stored_binding_id(
                organization_id=organization_id,
                tenant_id=tenant_id,
                customer_org_id=customer_org_id,
            ),
            "organization_id": organization_id,
            "organization_id_shape": anchor_shape,
            # Labels. Recorded, never anchoring.
            "tenant_id": tenant_id,
            "customer_org_id": customer_org_id,
            "binding_status": status,
            "binding_source": source,
            "binding_confidence": confidence,
            "verified_by_identity_id": verified_by_identity_id
            if status in VERIFIER_REQUIRED_STATUSES
            else None,
            "verified_at": verified_at
            if status in VERIFIER_REQUIRED_STATUSES
            else None,
            "revoked_at": revoked_at,
            "revoked_by_identity_id": revoked_by_identity_id,
            "is_demo": bool(is_demo or demo_binding),
            "demo_label": demo_label if demo_binding else None,
            "created_at": created_at,
            "updated_at": updated_at,
            "storage_allowed": storage_allowed,
            "read_allowed": read_allowed,
            "write_allowed": write_allowed,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this shapes a row. It writes none.
            "rows_written": 0,
            "persisted": False,
            "customer_persistence_live": False,
            "tenant_id_is_rls_anchor": False,
            "customer_org_id_is_rls_anchor": False,
            "fabricated": False,
        }
    )


def revoke_binding(
    *, record: dict[str, Any], revoked_at: Any, revoked_by_identity_id: Any = None
) -> dict[str, Any]:
    """Withdraw a binding. Nothing is deleted and the history stays."""
    blocked_reasons = list(record.get("blocked_reasons") or [])
    if not str(revoked_at or "").strip():
        blocked_reasons.append("revocation_without_a_timestamp")

    return _json_safe(
        {
            **record,
            "binding_status": "revoked",
            "revoked_at": revoked_at,
            "revoked_by_identity_id": revoked_by_identity_id,
            "write_allowed": False,
            "human_review_required": True,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # The row remains; only its status changes.
            "rows_deleted": 0,
            "history_preserved": True,
            "verified_by_identity_id": record.get("verified_by_identity_id"),
            "verified_at": record.get("verified_at"),
        }
    )


def read_bindings_for_organization(
    *,
    organization_id: Any,
    records: list[dict[str, Any]] | None = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
) -> dict[str, Any]:
    """Read anchored on organization_id. Labels narrow, they never select."""
    blocked_reasons: list[str] = []
    anchor_shape = classify_identity_value_shape(organization_id)
    if anchor_shape != "uuid":
        blocked_reasons.append(f"read_without_a_uuid_anchor:{anchor_shape}")

    matched: list[dict[str, Any]] = []
    if anchor_shape == "uuid":
        for record in records or []:
            if str(record.get("organization_id") or "") != str(organization_id):
                continue
            if tenant_id and str(record.get("tenant_id") or "") != str(tenant_id):
                continue
            if customer_org_id and str(record.get("customer_org_id") or "") != str(
                customer_org_id
            ):
                continue
            matched.append(record)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "organization_id_shape": anchor_shape,
            "tenant_id_filter": tenant_id,
            "customer_org_id_filter": customer_org_id,
            "records": matched,
            "record_count": len(matched),
            "read_allowed": anchor_shape == "uuid" and not blocked_reasons,
            "rls_anchor": RLS_ANCHOR_COLUMN,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "rows_written": 0,
            "persisted": False,
            "fabricated": False,
        }
    )


def binding_store_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RECORD_FIELDS:
        if field not in record:
            fails.append(f"binding_record_missing_field:{field}")

    for constant in (
        "persisted",
        "customer_persistence_live",
        "tenant_id_is_rls_anchor",
        "customer_org_id_is_rls_anchor",
        "fabricated",
    ):
        if record.get(constant) is not False:
            fails.append(f"binding_record_claimed:{constant}")
    if record.get("rows_written") != 0:
        fails.append("binding_store_wrote_rows")

    if record.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        fails.append("binding_record_anchored_on_the_wrong_column")
    if record.get("binding_status") not in BINDING_STATUSES:
        fails.append("binding_status_out_of_vocabulary")
    if record.get("binding_source") not in BINDING_SOURCES:
        fails.append("binding_source_out_of_vocabulary")

    status = record.get("binding_status")

    # Storage requires a UUID anchor, always.
    if record.get("storage_allowed"):
        if record.get("organization_id_shape") != "uuid":
            fails.append("storage_permitted_without_a_uuid_organization_id")
        if record.get("blocked_reasons"):
            fails.append("storage_permitted_despite_blocked_reasons")

    # A verified binding names its verifier and when.
    #
    # Scoped to records that claim they may be stored. A record correctly
    # refused for lacking a verifier already carries a blocked reason, and an
    # invariant that also fired on it would be flagging correct behaviour -
    # which teaches people to ignore invariants.
    if status == "verified_binding" and (
        record.get("storage_allowed") or record.get("write_allowed")
    ):
        if not (
            record.get("verified_by_identity_id") and record.get("verified_at")
        ):
            fails.append("stored_verified_binding_without_a_verifier")
        if record.get("binding_source") not in VERIFYING_SOURCES:
            fails.append("stored_verified_binding_from_a_source_that_cannot_verify")

    # A demo binding never carries a verifier.
    if status == "demo_fixture" and (
        record.get("verified_by_identity_id") or record.get("verified_at")
    ):
        fails.append("stored_demo_binding_carried_a_verifier")

    # A conflict is readable by nobody.
    if status == "conflict" and (
        record.get("read_allowed") or record.get("write_allowed")
    ):
        fails.append("conflict_binding_permitted_access")

    # A revoked binding never writes.
    if record.get("revoked_at") and record.get("write_allowed"):
        fails.append("revoked_binding_permitted_a_write")

    # Identity reproducible from the record's own fields.
    expected = build_stored_binding_id(
        organization_id=record.get("organization_id"),
        tenant_id=record.get("tenant_id"),
        customer_org_id=record.get("customer_org_id"),
    )
    if record.get("binding_id") != expected:
        fails.append("binding_id_not_derivable_from_its_fields")

    # A refusal must name itself.
    if not record.get("storage_allowed") and not record.get("blocked_reasons"):
        fails.append("storage_refused_without_a_reason")

    return fails
