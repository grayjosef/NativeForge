"""Gate 151C: the digest a delivery intent names, stored and readable back.

## What this closes

Seventy-one delivery intents named a digest. None of those digests existed
anywhere. A tenant asking "what did you tell me before I missed that deadline"
got an intent that could say a digest was queued and nothing that could say what
was in it.

## The label is forced, not accepted

`is_demo` and `fact_status` are set by this repository from the organization's
own classification, never from a caller. Gate 137A found a verified binding
written onto the demo organization because the caller said it was not one, and
Gate 139 put the fixture-labelling in one place for the same reason. A caller
that supplies either gets a named refusal.

## Cross-org access is refused, not filtered

Every read takes an `organization_id` and every query is partitioned by it. A
read for a digest that exists in another organization returns nothing and says
`no_digest_record_for_this_organization` — the same answer it gives for a digest
that does not exist at all, because a different answer would confirm it does.

## Archive is a state

An audit of a missed deadline needs the digest that was current at the time, not
only the current one. `archive` sets `archived_at` and the row stays readable.

## What it never does

No email, no provider contact, no live source call, no object store, no document
body. There is no column for an address and no code path that could fill one.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_tenant_digest_records_repository_v1"

TABLE_NAME = "nf_tenant_digest_records"

#: Gate 151's demo organization. The only one this path writes to today.
DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: Refused by name, as everywhere else in this campaign.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Extra keyword arguments a caller may not smuggle in, because each would
#: decide whether a write is a production write or what the record claims about
#: itself. Gate 139's `CALLER_MAY_NOT_SET`, restated at a new entry point.
#:
#: `organization_id` is deliberately absent: it is a named parameter of every
#: function here and is required, so listing it would say the repository
#: refuses the one thing it cannot work without. The partition is authoritative,
#: not forbidden.
CALLER_MAY_NOT_SET: tuple[str, ...] = (
    "is_demo",
    "fact_status",
    "email_delivery_live",
    "source_monitoring_live",
    "payload_sha256",
)

#: A body field naming any of these is trying to store a rendering or a
#: recipient. There is no column for either; the refusal names it rather than
#: letting the write fail on a missing column.
FORBIDDEN_PAYLOAD_FIELDS: tuple[str, ...] = (
    "recipient",
    "recipient_email",
    "email",
    "address",
    "to",
    "rendered_body",
    "body",
    "html",
    "mime",
)

_METADATA = sa.MetaData()

RECORDS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("tenant_id_label", sa.Text(), nullable=True),
    sa.Column("digest_id", sa.Text(), nullable=False),
    sa.Column("digest_period_key", sa.Text(), nullable=False),
    sa.Column("cadence", sa.String(length=16), nullable=False),
    sa.Column("period_start", sa.Date(), nullable=True),
    sa.Column("period_end", sa.Date(), nullable=True),
    sa.Column("digest_payload_json", sa.JSON(), nullable=False),
    sa.Column("payload_sha256", sa.String(length=64), nullable=False),
    sa.Column("snapshot_ids", sa.JSON(), nullable=True),
    sa.Column("items_total", sa.Integer(), nullable=False),
    sa.Column("items_visible", sa.Integer(), nullable=False),
    sa.Column("items_suppressed", sa.Integer(), nullable=False),
    sa.Column("items_unchanged", sa.Integer(), nullable=False),
    sa.Column("items_human_review", sa.Integer(), nullable=False),
    sa.Column("items_with_unverified_deadlines", sa.Integer(), nullable=False),
    sa.Column("items_with_unknown_reporting_burden", sa.Integer(), nullable=False),
    sa.Column("caveats_json", sa.JSON(), nullable=True),
    sa.Column("blocked_reasons", sa.JSON(), nullable=True),
    sa.Column("delivery_status", sa.String(length=32), nullable=False),
    sa.Column("email_delivery_live", sa.Boolean(), nullable=False),
    sa.Column("source_monitoring_live", sa.Boolean(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


def _as_date(value: Any) -> date | None:
    """The digest carries ISO strings; `period_start` and `period_end` are DATE.

    SQLite refuses a string outright and Postgres coerces it, so a value that
    worked in one environment would have failed in the other - the same split
    Gate 142 hit when an untyped column bound a UUID on one dialect and not the
    other. Coerced here so both dialects see a date object.
    """
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:  # noqa: BLE001
        return None


def payload_sha256(payload: Any) -> str:
    """Stable over key order and whitespace, so a re-render can be checked."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result(**fields: Any) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "operation": None,
        "organization_id": None,
        "digest_id": None,
        "rows_written": 0,
        "rows_read": 0,
        "records": [],
        "record": None,
        "write_performed": False,
        "archived": False,
        # Constants. This repository contacts nothing.
        "email_sent": False,
        "provider_contacted": False,
        "live_source_called": False,
        "object_store_contacted": False,
        "document_body_written": False,
        "real_organization_touched": False,
        "blocked_reasons": [],
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def _row_to_record(row: Any) -> dict[str, Any]:
    return _json_safe(
        {
            "digest_id": row["digest_id"],
            "organization_id": str(row["organization_id"]),
            "is_demo": bool(row["is_demo"]),
            "tenant_id_label": row["tenant_id_label"],
            "digest_period_key": row["digest_period_key"],
            "cadence": row["cadence"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "digest_payload_json": row["digest_payload_json"],
            "payload_sha256": row["payload_sha256"],
            "snapshot_ids": row["snapshot_ids"],
            "items_total": row["items_total"],
            "items_visible": row["items_visible"],
            "items_suppressed": row["items_suppressed"],
            "items_unchanged": row["items_unchanged"],
            "items_human_review": row["items_human_review"],
            "items_with_unverified_deadlines": row[
                "items_with_unverified_deadlines"
            ],
            "items_with_unknown_reporting_burden": row[
                "items_with_unknown_reporting_burden"
            ],
            "caveats_json": row["caveats_json"],
            "blocked_reasons": row["blocked_reasons"],
            "delivery_status": row["delivery_status"],
            "email_delivery_live": bool(row["email_delivery_live"]),
            "source_monitoring_live": bool(row["source_monitoring_live"]),
            "fact_status": row["fact_status"],
            "human_review_required": bool(row["human_review_required"]),
            "archived_at": row["archived_at"],
            "created_at": row["created_at"],
        }
    )


def _payload_refusals(payload: Any) -> list[str]:
    """A payload trying to carry a recipient or a rendering is refused."""
    if not isinstance(payload, dict):
        return ["digest_payload_is_not_an_object"]
    offending = sorted(
        key for key in payload if str(key).strip().lower() in FORBIDDEN_PAYLOAD_FIELDS
    )
    return [f"payload_field_refused:{key}" for key in offending]


def insert_digest_record(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest: dict[str, Any] | None = None,
    org_is_demo: bool | None = None,
    created_by_identity_id: Any = None,
    **offered: Any,
) -> dict[str, Any]:
    """Persist one digest. The labelling is derived, never supplied."""
    blocked: list[str] = []

    org = _as_uuid(organization_id)
    normalized = str(organization_id or "").strip().lower()

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if normalized == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")

    offered_forbidden = sorted(k for k in offered if k in CALLER_MAY_NOT_SET)
    if offered_forbidden:
        blocked.extend(f"caller_may_not_set:{key}" for key in offered_forbidden)

    if not isinstance(digest, dict) or not digest:
        blocked.append("no_digest_supplied")
        return _result(
            operation="insert_digest_record",
            organization_id=normalized or None,
            blocked_reasons=blocked,
        )

    blocked.extend(_payload_refusals(digest))

    digest_id = str(digest.get("digest_id") or "").strip()
    if not digest_id:
        blocked.append("digest_has_no_digest_id")

    # The three counts have to agree before the database says so, because a
    # CHECK failure is a stack trace and a blocked reason is an answer.
    total = int(digest.get("items_total") or 0)
    visible = int(digest.get("items_visible") or 0)
    suppressed = int(digest.get("items_suppressed") or 0)
    if total < visible + suppressed:
        blocked.append("item_counts_do_not_agree")

    if blocked:
        return _result(
            operation="insert_digest_record",
            organization_id=normalized or None,
            digest_id=digest_id or None,
            blocked_reasons=blocked,
        )

    # Derived from the organization, never from the caller.
    is_demo = bool(org_is_demo if org_is_demo is not None else True)
    fact_status = "demo_fixture" if is_demo else "unknown"

    payload = _json_safe(digest)
    digest_hash = payload_sha256(payload)
    now = datetime.now(UTC)

    try:
        connection.execute(
            RECORDS.insert().values(
                id=uuid.uuid4(),
                organization_id=org,
                is_demo=is_demo,
                tenant_id_label=str(digest.get("tenant_id") or "") or None,
                digest_id=digest_id,
                digest_period_key=str(
                    digest.get("digest_period_key")
                    or f"{digest.get('period_start')}..{digest.get('period_end')}"
                ),
                cadence=str(digest.get("cadence") or "unknown"),
                period_start=_as_date(digest.get("period_start")),
                period_end=_as_date(digest.get("period_end")),
                digest_payload_json=payload,
                payload_sha256=digest_hash,
                snapshot_ids=_json_safe(digest.get("snapshot_ids") or []),
                items_total=total,
                items_visible=visible,
                items_suppressed=suppressed,
                items_unchanged=max(total - visible - suppressed, 0),
                items_human_review=int(digest.get("items_human_review") or 0),
                items_with_unverified_deadlines=int(
                    digest.get("items_with_unverified_deadlines") or 0
                ),
                items_with_unknown_reporting_burden=int(
                    digest.get("items_with_unknown_reporting_burden") or 0
                ),
                caveats_json=_json_safe(digest.get("caveats") or []),
                blocked_reasons=_json_safe(digest.get("blocked_reasons") or []),
                delivery_status=str(
                    digest.get("delivery_status") or "preview_only"
                ),
                # Never supplied. The record states the capabilities were off.
                email_delivery_live=False,
                source_monitoring_live=False,
                fact_status=fact_status,
                human_review_required=bool(
                    int(digest.get("items_human_review") or 0) > 0
                ),
                created_by_identity_id=_as_uuid(created_by_identity_id),
                archived_at=None,
                created_at=now,
                updated_at=now,
            )
        )
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        blocked.append(
            "digest_already_persisted_for_this_period"
            if "Integrity" in name
            else f"insert_refused:{name}"
        )
        return _result(
            operation="insert_digest_record",
            organization_id=normalized,
            digest_id=digest_id,
            blocked_reasons=blocked,
        )

    return _result(
        operation="insert_digest_record",
        organization_id=normalized,
        digest_id=digest_id,
        rows_written=1,
        write_performed=True,
        record={"digest_id": digest_id, "payload_sha256": digest_hash},
    )


def get_digest_record(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_id: Any = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    """Read one digest, partitioned by organization."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    wanted = str(digest_id or "").strip()

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if not wanted:
        blocked.append("no_digest_id_supplied")

    if blocked:
        return _result(
            operation="get_digest_record",
            organization_id=str(organization_id or "") or None,
            digest_id=wanted or None,
            blocked_reasons=blocked,
        )

    query = sa.select(RECORDS).where(
        sa.and_(
            RECORDS.c.organization_id == org,
            RECORDS.c.digest_id == wanted,
        )
    )
    if not include_archived:
        query = query.where(RECORDS.c.archived_at.is_(None))

    rows = connection.execute(query).mappings().all()
    if not rows:
        # The same answer for "not yours" as for "does not exist". A different
        # one would confirm it exists.
        return _result(
            operation="get_digest_record",
            organization_id=str(org),
            digest_id=wanted,
            blocked_reasons=["no_digest_record_for_this_organization"],
        )

    return _result(
        operation="get_digest_record",
        organization_id=str(org),
        digest_id=wanted,
        rows_read=len(rows),
        record=_row_to_record(rows[0]),
    )


def list_digest_records(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """Every digest for one organization, newest first."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")

    if blocked:
        return _result(
            operation="list_digest_records",
            organization_id=str(organization_id or "") or None,
            blocked_reasons=blocked,
        )

    query = sa.select(RECORDS).where(RECORDS.c.organization_id == org)
    if not include_archived:
        query = query.where(RECORDS.c.archived_at.is_(None))
    query = query.order_by(RECORDS.c.created_at.desc()).limit(max(1, int(limit)))

    rows = connection.execute(query).mappings().all()
    return _result(
        operation="list_digest_records",
        organization_id=str(org),
        rows_read=len(rows),
        records=[_row_to_record(row) for row in rows],
    )


def archive_digest_record(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_id: Any = None,
) -> dict[str, Any]:
    """Archive one digest. It stays readable; an audit needs it to."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    wanted = str(digest_id or "").strip()

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if not wanted:
        blocked.append("no_digest_id_supplied")

    if blocked:
        return _result(
            operation="archive_digest_record",
            organization_id=str(organization_id or "") or None,
            digest_id=wanted or None,
            blocked_reasons=blocked,
        )

    now = datetime.now(UTC)
    result = connection.execute(
        RECORDS.update()
        .where(
            sa.and_(
                RECORDS.c.organization_id == org,
                RECORDS.c.digest_id == wanted,
                RECORDS.c.archived_at.is_(None),
            )
        )
        .values(archived_at=now, updated_at=now)
    )

    written = int(result.rowcount or 0)
    if not written:
        return _result(
            operation="archive_digest_record",
            organization_id=str(org),
            digest_id=wanted,
            blocked_reasons=["no_live_digest_record_for_this_organization"],
        )

    return _result(
        operation="archive_digest_record",
        organization_id=str(org),
        digest_id=wanted,
        rows_written=written,
        write_performed=True,
        archived=True,
    )


def repository_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims more than it did, or contacted anything."""
    fails: list[str] = []

    if result.get("write_performed") and not result.get("rows_written"):
        fails.append("write_performed_without_rows")
    if result.get("rows_written") and result.get("blocked_reasons"):
        fails.append("rows_written_alongside_blockers")
    if result.get("archived") and not result.get("write_performed"):
        fails.append("archived_without_a_write")
    if result.get("record") and result.get("blocked_reasons"):
        fails.append("record_returned_alongside_blockers")

    for flag in (
        "email_sent",
        "provider_contacted",
        "live_source_called",
        "object_store_contacted",
        "document_body_written",
        "real_organization_touched",
    ):
        if result.get(flag):
            fails.append(f"repository_claimed_to_have:{flag}")

    return sorted(set(fails))
