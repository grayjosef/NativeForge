"""Identity binding repository (Gate 120B).

The database boundary for `nf_tenant_customer_org_bindings`. Gate 113 built the
table and the contract that decides what may enter it; nothing has ever acted on
that decision, because nothing could address the table.

## What was missing, precisely

```python
# Gate 113, tenant_customer_org_binding_store_service
record = build_binding_record(...)
record["write_allowed"]   # True, and nothing consumes it
```

A permission nothing acts on is a permission nobody has tested. This module is
what consumes it.

## organization_id is the anchor, and labels never select

```text
organization_id    UUID, foreign key, the RLS predicate's left-hand side
tenant_id          text label. Narrows a read. Never selects one.
customer_org_id    text label. Same.
organization_profile_id  refused outright
```

Every read takes `organization_id` and applies labels as *additional* filters.
A read anchored on a label is a read the RLS policy cannot scope, which is a
cross-tenant read waiting for a second tenant to exist.

`organization_profile_id` is refused rather than ignored. It is a real value
from a real column in the wrong identity space — the specific substitution
Gates 110–113 exist to prevent — and silently dropping it would let a caller
believe it had been honoured.

## A verified binding names its verifier, and the database agrees

```text
verified_binding   verified_by_identity_id AND verified_at, both required
demo_fixture       both forbidden
pending_review     neither required
```

Migration 0029 enforces this with two CHECK constraints. This module enforces
it *before* the statement, so a caller gets a named refusal rather than an
`IntegrityError` — and the constraint is left in place as the thing that
catches the case this module gets wrong.

## Revocation is an UPDATE

Nothing here deletes. `revoke_binding` sets `revoked_at` and
`revoked_by_identity_id` and leaves the row. The partial unique index
(`WHERE revoked_at IS NULL`) is what makes that safe: a revoked row stops
blocking a replacement without disappearing from the audit trail.

`rows_deleted` is a constant `0` and an invariant refuses any result claiming
otherwise.

## Contract mode is the default

Without a connection nothing is written and nothing is read; the result
describes what *would* have happened and says `storage_allowed: False` with a
reason. Importing this module touches no database.

The `database` path is exercised against an isolated database in tests. It is
reached by nothing in the running application: no verifier identity can exist
while `customer_auth_live` is false, so no production verified binding is
constructible, let alone written.

```text
rows written in the application database   0
production verified bindings created       0
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_customer_org_binding_store_service import (
    BINDING_CONFIDENCES,
    BINDING_SOURCES,
    BINDING_STATUSES,
    FORBIDDEN_ANCHOR_NAMES,
    RLS_ANCHOR_COLUMN,
    STORABLE_BINDING_STATUSES,
    STORE_TABLE,
    VERIFIER_REQUIRED_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_customer_org_binding_repository_v1"

TABLE_NAME = STORE_TABLE

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_insert",
        "insert_binding",
        "get_active_binding",
        "list_bindings_for_organization",
        "revoke_binding",
        "mark_conflict",
    }
)

WRITE_OPERATIONS = frozenset({"insert_binding", "revoke_binding", "mark_conflict"})
READ_OPERATIONS = frozenset({"get_active_binding", "list_bindings_for_organization"})

# A demo binding is labelled, and the label is a column rather than a
# convention. Bridged from Gate 109.
DEMO_STATUS = "demo_fixture"

# A conflict is a binding that contradicts another. It is stored so somebody can
# look at it, and it authorizes nothing.
CONFLICT_STATUS = "conflict"

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "rls_anchor",
    "organization_id",
    "tenant_id",
    "customer_org_id",
    "binding_status",
    "binding_source",
    "binding_confidence",
    "verified_by_identity_id",
    "verified_at",
    "revoked_by_identity_id",
    "revoked_at",
    "human_review_required",
    "production_verified_binding",
    "demo_fixture",
    "storage_allowed",
    "write_performed",
    "read_performed",
    "rows_written",
    "rows_read",
    "rows_deleted",
    "blocked_reasons",
)

_METADATA = sa.MetaData()

# Mirrors migration 0029 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production and passed on writes the real database refuses.
# A test compares the two definitions by name so they cannot drift.
BINDINGS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text(), nullable=False),
    sa.Column("customer_org_id", sa.Text(), nullable=False),
    sa.Column("binding_status", sa.String(length=32), nullable=False),
    sa.Column("binding_source", sa.String(length=32), nullable=False),
    sa.Column("binding_confidence", sa.String(length=16), nullable=False),
    sa.Column("verified_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "binding_status IN ('unbound', 'pending_review', 'demo_fixture', "
        "'verified_binding', 'conflict', 'revoked', 'unknown')",
        name="ck_nf_binding_status",
    ),
    sa.CheckConstraint(
        "binding_source IN ('human_entered', 'admin_verified', "
        "'migration_import', 'demo_fixture', 'system_inferred_blocked', "
        "'unknown')",
        name="ck_nf_binding_source",
    ),
    sa.CheckConstraint(
        "binding_status <> 'verified_binding' OR ("
        "verified_at IS NOT NULL AND verified_by_identity_id IS NOT NULL)",
        name="ck_nf_binding_verified_needs_verifier",
    ),
    sa.CheckConstraint(
        "binding_status <> 'demo_fixture' OR ("
        "verified_at IS NULL AND verified_by_identity_id IS NULL)",
        name="ck_nf_binding_demo_has_no_verifier",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_shaped(value: Any) -> bool:
    """Can this survive the ``::uuid`` cast the RLS policy performs?"""
    try:
        uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _iso(moment: Any) -> str | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return aware.isoformat()
    return str(moment)


def _parse_moment(value: Any, *, fallback: datetime) -> datetime:
    """An ISO timestamp back into a datetime, or the fallback if unreadable."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return fallback
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _result(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "rls_anchor": RLS_ANCHOR_COLUMN,
        # Constants. This repository updates and inserts; it never deletes, and
        # a revoked binding is a row that stays.
        "rows_deleted": 0,
        "history_preserved": True,
        "real_customer_rows_written": 0,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    return _json_safe(out)


def prepare_insert(
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
    is_demo: bool = False,
    human_review_required: bool = True,
) -> dict[str, Any]:
    """Decide whether a row may be inserted. Touches no database.

    Separate from ``insert_binding`` on purpose: the decision is worth being
    able to ask for without a connection in hand, and a caller that wants only
    the verdict should not have to open a session to get one.
    """
    status = str(binding_status or "").strip().lower() or "unknown"
    source = str(binding_source or "").strip().lower() or "unknown"
    confidence = str(binding_confidence or "").strip().lower() or "none"

    blocked_reasons: list[str] = []

    # -- the anchor, and nothing else, decides whether this row is protectable
    if not str(organization_id or "").strip():
        blocked_reasons.append("binding_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # A profile id is a real value in the wrong identity space. Refused rather
    # than ignored: a caller that offered one should learn it was not honoured.
    if organization_profile_id:
        blocked_reasons.append(
            "organization_profile_id_is_not_an_organization_id_anchor"
        )

    # -- labels are required and are never the anchor
    if not str(tenant_id or "").strip():
        blocked_reasons.append("binding_without_a_tenant_label")
    if not str(customer_org_id or "").strip():
        blocked_reasons.append("binding_without_a_customer_org_label")

    # -- vocabulary, bridged from Gate 109 rather than restated
    if status not in BINDING_STATUSES:
        blocked_reasons.append(f"binding_status_not_recognised:{status}")
    elif status not in STORABLE_BINDING_STATUSES:
        blocked_reasons.append(f"binding_status_is_not_storable:{status}")
    if source not in BINDING_SOURCES:
        blocked_reasons.append(f"binding_source_not_recognised:{source}")
    if confidence not in BINDING_CONFIDENCES:
        blocked_reasons.append(f"binding_confidence_not_recognised:{confidence}")

    # -- the verifier pair, matching migration 0029's two CHECK constraints
    verifier_id = str(verified_by_identity_id or "").strip()
    verifier_at = str(verified_at or "").strip()
    has_verifier = bool(verifier_id and verifier_at)

    if status in VERIFIER_REQUIRED_STATUSES:
        if not verifier_id:
            blocked_reasons.append("verified_binding_without_a_verifier_identity")
        elif not _uuid_shaped(verifier_id):
            blocked_reasons.append("verifier_identity_is_not_uuid_shaped")
        if not verifier_at:
            blocked_reasons.append("verified_binding_without_a_verified_at")

    demo_fixture = bool(is_demo or status == DEMO_STATUS)
    if demo_fixture and has_verifier:
        # A fixture carrying a verifier is a fixture impersonating production
        # verification. The database refuses it too.
        blocked_reasons.append("demo_fixture_binding_cannot_carry_a_verifier")
    if demo_fixture and status in VERIFIER_REQUIRED_STATUSES:
        blocked_reasons.append("demo_fixture_cannot_be_a_verified_binding")

    if status == CONFLICT_STATUS:
        # Stored so somebody can look at it. It authorizes nothing.
        blocked_reasons.append("conflict_binding_authorizes_no_operational_write")

    storage_allowed = not blocked_reasons
    production_verified = bool(
        storage_allowed
        and status in VERIFIER_REQUIRED_STATUSES
        and has_verifier
        and not demo_fixture
    )

    return _result(
        operation="prepare_insert",
        organization_id=str(organization_id or "") or None,
        tenant_id=str(tenant_id or "") or None,
        customer_org_id=str(customer_org_id or "") or None,
        binding_status=status,
        binding_source=source,
        binding_confidence=confidence,
        verified_by_identity_id=verifier_id or None,
        verified_at=verifier_at or None,
        revoked_by_identity_id=None,
        revoked_at=None,
        human_review_required=bool(human_review_required),
        production_verified_binding=production_verified,
        demo_fixture=demo_fixture,
        storage_allowed=storage_allowed,
        write_performed=False,
        read_performed=False,
        rows_written=0,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def insert_binding(
    *,
    connection: Any = None,
    binding_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert one binding, if ``prepare_insert`` permits it.

    Without a connection nothing is written and the result says so. The decision
    is made by ``prepare_insert`` rather than duplicated here, so the two can
    never disagree about what is storable.
    """
    decision = prepare_insert(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if decision["storage_allowed"] and connection is not None:
        moment = created_at or datetime.now(UTC)
        connection.execute(
            sa.insert(BINDINGS).values(
                id=binding_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                tenant_id=str(decision["tenant_id"]),
                customer_org_id=str(decision["customer_org_id"]),
                binding_status=decision["binding_status"],
                binding_source=decision["binding_source"],
                binding_confidence=decision["binding_confidence"],
                verified_by_identity_id=_as_uuid(decision["verified_by_identity_id"]),
                # The caller's timestamp, not this call's. When a binding was
                # verified is a fact about the verification, not about the
                # moment somebody got around to writing the row.
                verified_at=(
                    _parse_moment(decision["verified_at"], fallback=moment)
                    if decision["verified_by_identity_id"]
                    else None
                ),
                revoked_at=None,
                revoked_by_identity_id=None,
                is_demo=bool(decision["demo_fixture"]),
                human_review_required=bool(decision["human_review_required"]),
                blocked_reasons=[],
                created_at=moment,
                updated_at=moment,
            )
        )
        written = 1

    return _result(
        **{
            **decision,
            "operation": "insert_binding",
            "storage_allowed": bool(decision["storage_allowed"]),
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "organization_id": str(row["organization_id"]),
        "tenant_id": row["tenant_id"],
        "customer_org_id": row["customer_org_id"],
        "binding_status": row["binding_status"],
        "binding_source": row["binding_source"],
        "binding_confidence": row["binding_confidence"],
        "verified_by_identity_id": (
            str(row["verified_by_identity_id"])
            if row["verified_by_identity_id"]
            else None
        ),
        "verified_at": _iso(row["verified_at"]),
        "revoked_at": _iso(row["revoked_at"]),
        "revoked_by_identity_id": (
            str(row["revoked_by_identity_id"])
            if row["revoked_by_identity_id"]
            else None
        ),
        "demo_fixture": bool(row["is_demo"]),
        "human_review_required": bool(row["human_review_required"]),
    }


def _anchored_select(organization_id: Any) -> Any:
    return sa.select(BINDINGS).where(
        BINDINGS.c.organization_id == _as_uuid(organization_id)
    )


def get_active_binding(
    *,
    connection: Any = None,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
) -> dict[str, Any]:
    """The one live binding for an organization and a label pair.

    Anchored on ``organization_id``. The labels narrow; they never select on
    their own, because a read anchored on a label is a read the RLS policy
    cannot scope.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = _anchored_select(organization_id).where(BINDINGS.c.revoked_at.is_(None))
        if str(tenant_id or "").strip():
            query = query.where(BINDINGS.c.tenant_id == str(tenant_id).strip())
        if str(customer_org_id or "").strip():
            query = query.where(
                BINDINGS.c.customer_org_id == str(customer_org_id).strip()
            )
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_active_binding_for_this_organization")

    facts = _row_to_facts(row) if row is not None else {}
    production_verified = bool(
        row is not None
        and facts["binding_status"] in VERIFIER_REQUIRED_STATUSES
        and facts["verified_by_identity_id"]
        and facts["verified_at"]
        and not facts["demo_fixture"]
    )

    return _result(
        operation="get_active_binding",
        organization_id=str(organization_id or "") or None,
        tenant_id=facts.get("tenant_id") or (str(tenant_id or "") or None),
        customer_org_id=(
            facts.get("customer_org_id") or (str(customer_org_id or "") or None)
        ),
        binding_status=facts.get("binding_status"),
        binding_source=facts.get("binding_source"),
        binding_confidence=facts.get("binding_confidence"),
        verified_by_identity_id=facts.get("verified_by_identity_id"),
        verified_at=facts.get("verified_at"),
        revoked_by_identity_id=facts.get("revoked_by_identity_id"),
        revoked_at=facts.get("revoked_at"),
        human_review_required=bool(facts.get("human_review_required", True)),
        production_verified_binding=production_verified,
        demo_fixture=bool(facts.get("demo_fixture", False)),
        storage_allowed=False,
        write_performed=False,
        read_performed=row is not None,
        rows_written=0,
        rows_read=1 if row is not None else 0,
        blocked_reasons=blocked_reasons,
    )


def list_bindings_for_organization(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_revoked: bool = True,
) -> dict[str, Any]:
    """Every binding for one organization, revoked ones included by default.

    Revoked rows are returned because they are the audit trail. A listing that
    hid them would make a revocation indistinguishable from a row that never
    existed.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        query = _anchored_select(organization_id)
        if not include_revoked:
            query = query.where(BINDINGS.c.revoked_at.is_(None))
        rows = [
            _row_to_facts(row)
            for row in connection.execute(
                query.order_by(BINDINGS.c.created_at)
            ).mappings()
        ]

    result = _result(
        operation="list_bindings_for_organization",
        organization_id=str(organization_id or "") or None,
        tenant_id=None,
        customer_org_id=None,
        binding_status=None,
        binding_source=None,
        binding_confidence=None,
        verified_by_identity_id=None,
        verified_at=None,
        revoked_by_identity_id=None,
        revoked_at=None,
        human_review_required=True,
        production_verified_binding=any(
            r["binding_status"] in VERIFIER_REQUIRED_STATUSES
            and r["verified_by_identity_id"]
            and not r["demo_fixture"]
            for r in rows
        ),
        demo_fixture=all(r["demo_fixture"] for r in rows) if rows else False,
        storage_allowed=False,
        write_performed=False,
        read_performed=bool(rows),
        rows_written=0,
        rows_read=len(rows),
        blocked_reasons=blocked_reasons,
    )
    result["bindings"] = rows
    result["revoked_count"] = sum(1 for r in rows if r["revoked_at"])
    return _json_safe(result)


def revoke_binding(
    *,
    connection: Any = None,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    revoked_by_identity_id: Any = None,
    revoked_at: datetime | None = None,
) -> dict[str, Any]:
    """Withdraw a binding. An UPDATE, never a DELETE.

    The row stays, `revoked_at` is set, and the partial unique index stops
    treating it as the live binding for its label pair — so a replacement can be
    created without the history disappearing.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("revocation_without_a_uuid_shaped_anchor")
    if not str(revoked_by_identity_id or "").strip():
        blocked_reasons.append("revocation_without_a_revoker_identity")
    elif not _uuid_shaped(revoked_by_identity_id):
        blocked_reasons.append("revoker_identity_is_not_uuid_shaped")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = revoked_at or datetime.now(UTC)
    written = 0
    if not blocked_reasons:
        query = _anchored_select(organization_id).where(BINDINGS.c.revoked_at.is_(None))
        if str(tenant_id or "").strip():
            query = query.where(BINDINGS.c.tenant_id == str(tenant_id).strip())
        if str(customer_org_id or "").strip():
            query = query.where(
                BINDINGS.c.customer_org_id == str(customer_org_id).strip()
            )
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_active_binding_to_revoke")
        else:
            connection.execute(
                sa.update(BINDINGS)
                .where(BINDINGS.c.id == row["id"])
                .values(
                    binding_status="revoked",
                    revoked_at=moment,
                    revoked_by_identity_id=_as_uuid(revoked_by_identity_id),
                    human_review_required=True,
                    updated_at=moment,
                )
            )
            written = 1

    return _result(
        operation="revoke_binding",
        organization_id=str(organization_id or "") or None,
        tenant_id=str(tenant_id or "") or None,
        customer_org_id=str(customer_org_id or "") or None,
        binding_status="revoked" if written else None,
        binding_source=None,
        binding_confidence=None,
        verified_by_identity_id=None,
        verified_at=None,
        revoked_by_identity_id=str(revoked_by_identity_id or "") or None,
        revoked_at=_iso(moment) if written else None,
        human_review_required=True,
        # A revoked binding is not a verified one, whatever it was before.
        production_verified_binding=False,
        demo_fixture=False,
        storage_allowed=not blocked_reasons,
        write_performed=bool(written),
        read_performed=False,
        rows_written=written,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def mark_conflict(
    *,
    connection: Any = None,
    organization_id: Any = None,
    tenant_id: Any = None,
    customer_org_id: Any = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    """Flag a binding as contradicted. It then authorizes nothing.

    A conflict is not a revocation: the binding is still the live row for its
    label pair, and somebody has to look at it. `human_review_required` goes
    true and stays true.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("conflict_without_a_uuid_shaped_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = updated_at or datetime.now(UTC)
    written = 0
    if not blocked_reasons:
        query = _anchored_select(organization_id).where(BINDINGS.c.revoked_at.is_(None))
        if str(tenant_id or "").strip():
            query = query.where(BINDINGS.c.tenant_id == str(tenant_id).strip())
        if str(customer_org_id or "").strip():
            query = query.where(
                BINDINGS.c.customer_org_id == str(customer_org_id).strip()
            )
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_active_binding_to_mark_as_conflicting")
        else:
            connection.execute(
                sa.update(BINDINGS)
                .where(BINDINGS.c.id == row["id"])
                .values(
                    binding_status=CONFLICT_STATUS,
                    # A conflicting row can no longer name a verifier: whatever
                    # it asserted is exactly what is in dispute.
                    verified_by_identity_id=None,
                    verified_at=None,
                    human_review_required=True,
                    updated_at=moment,
                )
            )
            written = 1

    return _result(
        operation="mark_conflict",
        organization_id=str(organization_id or "") or None,
        tenant_id=str(tenant_id or "") or None,
        customer_org_id=str(customer_org_id or "") or None,
        binding_status=CONFLICT_STATUS if written else None,
        binding_source=None,
        binding_confidence=None,
        verified_by_identity_id=None,
        verified_at=None,
        revoked_by_identity_id=None,
        revoked_at=None,
        human_review_required=True,
        production_verified_binding=False,
        demo_fixture=False,
        storage_allowed=not blocked_reasons,
        write_performed=bool(written),
        read_performed=False,
        rows_written=written,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def binding_repository_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this repository must never be able to produce."""
    failures: list[str] = []

    operation = str(result.get("operation") or "")
    if operation not in REPOSITORY_OPERATIONS:
        failures.append("operation_outside_vocabulary")

    if result.get("rls_anchor") != RLS_ANCHOR_COLUMN:
        failures.append("rls_anchor_is_not_organization_id")

    for name in sorted(FORBIDDEN_ANCHOR_NAMES):
        if result.get(f"{name}_anchor") or result.get(f"anchored_on_{name}"):
            failures.append(f"anchored_on_a_label:{name}")

    if result.get("rows_deleted"):
        failures.append("a_binding_row_was_deleted")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("write_performed") and operation not in WRITE_OPERATIONS:
        failures.append("a_read_operation_reported_a_write")

    if result.get("rows_written") and not result.get("write_performed"):
        failures.append("rows_written_without_a_write")

    if result.get("write_performed") and not result.get("storage_allowed"):
        failures.append("a_write_happened_without_storage_being_allowed")

    if result.get("storage_allowed") and result.get("blocked_reasons"):
        # A write path with a named refusal on it is not a write path. The
        # connection-absent case is a refusal of the write, not of the row.
        remaining = [
            reason
            for reason in result["blocked_reasons"]
            if not reason.startswith("no_connection_supplied")
        ]
        if remaining:
            failures.append("storage_allowed_with_blocked_reasons_present")

    status = str(result.get("binding_status") or "")
    verified = bool(result.get("verified_by_identity_id"))
    if status in VERIFIER_REQUIRED_STATUSES and result.get("storage_allowed"):
        if not verified:
            failures.append("verified_binding_permitted_without_a_verifier")
        if not result.get("verified_at"):
            failures.append("verified_binding_permitted_without_a_verified_at")

    if result.get("demo_fixture") and result.get("production_verified_binding"):
        failures.append("a_demo_fixture_claimed_a_production_verified_binding")

    if result.get("production_verified_binding") and not verified:
        failures.append("production_verified_binding_without_a_verifier")

    if status == CONFLICT_STATUS and result.get("production_verified_binding"):
        failures.append("a_conflicting_binding_claimed_verification")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))
