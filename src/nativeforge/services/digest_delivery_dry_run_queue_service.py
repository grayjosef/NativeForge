"""Gate 142E: record an intention to deliver, and deliver nothing.

## An intent is not a queue position

Gate 104's digest builder owns the word `queued` and lists it under
`DELIVERED_STATUSES` — "statuses that assert something left the building". So a
row here starts at `dry_run_recorded` and the digest it names keeps
`delivery_status: preview_only`. Borrowing `queued` would have made the
digest's own invariant a lie about this system rather than a check on it.

## Three CHECKs the database enforces

```sql
NOT send_attempted
NOT provider_contacted
emails_sent = 0
delivery_status <> 'queued' AND delivery_status <> 'sent'
```

A future gate that activates sending has to remove those in a migration
somebody reviews. It cannot happen by a default changing somewhere.

## No address, and nowhere to put one

The table has `recipient_fingerprint` and `recipient_domain` and no address
column, plus two CHECKs — 32 characters, and no `@` — so the fingerprint column
cannot quietly become one. `validate_recipient` is where an address is read,
and this module never sees one.

## One live intent per period and recipient

A partial unique index on
`(organization_id, digest_period_key, recipient_fingerprint)` where
`cancelled_at IS NULL`. Recording the same intention twice is how a tenant gets
two copies of one digest the day sending is switched on, and the index refuses
it before a service has to remember to.

## Nothing here is a send

No provider, no socket, no mail library. Every result reports
`provider_contacted: False` and `emails_sent: 0`, and an invariant fails if
either changes.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_digest_delivery_dry_run_queue_v1"

TABLE_NAME = "nf_digest_delivery_intents"

#: The queue's own vocabulary. `queued` and `sent` are deliberately absent.
DELIVERY_INTENT_STATES: frozenset[str] = frozenset(
    {
        "dry_run_recorded",
        "send_disabled",
        "recipient_refused",
        "cancelled",
        "needs_human_review",
        "unknown",
    }
)

#: States Gate 104 reserved for something that actually left.
FORBIDDEN_STATES: frozenset[str] = frozenset({"queued", "sent", "failed"})

DELIVERY_BLOCKED_REASONS: frozenset[str] = frozenset(
    {
        "send_activation_absent",
        "no_email_provider_configured",
        "recipient_not_verified",
        "recipient_domain_not_allowed",
        "recipient_shape_invalid",
        "digest_not_deliverable",
        "cancelled_by_tenant",
        "human_review_required",
        "unknown",
    }
)

RECIPIENT_SOURCES: frozenset[str] = frozenset(
    {
        "org_membership",
        "controlled_fixture",
        "tenant_requested",
        "needs_human_review",
        "unknown",
    }
)

CADENCES: frozenset[str] = frozenset({"weekly", "daily", "manual_preview", "unknown"})

#: The normal answer. Nothing is wrong; nobody has decided to send.
DEFAULT_BLOCKED_REASON = "send_activation_absent"

#: Fields a caller may never set. Same rule as every other repository in this
#: campaign: a caller cannot relabel its own write.
CALLER_MAY_NOT_SET: tuple[str, ...] = (
    "send_attempted",
    "provider_contacted",
    "emails_sent",
    "is_demo",
    "fact_status",
)

_METADATA = sa.MetaData()

DELIVERIES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("tenant_id_label", sa.Text(), nullable=True),
    sa.Column("digest_id", sa.Text(), nullable=True),
    sa.Column("digest_period_key", sa.Text(), nullable=False),
    sa.Column("cadence", sa.String(length=16), nullable=False),
    # A handle and a domain. There is no address column, here or in the
    # migration, so an address has nowhere to be stored.
    sa.Column("recipient_fingerprint", sa.String(length=64), nullable=False),
    sa.Column("recipient_domain", sa.String(length=255), nullable=True),
    sa.Column("recipient_source", sa.String(length=32), nullable=False),
    sa.Column("recipient_verified", sa.Boolean(), nullable=False),
    sa.Column("subject_line", sa.Text(), nullable=True),
    sa.Column("body_render_hash", sa.String(length=64), nullable=True),
    sa.Column("body_byte_length", sa.Integer(), nullable=True),
    sa.Column("items_total", sa.Integer(), nullable=False),
    sa.Column("items_visible", sa.Integer(), nullable=False),
    sa.Column("delivery_status", sa.String(length=32), nullable=False),
    sa.Column("blocked_reason", sa.String(length=48), nullable=False),
    sa.Column("blocked_reasons", sa.Text(), nullable=True),
    sa.Column("send_attempted", sa.Boolean(), nullable=False),
    sa.Column("provider_contacted", sa.Boolean(), nullable=False),
    sa.Column("emails_sent", sa.Integer(), nullable=False),
    sa.Column("audit_event_id", sa.Text(), nullable=True),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _iso(moment: Any) -> str | None:
    return moment.isoformat() if hasattr(moment, "isoformat") else None


def prepare_delivery_intent(
    *,
    organization_id: Any = None,
    digest_period_key: Any = None,
    cadence: Any = None,
    recipient_fingerprint: Any = None,
    recipient_domain: Any = None,
    recipient_source: Any = None,
    recipient_verified: Any = None,
    subject_line: Any = None,
    body_render_hash: Any = None,
    body_byte_length: Any = None,
    items_total: Any = None,
    items_visible: Any = None,
    digest_deliverable: Any = None,
    send_activated: Any = None,
    provider_configured: Any = None,
    **offered: Any,
) -> dict[str, Any]:
    """May this intent be recorded, and in what state? Touches no database.

    Separate from the write on purpose: the verdict is worth being able to ask
    for without a connection, and every other repository in this campaign
    splits them the same way.
    """
    blocked: list[str] = []

    anchor = _as_uuid(organization_id)
    if anchor is None:
        blocked.append("delivery_intent_without_an_organization_id_anchor")

    for key in ("tenant_id", "customer_org_id", "organization_profile_id"):
        if str(offered.get(key) or "").strip():
            blocked.append(f"not_an_anchor_for_a_delivery_intent:{key}")

    for field in CALLER_MAY_NOT_SET:
        if field in offered:
            blocked.append(f"caller_may_not_set:{field}")

    # An address must never arrive here. Refused by name rather than hashed
    # helpfully - a repository that accepted one would be a repository that
    # could store one.
    fingerprint = str(recipient_fingerprint or "").strip()
    if not fingerprint:
        blocked.append("delivery_intent_without_a_recipient_fingerprint")
    elif "@" in fingerprint:
        blocked.append("recipient_fingerprint_is_an_address")
    elif len(fingerprint) != 32:
        blocked.append("recipient_fingerprint_is_not_32_characters")

    domain = str(recipient_domain or "").strip().lower() or None
    if domain and "@" in domain:
        blocked.append("recipient_domain_is_an_address")

    period = str(digest_period_key or "").strip()
    if not period:
        blocked.append("delivery_intent_without_a_digest_period_key")

    resolved_cadence = str(cadence or "unknown").strip().lower()
    if resolved_cadence not in CADENCES:
        blocked.append(f"cadence_not_recognised:{resolved_cadence}")

    source = str(recipient_source or "unknown").strip().lower()
    if source not in RECIPIENT_SOURCES:
        blocked.append(f"recipient_source_not_recognised:{source}")

    verified = bool(recipient_verified)

    # -- the state, derived from what is true -------------------------------
    if not verified:
        status = "recipient_refused"
        reason = "recipient_not_verified"
    elif not digest_deliverable:
        status = "recipient_refused"
        reason = "digest_not_deliverable"
    elif source in {"tenant_requested", "needs_human_review", "unknown"}:
        status = "needs_human_review"
        reason = "human_review_required"
    elif send_activated:
        # Unreachable in this deployment and deliberately present: a state
        # nothing can produce is a state nobody can test, and an activation
        # path that first appears on the day it is needed is not a path.
        status = "dry_run_recorded"
        reason = "unknown"
    elif not provider_configured:
        status = "send_disabled"
        reason = "no_email_provider_configured"
    else:
        status = "dry_run_recorded"
        reason = DEFAULT_BLOCKED_REASON

    if status in FORBIDDEN_STATES:
        blocked.append(f"delivery_status_asserts_a_real_delivery:{status}")
    if reason not in DELIVERY_BLOCKED_REASONS:
        blocked.append(f"blocked_reason_not_recognised:{reason}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_allowed": not blocked,
            "organization_id": str(anchor) if anchor else None,
            "digest_period_key": period or None,
            "cadence": resolved_cadence,
            "recipient_fingerprint": fingerprint or None,
            "recipient_domain": domain,
            "recipient_source": source,
            "recipient_verified": verified,
            "delivery_status": status,
            "blocked_reason": reason,
            "subject_line": str(subject_line or "").strip() or None,
            "body_render_hash": str(body_render_hash or "").strip() or None,
            "body_byte_length": int(body_byte_length or 0),
            "items_total": int(items_total or 0),
            "items_visible": int(items_visible or 0),
            # Constants, and the database CHECKs each of them.
            "send_attempted": False,
            "provider_contacted": False,
            "emails_sent": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def record_delivery_intent(
    *,
    connection: Any = None,
    intent_id: uuid.UUID | None = None,
    now: datetime | None = None,
    is_demo: bool = True,
    fact_status: Any = None,
    tenant_id_label: Any = None,
    digest_id: Any = None,
    audit_event_id: Any = None,
    created_by_identity_id: Any = None,
    **fields: Any,
) -> dict[str, Any]:
    """Write one intent. An INSERT; nothing is sent and nothing is updated."""
    decision = prepare_delivery_intent(**fields)
    blocked = list(decision["blocked_reasons"])

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    moment = now or datetime.now(UTC)
    written = 0
    row_id = intent_id or uuid.uuid4()

    if decision["storage_allowed"] and connection is not None:
        anchor = _as_uuid(decision["organization_id"])
        existing = int(
            connection.execute(
                sa.select(sa.func.count())
                .select_from(DELIVERIES)
                .where(
                    DELIVERIES.c.organization_id == anchor,
                    DELIVERIES.c.digest_period_key == decision["digest_period_key"],
                    DELIVERIES.c.recipient_fingerprint
                    == decision["recipient_fingerprint"],
                    DELIVERIES.c.cancelled_at.is_(None),
                )
            ).scalar_one()
        )
        if existing:
            # The unique index would refuse it. Named first, so a caller gets a
            # reason rather than an IntegrityError.
            blocked.append("this_recipient_is_already_recorded_for_this_period")
        else:
            connection.execute(
                sa.insert(DELIVERIES).values(
                    id=row_id,
                    organization_id=anchor,
                    is_demo=bool(is_demo),
                    tenant_id_label=str(tenant_id_label or "").strip() or None,
                    digest_id=str(digest_id or "").strip() or None,
                    digest_period_key=decision["digest_period_key"],
                    cadence=decision["cadence"],
                    recipient_fingerprint=decision["recipient_fingerprint"],
                    recipient_domain=decision["recipient_domain"],
                    recipient_source=decision["recipient_source"],
                    recipient_verified=decision["recipient_verified"],
                    subject_line=decision["subject_line"],
                    body_render_hash=decision["body_render_hash"],
                    body_byte_length=decision["body_byte_length"],
                    items_total=decision["items_total"],
                    items_visible=decision["items_visible"],
                    delivery_status=decision["delivery_status"],
                    blocked_reason=decision["blocked_reason"],
                    blocked_reasons=json.dumps(decision["blocked_reasons"]),
                    send_attempted=False,
                    provider_contacted=False,
                    emails_sent=0,
                    audit_event_id=str(audit_event_id or "").strip() or None,
                    fact_status=str(fact_status or "demo_fixture").strip(),
                    created_by_identity_id=_as_uuid(created_by_identity_id),
                    created_at=moment,
                    recorded_at=moment,
                )
            )
            written = 1

    return _json_safe(
        {
            **decision,
            "intent_id": str(row_id) if written else None,
            "rows_written": written,
            "rows_deleted": 0,
            "recorded_at": _iso(moment) if written else None,
            "emails_sent": 0,
            "provider_contacted": False,
            "send_attempted": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _row_to_record(row: Any) -> dict[str, Any]:
    """One stored intent. No address, because there is no column for one."""
    return {
        "intent_id": str(row.id),
        "organization_id": str(row.organization_id),
        "digest_id": row.digest_id,
        "digest_period_key": row.digest_period_key,
        "cadence": row.cadence,
        "recipient_fingerprint": row.recipient_fingerprint,
        "recipient_domain": row.recipient_domain,
        "recipient_source": row.recipient_source,
        "recipient_verified": bool(row.recipient_verified),
        "subject_line": row.subject_line,
        "body_render_hash": row.body_render_hash,
        "body_byte_length": int(row.body_byte_length or 0),
        "items_total": int(row.items_total or 0),
        "items_visible": int(row.items_visible or 0),
        "delivery_status": row.delivery_status,
        "blocked_reason": row.blocked_reason,
        "audit_event_id": row.audit_event_id,
        "send_attempted": bool(row.send_attempted),
        "provider_contacted": bool(row.provider_contacted),
        "emails_sent": int(row.emails_sent or 0),
        "fact_status": row.fact_status,
        "recorded_at": _iso(row.recorded_at),
        "cancelled_at": _iso(row.cancelled_at),
    }


def list_delivery_intents(
    *,
    connection: Any = None,
    organization_id: Any = None,
    digest_period_key: Any = None,
    include_cancelled: bool = False,
) -> dict[str, Any]:
    """Every intent for one organization, anchored on `organization_id`."""
    blocked: list[str] = []
    anchor = _as_uuid(organization_id)
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_read")
    if anchor is None:
        blocked.append("read_without_an_organization_id_anchor")

    intents: list[dict[str, Any]] = []
    if not blocked:
        statement = sa.select(DELIVERIES).where(DELIVERIES.c.organization_id == anchor)
        if not include_cancelled:
            statement = statement.where(DELIVERIES.c.cancelled_at.is_(None))
        if str(digest_period_key or "").strip():
            statement = statement.where(
                DELIVERIES.c.digest_period_key == str(digest_period_key).strip()
            )
        intents = [
            _row_to_record(row)
            for row in connection.execute(
                statement.order_by(DELIVERIES.c.recorded_at, DELIVERIES.c.id)
            ).all()
        ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(anchor) if anchor else None,
            "intents": intents,
            "rows_read": len(intents),
            "dry_run_recorded_count": sum(
                1 for i in intents if i["delivery_status"] == "dry_run_recorded"
            ),
            "send_disabled_count": sum(
                1 for i in intents if i["delivery_status"] == "send_disabled"
            ),
            "refused_count": sum(
                1 for i in intents if i["delivery_status"] == "recipient_refused"
            ),
            "emails_sent": 0,
            "provider_contacted": False,
            "addresses_stored": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def cancel_delivery_intent(
    *,
    connection: Any = None,
    organization_id: Any = None,
    intent_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Withdraw an intent. An UPDATE; the row stays."""
    blocked: list[str] = []
    anchor = _as_uuid(organization_id)
    target = _as_uuid(intent_id)

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")
    if anchor is None:
        blocked.append("cancel_without_an_organization_id_anchor")
    if target is None:
        blocked.append("cancel_without_an_intent_id")

    moment = now or datetime.now(UTC)
    written = 0
    if not blocked:
        result = connection.execute(
            sa.update(DELIVERIES)
            .where(
                DELIVERIES.c.organization_id == anchor,
                DELIVERIES.c.id == target,
                DELIVERIES.c.cancelled_at.is_(None),
            )
            .values(
                delivery_status="cancelled",
                blocked_reason="cancelled_by_tenant",
                cancelled_at=moment,
            )
        )
        written = int(result.rowcount or 0)
        if not written:
            blocked.append("no_live_delivery_intent_for_this_organization")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(anchor) if anchor else None,
            "intent_id": str(target) if target else None,
            "rows_written": written,
            "rows_deleted": 0,
            "emails_sent": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def queue_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a delivery queue result."""
    fails: list[str] = []

    for field in ("send_attempted", "provider_contacted", "addresses_stored"):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("emails_sent"):
        fails.append("nonzero:emails_sent")
    if result.get("rows_deleted"):
        fails.append("nonzero:rows_deleted")

    status = result.get("delivery_status")
    if status in FORBIDDEN_STATES:
        fails.append(f"delivery_status_asserts_a_real_delivery:{status}")
    if status is not None and status not in DELIVERY_INTENT_STATES:
        fails.append(f"delivery_status_not_recognised:{status}")

    if result.get("rows_written") and result.get("blocked_reasons"):
        fails.append("wrote_a_row_alongside_blockers")

    fingerprint = result.get("recipient_fingerprint")
    if fingerprint and "@" in str(fingerprint):
        fails.append("the_stored_fingerprint_is_an_address")

    for intent in result.get("intents") or []:
        if intent.get("send_attempted"):
            fails.append(f"stored_intent_attempted_a_send:{intent['intent_id']}")
        if intent.get("provider_contacted"):
            fails.append(f"stored_intent_contacted_a_provider:{intent['intent_id']}")
        if intent.get("emails_sent"):
            fails.append(f"stored_intent_sent_email:{intent['intent_id']}")
        if intent.get("delivery_status") in FORBIDDEN_STATES:
            fails.append(f"stored_intent_claims_a_delivery:{intent['intent_id']}")

    rendered = json.dumps(result)
    if "@" in rendered:
        fails.append("queue_result_carries_an_address_shaped_string")

    return fails
