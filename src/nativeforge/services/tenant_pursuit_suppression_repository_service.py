"""Gate 140D: suppression that survives a request.

`tenant_pursuit_suppression_service` has existed since Gate 104 with statuses,
reasons, an id builder and an `is_suppressed_for_tenant` the digest builder
already consults. Nothing ever wrote one down.

So *"once pursuit starts, the item disappears from future digests"* was true
inside a single call and false between them — the digest recomputed from
whatever list of suppressions a caller happened to hand it, and no caller had
one to hand.

## organization_id anchors; tenant_id is carried and never selects

The Gate 104 service keys its records on `tenant_id`, which Gates 109 through
113 settled is a label and never authority. This repository anchors every read
and write on `organization_id` — the column every RLS policy compares against —
and stores `tenant_id_label` beside it.

That is not a rename. It means a caller who knows another organization's tenant
label still cannot reach its suppressions, because the label is not what the
query is anchored on.

## Suppression retains

```sql
CHECK (source_history_preserved AND provenance_preserved)
```

Both columns are stored `NOT NULL` and the database requires both true. Hiding
an opportunity from a view must not be a way to make the source record go away,
and the row says so rather than a docstring saying so.

Lifting a suppression sets `lifted_at`; it deletes nothing. `rows_deleted` is a
constant `0` and there is no DELETE path.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.tenant_pursuit_suppression_service import (
    ACTIVE_SUPPRESSION_STATUSES,
    PURSUIT_BACKED_REASONS,
    SUPPRESSION_REASONS,
    SUPPRESSION_STATUSES,
    suppress_for_tenant,
)

SCHEMA_VERSION = "nf_tenant_pursuit_suppression_repository_v1"

TABLE_NAME = "nf_tenant_pursuit_suppressions"

FACT_STATUSES = frozenset(
    {"demo_fixture", "tenant_supplied", "verified", "needs_human_review", "unknown"}
)

FORBIDDEN_ANCHOR_NAMES: tuple[str, ...] = (
    "tenant_id",
    "customer_org_id",
    "organization_profile_id",
)

_METADATA = sa.MetaData()

SUPPRESSIONS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("tenant_id_label", sa.Text(), nullable=True),
    sa.Column("opportunity_id", sa.Text(), nullable=False),
    sa.Column("suppression_status", sa.String(length=48), nullable=False),
    sa.Column("suppression_reason", sa.String(length=48), nullable=False),
    sa.Column("pursuit_record_id", sa.Text(), nullable=True),
    sa.Column("audit_event_id", sa.Text(), nullable=True),
    sa.Column("source_history_preserved", sa.Boolean(), nullable=False),
    sa.Column("provenance_preserved", sa.Boolean(), nullable=False),
    sa.Column("visible_in_pipeline", sa.Boolean(), nullable=False),
    sa.Column("visible_in_awarded_workspace", sa.Boolean(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint(
        "source_history_preserved AND provenance_preserved",
        name=f"ck_{TABLE_NAME}_retains_the_record",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def record_suppression(
    *,
    connection: Any = None,
    organization_id: Any = None,
    opportunity_id: Any = None,
    suppression_reason: Any = None,
    pursuit_record_id: Any = None,
    audit_event_id: Any = None,
    suppress_from: Any = None,
    tenant_id_label: Any = None,
    created_by_identity_id: Any = None,
    fact_status: Any = "demo_fixture",
    is_demo: bool = True,
    suppression_id: uuid.UUID | None = None,
    now: datetime | None = None,
    human_review_acknowledged: bool = False,
    **offered: Any,
) -> dict[str, Any]:
    """Write one suppression, if the Gate 104 contract permits it.

    The decision is that service's, not this module's: it owns the vocabulary,
    the reason-to-status mapping and the human-review rule, and restating any of
    them here would give the two somewhere to disagree.
    """
    anchor = _as_uuid(organization_id)
    opportunity = str(opportunity_id or "").strip()
    moment = now or datetime.now(UTC)
    blocked: list[str] = []

    for key in FORBIDDEN_ANCHOR_NAMES:
        if str(offered.get(key) or "").strip():
            blocked.append(f"not_an_anchor_for_a_suppression:{key}")

    if anchor is None:
        blocked.append("suppression_without_an_organization_id_anchor")
    if not opportunity:
        blocked.append("suppression_without_an_opportunity_id")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    # The Gate 104 contract decides. `tenant_id` there is its in-memory key;
    # the organization id is what this row is anchored on.
    decision = suppress_for_tenant(
        tenant_id=str(anchor) if anchor else "",
        opportunity_id=opportunity,
        suppression_reason=suppression_reason,
        suppressed_at=moment.isoformat(),
        pursuit_record_id=pursuit_record_id,
        audit_event_id=audit_event_id,
        human_review_acknowledged=human_review_acknowledged,
        suppress_from=suppress_from,
    )
    blocked.extend(f"contract:{r}" for r in decision.get("blocked_reasons") or [])

    status = str(decision.get("suppression_status") or "unknown")
    reason = str(decision.get("suppression_reason") or "unknown")
    if status not in SUPPRESSION_STATUSES:
        blocked.append(f"suppression_status_not_recognised:{status}")
    if reason not in SUPPRESSION_REASONS:
        blocked.append(f"suppression_reason_not_recognised:{reason}")
    if reason in PURSUIT_BACKED_REASONS and not str(pursuit_record_id or "").strip():
        # A pursuit-backed reason claims a pursuit exists. Requiring the id is
        # what stops "we started pursuing it" from being a free assertion.
        blocked.append("pursuit_backed_reason_without_a_pursuit_record_id")

    facts = str(fact_status or "").strip().lower()
    if facts not in FACT_STATUSES:
        blocked.append(f"fact_status_not_recognised:{facts}")

    # One live suppression per organization and opportunity.
    if connection is not None and anchor is not None and opportunity:
        existing = int(
            connection.execute(
                sa.select(sa.func.count())
                .select_from(SUPPRESSIONS)
                .where(
                    SUPPRESSIONS.c.organization_id == anchor,
                    SUPPRESSIONS.c.opportunity_id == opportunity,
                    SUPPRESSIONS.c.lifted_at.is_(None),
                )
            ).scalar_one()
        )
        if existing:
            blocked.append("this_opportunity_is_already_suppressed_for_this_org")

    written = 0
    if not blocked:
        connection.execute(
            sa.insert(SUPPRESSIONS).values(
                id=suppression_id or uuid.uuid4(),
                organization_id=anchor,
                is_demo=bool(is_demo),
                tenant_id_label=str(tenant_id_label or "").strip() or None,
                opportunity_id=opportunity,
                suppression_status=status,
                suppression_reason=reason,
                pursuit_record_id=str(pursuit_record_id or "").strip() or None,
                audit_event_id=str(audit_event_id or "").strip() or None,
                # The contract's own values, and the CHECK requires both true.
                source_history_preserved=bool(
                    decision.get("source_history_preserved", True)
                ),
                provenance_preserved=bool(decision.get("provenance_preserved", True)),
                visible_in_pipeline=bool(decision.get("visible_in_pipeline")),
                visible_in_awarded_workspace=bool(
                    decision.get("visible_in_awarded_workspace")
                ),
                fact_status=facts,
                blocked_reasons=[],
                created_by_identity_id=_as_uuid(created_by_identity_id),
                suppressed_at=moment,
                created_at=moment,
                lifted_at=None,
            )
        )
        written = 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "record_suppression",
            "organization_id": str(anchor) if anchor else None,
            "opportunity_id": opportunity or None,
            "suppression_status": status,
            "suppression_reason": reason,
            "write_performed": bool(written),
            "rows_written": written,
            "rows_deleted": 0,
            "source_history_preserved": True,
            "provenance_preserved": True,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _row_to_record(row: Any) -> dict[str, Any]:
    """The shape `is_suppressed_for_tenant` reads.

    `tenant_id` is the ORGANIZATION id, because that is what this repository
    anchored on when it wrote the row. The Gate 104 service uses the field as
    an opaque key, so handing it the anchor keeps the two consistent without
    either pretending a tenant label is authority.
    """
    return {
        "suppression_id": str(row["id"]),
        "tenant_id": str(row["organization_id"]),
        "organization_id": str(row["organization_id"]),
        "tenant_id_label": row["tenant_id_label"],
        "opportunity_id": row["opportunity_id"],
        "suppression_status": row["suppression_status"],
        "suppression_reason": row["suppression_reason"],
        "pursuit_record_id": row["pursuit_record_id"],
        "audit_event_id": row["audit_event_id"],
        "source_history_preserved": bool(row["source_history_preserved"]),
        "provenance_preserved": bool(row["provenance_preserved"]),
        "visible_in_pipeline": bool(row["visible_in_pipeline"]),
        "visible_in_awarded_workspace": bool(row["visible_in_awarded_workspace"]),
        "suppressed_at": row["suppressed_at"].isoformat()
        if row["suppressed_at"]
        else None,
        "lifted_at": row["lifted_at"].isoformat() if row["lifted_at"] else None,
        "blocked_reasons": [],
    }


def list_suppressions(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_lifted: bool = False,
) -> dict[str, Any]:
    """Every suppression for one organization, anchored on organization_id."""
    anchor = _as_uuid(organization_id)
    blocked: list[str] = []
    if anchor is None:
        blocked.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_read")

    records: list[dict[str, Any]] = []
    if not blocked:
        query = sa.select(SUPPRESSIONS).where(SUPPRESSIONS.c.organization_id == anchor)
        if not include_lifted:
            query = query.where(SUPPRESSIONS.c.lifted_at.is_(None))
        records = [
            _row_to_record(row)
            for row in connection.execute(query.order_by(SUPPRESSIONS.c.opportunity_id))
            .mappings()
            .all()
        ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "list_suppressions",
            "organization_id": str(anchor) if anchor else None,
            "rows_read": len(records),
            "suppressions": records,
            "active_count": sum(
                1
                for record in records
                if record["suppression_status"] in ACTIVE_SUPPRESSION_STATUSES
                and not record["lifted_at"]
            ),
            "rows_deleted": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def lift_suppression(
    *,
    connection: Any = None,
    organization_id: Any = None,
    opportunity_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Stop suppressing. Sets `lifted_at`; deletes nothing."""
    anchor = _as_uuid(organization_id)
    opportunity = str(opportunity_id or "").strip()
    blocked: list[str] = []
    if anchor is None:
        blocked.append("lift_without_a_uuid_shaped_organization_id_anchor")
    if not opportunity:
        blocked.append("lift_without_an_opportunity_id")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if not blocked:
        result = connection.execute(
            sa.update(SUPPRESSIONS)
            .where(
                SUPPRESSIONS.c.organization_id == anchor,
                SUPPRESSIONS.c.opportunity_id == opportunity,
                SUPPRESSIONS.c.lifted_at.is_(None),
            )
            .values(lifted_at=now or datetime.now(UTC))
        )
        written = int(result.rowcount or 0)
        if not written:
            blocked.append("no_live_suppression_for_this_organization")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "lift_suppression",
            "organization_id": str(anchor) if anchor else None,
            "opportunity_id": opportunity or None,
            "write_performed": bool(written),
            "rows_written": written,
            "rows_deleted": 0,
            "source_history_preserved": True,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def suppression_repository_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("rows_deleted"):
        fails.append("a_suppression_was_deleted_rather_than_lifted")
    if result.get("rows_written") and result.get("blocked_reasons"):
        fails.append("wrote_a_suppression_alongside_blockers")

    if result.get("rows_written") and result.get("operation") == "record_suppression":
        if not result.get("source_history_preserved"):
            fails.append("suppression_did_not_preserve_the_source_history")
        if not result.get("provenance_preserved"):
            fails.append("suppression_did_not_preserve_the_provenance")

    for record in result.get("suppressions") or []:
        if not record.get("source_history_preserved"):
            fails.append(
                f"record_lost_the_source_history:{record.get('opportunity_id')}"
            )
        if not record.get("provenance_preserved"):
            fails.append(f"record_lost_the_provenance:{record.get('opportunity_id')}")

    return fails
