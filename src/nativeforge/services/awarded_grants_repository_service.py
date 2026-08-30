"""Awarded grants repository (Gate 124C).

The database boundary for `nf_awarded_grants`, anchored on `organization_id`.

## What was missing

Gate 91 separated pursuit from award. Gate 108 built requirement tracking,
calendars and proof audit. Nine services, roughly 3,800 lines, and Gate 124A
found no table — every one of them produces a dictionary and none has anywhere
to put it.

## An award is not a pursuit, and lineage is not a cause

```text
source_pursuit_id       text, no foreign key. Where it came from.
source_opportunity_id   text, no foreign key. Same.
```

No foreign key, deliberately: a foreign key would make a pursuit's existence a
precondition for an award, and awards arrive for things nobody pursued in this
system.

They are also never a reason to create a row. A pursuit reaching "submitted"
produces nothing here; a human recording an award does.
`award_created_from_lineage` is a constant `False` and an invariant refuses any
result claiming otherwise.

## A projected burden is not an active obligation

Gate 91's `pursuit_reporting_burden_projection_service` prefixes every field
`projected_` and stamps every result `is_active_obligation: False`. This
repository is the other end of that refusal.

`active_obligation_status` is its own column. It is never derived from a
projection, never derived from the award's own status, and reaching
`obligations_established` requires *three* separate things:

```text
fact_status in {verified, tenant_supplied}   somebody established the award
extraction in {human_entered,                somebody established the
               evidence_extracted}           requirements
award_status in {active_award,               the award is actually live
                 closeout_pending}
```

The database enforces the first
(`ck_nf_awarded_grants_obligations_need_established_facts`); the validation
service enforces all three; and an invariant refuses a result that claims the
obligation without them.

## organization_id anchors; everything else is a label

```text
organization_id          UUID, foreign key, the RLS predicate's left side
tenant_beta_profile_id   optional context. Not authority.
tenant_id_label          text, no foreign key
customer_org_id_label    text, no foreign key
organization_profile_id  refused outright
```

`tenant_beta_profile_id` is the interesting one. It is a real foreign key to a
real table and it is still not an anchor: an award belongs to an *organization*,
and a beta profile is how that organization wants to be served. If the profile
is archived the award remains, which is why the FK is `ON DELETE SET NULL`.

## Archive, never delete

`archive_awarded_grant` sets `archived_at` and leaves the row. `rows_deleted` is
a constant `0` and there is no DELETE path.

`mistaken_award` is a *status*, not a deletion. An award recorded and later found
not to exist is a fact about what happened, and a funder's audit does not accept
"we removed it".

## Production writes need two things that are both false

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable so the permitted branch is reachable in a test, both false in
reality. An award row is an obligation to a real funder; writing one while
nobody can be authenticated as the tenant it binds is the worst version of the
fabricated-fact problem this campaign keeps refusing.

```text
rows in the application database    0
production awarded grants created   0
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa

from nativeforge.services.awarded_grant_record_service import (
    AWARD_STATUSES,
    LIVE_AWARD_STATUSES,
    OBLIGATION_CAPABLE_EXTRACTION,
    REQUIREMENTS_EXTRACTION_STATUSES,
)
from nativeforge.services.awarded_grants_persistence_validation_service import (
    ACTIVE_OBLIGATION_STATUSES,
    OBLIGATING_STATUSES,
    validate_awarded_grant,
)
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
)

SCHEMA_VERSION = "nf_awarded_grants_repository_v1"

TABLE_NAME = "nf_awarded_grants"

RLS_ANCHOR_COLUMN = "organization_id"

REPOSITORY_OPERATIONS = frozenset(
    {
        "prepare_award_write",
        "create_awarded_grant",
        "get_awarded_grant",
        "list_awarded_grants",
        "archive_awarded_grant",
        "validate_award_persistence",
    }
)

WRITE_OPERATIONS = frozenset({"create_awarded_grant", "archive_awarded_grant"})
READ_OPERATIONS = frozenset({"get_awarded_grant", "list_awarded_grants"})

# Names that may never anchor a row.
FORBIDDEN_ANCHOR_NAMES = frozenset(
    {"tenant_id", "customer_org_id", "organization_profile_id"}
)

# Lineage identifiers. Recorded, never causal.
LINEAGE_FIELDS: tuple[str, ...] = ("source_pursuit_id", "source_opportunity_id")

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "operation",
    "table_name",
    "rls_anchor",
    "organization_id",
    "tenant_beta_profile_id",
    "source_pursuit_id",
    "source_opportunity_id",
    "award_number",
    "award_title",
    "funder_name",
    "program_name",
    "award_status",
    "award_amount",
    "award_currency",
    "period_start",
    "period_end",
    "awarded_at",
    "active_obligation_status",
    "fact_status",
    "human_review_required",
    "created_by_identity_id",
    "updated_by_identity_id",
    "archived_at",
    "storage_allowed",
    "production_write_allowed",
    "write_performed",
    "read_performed",
    "rows_written",
    "rows_read",
    "rows_deleted",
    "blocked_reasons",
)

_METADATA = sa.MetaData()

# Mirrors migration 0032 - columns *and* constraints. Gate 119C shipped a Core
# table with the columns and none of the constraints, which meant a test built a
# weaker schema than production. Two tests compare the definitions by name.
AWARDED_GRANTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("tenant_beta_profile_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("tenant_id_label", sa.Text(), nullable=True),
    sa.Column("customer_org_id_label", sa.Text(), nullable=True),
    sa.Column("source_pursuit_id", sa.Text(), nullable=True),
    sa.Column("source_opportunity_id", sa.Text(), nullable=True),
    sa.Column("award_number", sa.Text(), nullable=True),
    sa.Column("award_title", sa.Text(), nullable=False),
    sa.Column("funder_name", sa.Text(), nullable=True),
    sa.Column("program_name", sa.Text(), nullable=True),
    sa.Column("award_status", sa.String(length=32), nullable=False),
    sa.Column("award_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column("award_currency", sa.String(length=3), nullable=True),
    sa.Column("period_start", sa.Date(), nullable=True),
    sa.Column("period_end", sa.Date(), nullable=True),
    sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("active_obligation_status", sa.String(length=32), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("updated_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint(
        "award_status IN ('draft_award_record', 'active_award', "
        "'closeout_pending', 'closed', 'cancelled', 'mistaken_award', 'unknown')",
        name="ck_nf_awarded_grants_award_status",
    ),
    sa.CheckConstraint(
        "active_obligation_status IN ('no_obligations_established', "
        "'obligations_established', 'obligations_closed', 'needs_human_review', "
        "'unknown')",
        name="ck_nf_awarded_grants_obligation_status",
    ),
    sa.CheckConstraint(
        "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture', "
        "'unknown', 'needs_human_review')",
        name="ck_nf_awarded_grants_fact_status",
    ),
    sa.CheckConstraint(
        "length(trim(award_title)) > 0",
        name="ck_nf_awarded_grants_title_not_blank",
    ),
    sa.CheckConstraint(
        "period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
        name="ck_nf_awarded_grants_period_order",
    ),
    sa.CheckConstraint(
        "(award_amount IS NULL) = (award_currency IS NULL)",
        name="ck_nf_awarded_grants_amount_needs_currency",
    ),
    sa.CheckConstraint(
        "award_amount IS NOT NULL OR "
        "fact_status IN ('unknown', 'needs_human_review', 'demo_fixture')",
        name="ck_nf_awarded_grants_unknown_amount_is_unestablished",
    ),
    sa.CheckConstraint(
        "active_obligation_status <> 'obligations_established' OR "
        "fact_status IN ('verified', 'tenant_supplied')",
        name="ck_nf_awarded_grants_obligations_need_established_facts",
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


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _iso(moment: Any) -> str | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        return aware.isoformat()
    if isinstance(moment, date):
        return moment.isoformat()
    return str(moment)


def _result(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "table_name": TABLE_NAME,
        "rls_anchor": RLS_ANCHOR_COLUMN,
        # Constants. This repository inserts and archives; it never deletes,
        # never creates an award from lineage, and never promotes a projection.
        "rows_deleted": 0,
        "history_preserved": True,
        "real_customer_rows_written": 0,
        "production_awarded_grants_created": 0,
        "award_created_from_lineage": False,
        "projected_burden_considered": False,
        "award_status_inferred_from_pursuit": False,
    }
    out.update(fields)
    out["blocked_reasons"] = sorted(set(fields.get("blocked_reasons") or []))
    return _json_safe(out)


def prepare_award_write(
    *,
    organization_id: Any = None,
    tenant_beta_profile_id: Any = None,
    tenant_id_label: Any = None,
    customer_org_id_label: Any = None,
    organization_profile_id: Any = None,
    source_pursuit_id: Any = None,
    source_opportunity_id: Any = None,
    award_number: Any = None,
    award_title: Any = None,
    funder_name: Any = None,
    program_name: Any = None,
    award_status: Any = None,
    award_amount: Any = None,
    award_currency: Any = None,
    period_start: Any = None,
    period_end: Any = None,
    awarded_at: Any = None,
    active_obligation_status: Any = None,
    fact_status: Any = None,
    requirements_extraction_status: Any = None,
    created_by_identity_id: Any = None,
    updated_by_identity_id: Any = None,
    is_demo: bool = False,
    customer_auth_live: bool = False,
    verified_operational_binding: bool = False,
) -> dict[str, Any]:
    """Decide whether an award may be written. Touches no database.

    The award's own validity is decided by Gate 124D rather than duplicated
    here; this adds the anchor rules and the production write gates.
    """
    blocked_reasons: list[str] = []

    # -- the anchor ----------------------------------------------------------
    if not str(organization_id or "").strip():
        blocked_reasons.append("award_without_an_organization_id_anchor")
    elif not _uuid_shaped(organization_id):
        blocked_reasons.append("organization_id_anchor_is_not_uuid_shaped")

    # Refused rather than ignored. Gates 110-113 exist for this substitution.
    if organization_profile_id:
        blocked_reasons.append(
            "organization_profile_id_is_not_an_organization_id_anchor"
        )

    # A beta profile is context. It is a real foreign key and still not an
    # anchor: an award belongs to an organization.
    profile_id = str(tenant_beta_profile_id or "").strip()
    if profile_id and not _uuid_shaped(profile_id):
        blocked_reasons.append("tenant_beta_profile_id_is_not_uuid_shaped")

    # -- the award itself ----------------------------------------------------
    validation = validate_awarded_grant(
        award_title=award_title,
        award_status=award_status,
        active_obligation_status=active_obligation_status,
        fact_status=fact_status,
        award_amount=award_amount,
        award_currency=award_currency,
        period_start=period_start,
        period_end=period_end,
        source_pursuit_id=source_pursuit_id,
        source_opportunity_id=source_opportunity_id,
        requirements_extraction_status=requirements_extraction_status,
    )
    blocked_reasons.extend(validation["blocked_reasons"])

    # -- who may write, and whether this is a production write ---------------
    demo_fixture = bool(is_demo) or validation["fact_status"] == "demo_fixture"
    production_write = not demo_fixture

    if production_write and not customer_auth_live:
        blocked_reasons.append("production_award_write_requires_live_customer_auth")
    if production_write and not verified_operational_binding:
        blocked_reasons.append(
            "production_award_write_requires_a_verified_operational_binding"
        )

    storage_allowed = not blocked_reasons
    production_write_allowed = bool(storage_allowed and production_write)

    result = _result(
        operation="prepare_award_write",
        organization_id=str(organization_id or "") or None,
        tenant_beta_profile_id=profile_id or None,
        tenant_id_label=str(tenant_id_label or "") or None,
        customer_org_id_label=str(customer_org_id_label or "") or None,
        source_pursuit_id=validation["source_pursuit_id"],
        source_opportunity_id=validation["source_opportunity_id"],
        award_number=str(award_number or "") or None,
        award_title=str(award_title or "").strip() or None,
        funder_name=str(funder_name or "") or None,
        program_name=str(program_name or "") or None,
        award_status=validation["award_status"],
        award_amount=(
            str(_as_amount(award_amount)) if _as_amount(award_amount) else None
        ),
        award_currency=validation["award_currency"],
        period_start=validation["period_start"],
        period_end=validation["period_end"],
        awarded_at=_iso(awarded_at),
        active_obligation_status=validation["active_obligation_status"],
        fact_status=validation["fact_status"],
        requirements_extraction_status=validation["requirements_extraction_status"],
        created_by_identity_id=str(created_by_identity_id or "") or None,
        updated_by_identity_id=str(updated_by_identity_id or "") or None,
        archived_at=None,
        demo_fixture=demo_fixture,
        human_review_required=bool(validation["human_review_required"]),
        storage_allowed=storage_allowed,
        production_write_allowed=production_write_allowed,
        write_performed=False,
        read_performed=False,
        rows_written=0,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )
    result["validation"] = validation
    return _json_safe(result)


def create_awarded_grant(
    *,
    connection: Any = None,
    award_id: uuid.UUID | None = None,
    now: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Insert one awarded grant, if ``prepare_award_write`` permits it.

    There is no upsert. An award is a discrete event: a correction is a new row
    and the mistaken one is archived with `mistaken_award`, so the audit trail
    shows what was believed and when.
    """
    decision = prepare_award_write(**fields)
    blocked_reasons = list(decision["blocked_reasons"])

    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0

    if decision["storage_allowed"] and connection is not None:
        connection.execute(
            sa.insert(AWARDED_GRANTS).values(
                id=award_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                tenant_beta_profile_id=_as_uuid(decision["tenant_beta_profile_id"]),
                tenant_id_label=decision["tenant_id_label"],
                customer_org_id_label=decision["customer_org_id_label"],
                source_pursuit_id=decision["source_pursuit_id"],
                source_opportunity_id=decision["source_opportunity_id"],
                award_number=decision["award_number"],
                award_title=str(decision["award_title"]),
                funder_name=decision["funder_name"],
                program_name=decision["program_name"],
                award_status=decision["award_status"],
                award_amount=_as_amount(decision["award_amount"]),
                award_currency=decision["award_currency"],
                period_start=_as_date(decision["period_start"]),
                period_end=_as_date(decision["period_end"]),
                awarded_at=(
                    datetime.fromisoformat(decision["awarded_at"])
                    if decision["awarded_at"]
                    else None
                ),
                active_obligation_status=decision["active_obligation_status"],
                fact_status=decision["fact_status"],
                human_review_required=bool(decision["human_review_required"]),
                created_by_identity_id=_as_uuid(decision["created_by_identity_id"]),
                updated_by_identity_id=_as_uuid(decision["updated_by_identity_id"]),
                archived_at=None,
                is_demo=bool(decision["demo_fixture"]),
                blocked_reasons=[],
                created_at=moment,
                updated_at=moment,
            )
        )
        written = 1

    return _result(
        **{
            **decision,
            "operation": "create_awarded_grant",
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": blocked_reasons,
        }
    )


def _row_to_facts(row: Any) -> dict[str, Any]:
    return {
        "organization_id": str(row["organization_id"]),
        "tenant_beta_profile_id": (
            str(row["tenant_beta_profile_id"])
            if row["tenant_beta_profile_id"]
            else None
        ),
        "tenant_id_label": row["tenant_id_label"],
        "customer_org_id_label": row["customer_org_id_label"],
        "source_pursuit_id": row["source_pursuit_id"],
        "source_opportunity_id": row["source_opportunity_id"],
        "award_number": row["award_number"],
        "award_title": row["award_title"],
        "funder_name": row["funder_name"],
        "program_name": row["program_name"],
        "award_status": row["award_status"],
        "award_amount": str(row["award_amount"]) if row["award_amount"] else None,
        "award_currency": row["award_currency"],
        "period_start": _iso(row["period_start"]),
        "period_end": _iso(row["period_end"]),
        "awarded_at": _iso(row["awarded_at"]),
        "active_obligation_status": row["active_obligation_status"],
        "fact_status": row["fact_status"],
        "created_by_identity_id": (
            str(row["created_by_identity_id"])
            if row["created_by_identity_id"]
            else None
        ),
        "updated_by_identity_id": (
            str(row["updated_by_identity_id"])
            if row["updated_by_identity_id"]
            else None
        ),
        "archived_at": _iso(row["archived_at"]),
        "demo_fixture": bool(row["is_demo"]),
        "human_review_required": bool(row["human_review_required"]),
    }


def _empty_facts() -> dict[str, Any]:
    return {
        "tenant_beta_profile_id": None,
        "tenant_id_label": None,
        "customer_org_id_label": None,
        "source_pursuit_id": None,
        "source_opportunity_id": None,
        "award_number": None,
        "award_title": None,
        "funder_name": None,
        "program_name": None,
        "award_status": None,
        "award_amount": None,
        "award_currency": None,
        "period_start": None,
        "period_end": None,
        "awarded_at": None,
        "active_obligation_status": None,
        "fact_status": None,
        "created_by_identity_id": None,
        "updated_by_identity_id": None,
        "archived_at": None,
        "demo_fixture": False,
        "human_review_required": True,
    }


def get_awarded_grant(
    *,
    connection: Any = None,
    organization_id: Any = None,
    award_id: Any = None,
    award_number: Any = None,
    include_archived: bool = False,
) -> dict[str, Any]:
    """One award, anchored on ``organization_id``.

    An award id or an award number narrows within the organization. Neither
    selects on its own, because a read anchored on anything but the
    organization is a read the RLS policy cannot scope.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked_reasons:
        query = sa.select(AWARDED_GRANTS).where(
            AWARDED_GRANTS.c.organization_id == _as_uuid(organization_id)
        )
        if not include_archived:
            query = query.where(AWARDED_GRANTS.c.archived_at.is_(None))
        if award_id and _uuid_shaped(award_id):
            query = query.where(AWARDED_GRANTS.c.id == _as_uuid(award_id))
        if str(award_number or "").strip():
            query = query.where(
                AWARDED_GRANTS.c.award_number == str(award_number).strip()
            )
        row = connection.execute(query).mappings().first()
        if row is None:
            blocked_reasons.append("no_awarded_grant_for_this_organization")

    facts = _row_to_facts(row) if row is not None else _empty_facts()

    return _result(
        operation="get_awarded_grant",
        organization_id=str(organization_id or "") or None,
        **{k: v for k, v in facts.items() if k != "organization_id"},
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=row is not None,
        rows_written=0,
        rows_read=1 if row is not None else 0,
        blocked_reasons=blocked_reasons,
    )


def list_awarded_grants(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Every award for one organization, archived ones included by default.

    Archived rows are returned because they are the audit trail. A listing that
    hid a `mistaken_award` would make it indistinguishable from an award that
    never happened, which is exactly what a funder's audit asks about.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked_reasons:
        query = sa.select(AWARDED_GRANTS).where(
            AWARDED_GRANTS.c.organization_id == _as_uuid(organization_id)
        )
        if not include_archived:
            query = query.where(AWARDED_GRANTS.c.archived_at.is_(None))
        rows = [
            _row_to_facts(row)
            for row in connection.execute(
                query.order_by(AWARDED_GRANTS.c.created_at)
            ).mappings()
        ]

    result = _result(
        operation="list_awarded_grants",
        organization_id=str(organization_id or "") or None,
        **_empty_facts(),
        storage_allowed=False,
        production_write_allowed=False,
        write_performed=False,
        read_performed=bool(rows),
        rows_written=0,
        rows_read=len(rows),
        blocked_reasons=blocked_reasons,
    )
    result["awards"] = rows
    result["archived_count"] = sum(1 for r in rows if r["archived_at"])
    result["obligating_count"] = sum(
        1 for r in rows if r["active_obligation_status"] in OBLIGATING_STATUSES
    )
    return _json_safe(result)


def archive_awarded_grant(
    *,
    connection: Any = None,
    organization_id: Any = None,
    award_id: Any = None,
    archived_by_identity_id: Any = None,
    award_status: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Withdraw an award. An UPDATE, never a DELETE.

    ``award_status`` may be set at the same time - `mistaken_award` for one that
    turned out not to exist, `cancelled` for one the funder withdrew. They are
    different facts and the row records which.
    """
    blocked_reasons: list[str] = []

    if not _uuid_shaped(organization_id):
        blocked_reasons.append("archive_without_a_uuid_shaped_anchor")
    if not _uuid_shaped(award_id):
        blocked_reasons.append("archive_without_an_award_id")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_written")

    status = str(award_status or "").strip().lower()
    if status and status not in AWARD_STATUSES:
        blocked_reasons.append(f"award_status_not_recognised:{status}")

    moment = now or datetime.now(UTC)
    written = 0

    if not blocked_reasons:
        row = (
            connection.execute(
                sa.select(AWARDED_GRANTS).where(
                    AWARDED_GRANTS.c.organization_id == _as_uuid(organization_id),
                    AWARDED_GRANTS.c.id == _as_uuid(award_id),
                    AWARDED_GRANTS.c.archived_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked_reasons.append("no_live_awarded_grant_to_archive")
        else:
            values: dict[str, Any] = {
                "archived_at": moment,
                "updated_by_identity_id": _as_uuid(archived_by_identity_id),
                "human_review_required": True,
                "updated_at": moment,
                # An archived award obliges nobody, whatever it obliged before.
                "active_obligation_status": "obligations_closed",
            }
            if status:
                values["award_status"] = status
            connection.execute(
                sa.update(AWARDED_GRANTS)
                .where(AWARDED_GRANTS.c.id == row["id"])
                .values(**values)
            )
            written = 1

    return _result(
        operation="archive_awarded_grant",
        organization_id=str(organization_id or "") or None,
        **{
            **_empty_facts(),
            "award_status": status or None,
            "active_obligation_status": "obligations_closed" if written else None,
            "archived_at": _iso(moment) if written else None,
            "updated_by_identity_id": str(archived_by_identity_id or "") or None,
        },
        storage_allowed=not blocked_reasons,
        production_write_allowed=False,
        write_performed=bool(written),
        read_performed=False,
        rows_written=written,
        rows_read=0,
        blocked_reasons=blocked_reasons,
    )


def validate_award_persistence(
    *,
    connection: Any = None,
    organization_id: Any = None,
    award_id: Any = None,
) -> dict[str, Any]:
    """Is what is stored fit to drive obligation tracking?

    Reads the award and runs Gate 124D's validation over it, so a caller can ask
    "would this award produce a correct compliance calendar" without
    constructing one.
    """
    stored = get_awarded_grant(
        connection=connection, organization_id=organization_id, award_id=award_id
    )
    validation = validate_awarded_grant(
        award_title=stored.get("award_title"),
        award_status=stored.get("award_status"),
        active_obligation_status=stored.get("active_obligation_status"),
        fact_status=stored.get("fact_status"),
        award_amount=stored.get("award_amount"),
        award_currency=stored.get("award_currency"),
        period_start=stored.get("period_start"),
        period_end=stored.get("period_end"),
        source_pursuit_id=stored.get("source_pursuit_id"),
        source_opportunity_id=stored.get("source_opportunity_id"),
    )

    result = _result(
        **{
            **stored,
            "operation": "validate_award_persistence",
            "blocked_reasons": sorted(
                {*stored["blocked_reasons"], *validation["blocked_reasons"]}
            ),
        }
    )
    result["validation"] = validation
    result["award_found"] = bool(stored["rows_read"])
    return _json_safe(result)


def awarded_grants_repository_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
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
        failures.append("an_awarded_grant_row_was_deleted")

    if result.get("real_customer_rows_written"):
        failures.append("a_real_customer_row_was_written")

    if result.get("production_awarded_grants_created"):
        failures.append("a_production_awarded_grant_was_created")

    # The rules Gate 91 exists to protect.
    if result.get("award_created_from_lineage"):
        failures.append("an_award_was_created_from_pursuit_lineage")

    if result.get("projected_burden_considered"):
        failures.append("a_projected_burden_reached_an_award_row")

    if result.get("award_status_inferred_from_pursuit"):
        failures.append("an_award_status_was_inferred_from_a_pursuit")

    if result.get("write_performed") and operation not in WRITE_OPERATIONS:
        failures.append("a_read_operation_reported_a_write")

    if result.get("rows_written") and not result.get("write_performed"):
        failures.append("rows_written_without_a_write")

    if result.get("write_performed") and not result.get("storage_allowed"):
        failures.append("a_write_happened_without_storage_being_allowed")

    if result.get("production_write_allowed") and result.get("demo_fixture"):
        failures.append("a_demo_fixture_claimed_a_production_write")

    if result.get("storage_allowed") and result.get("blocked_reasons"):
        remaining = [
            reason
            for reason in result["blocked_reasons"]
            if not reason.startswith("no_connection_supplied")
        ]
        if remaining:
            failures.append("storage_allowed_with_blocked_reasons_present")

    # An obligation stored without established facts is the failure this table's
    # CHECK exists to catch, asserted here too so a contract-mode result cannot
    # claim it either.
    obligation = str(result.get("active_obligation_status") or "")
    fact = str(result.get("fact_status") or "")
    if (
        obligation in OBLIGATING_STATUSES
        and result.get("storage_allowed")
        and fact not in ACTIONABLE_FACT_STATUSES
    ):
        failures.append("obligations_established_without_established_facts")

    if (
        result.get("storage_allowed")
        and not str(result.get("award_title") or "").strip()
    ):
        if operation in {"prepare_award_write", "create_awarded_grant"}:
            failures.append("an_award_was_storable_without_a_title")

    if not result.get("storage_allowed") and not result.get("blocked_reasons"):
        if operation not in READ_OPERATIONS:
            failures.append("storage_refused_without_a_reason")

    return sorted(set(failures))


def repository_vocabularies() -> dict[str, list[str]]:
    """The Gate 91/103/108 vocabularies this repository bridges rather than owns."""
    return _json_safe(
        {
            "award_statuses": sorted(AWARD_STATUSES),
            "live_award_statuses": sorted(LIVE_AWARD_STATUSES),
            "active_obligation_statuses": sorted(ACTIVE_OBLIGATION_STATUSES),
            "obligating_statuses": sorted(OBLIGATING_STATUSES),
            "requirements_extraction_statuses": sorted(
                REQUIREMENTS_EXTRACTION_STATUSES
            ),
            "obligation_capable_extraction": sorted(OBLIGATION_CAPABLE_EXTRACTION),
            "fact_statuses": sorted(FACT_STATUSES),
            "actionable_fact_statuses": sorted(ACTIONABLE_FACT_STATUSES),
            "forbidden_anchor_names": sorted(FORBIDDEN_ANCHOR_NAMES),
            "lineage_fields": list(LINEAGE_FIELDS),
        }
    )
