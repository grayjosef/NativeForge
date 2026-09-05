"""Alembic 0041: the dry-run digest delivery queue (Gate 142E).

## What this table is

A record of an **intention to deliver**, and nothing more. Doc 741 found the
constraint that shapes it: Gate 104's digest builder already owns the word
`queued`, and lists it under `DELIVERED_STATUSES` — "statuses that assert
something left the building".

Nothing leaves the building here. So this table has its own vocabulary,
starting at `dry_run_recorded`, and the digest it names keeps
`delivery_status: preview_only`. A row here is a plan; it is not a position in
anybody's send queue.

## No address, ever

`nf_identities.email` holds a real address because OIDC handed it over. Every
row downstream of that holds a fingerprint instead — `nf_membership_invites`
has carried `invited_email_domain` plus `invited_email_fingerprint` since 0039,
and the reason is written into `membership_invite_repository_service`:

> enough for acceptance to require that the identity accepting is the identity
> invited, without the row holding the address that would let something else
> send to it.

A delivery queue is the most downstream thing there is, so it stores
`recipient_fingerprint` (sha256[:32] of the lowercased address, the same
function) and `recipient_domain`, and has no column an address could live in.
That is not a convention this migration hopes callers follow — there is
physically nowhere to put one.

## `send_attempted` is stored, defaulted false, and CHECKed

```sql
CHECK (NOT send_attempted)
CHECK (NOT provider_contacted)
CHECK (delivery_status <> 'sent' AND delivery_status <> 'queued')
```

Three constraints the database enforces rather than a service promising. A
future gate that activates sending will have to remove them deliberately, in a
migration somebody reviews, rather than by changing a default somewhere.

## One live intent per digest period and recipient

A partial unique index on
`(organization_id, digest_period_key, recipient_fingerprint)` where
`cancelled_at IS NULL`. Recording the same intention twice is how a tenant gets
two copies of one digest the day sending is switched on.

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-04

Gate 142. Demo/dev scope. No email is sent by this migration or by anything
that reads this table, no provider is contacted, and no live source is called.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | Sequence[str] | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DELIVERIES = "nf_digest_delivery_intents"

#: The queue's own vocabulary. `queued` and `sent` are deliberately ABSENT:
#: Gate 104's builder owns those words for something that actually left, and a
#: dry run that borrowed them would make the digest's own invariant a lie.
DELIVERY_INTENT_STATES = (
    "dry_run_recorded",
    "send_disabled",
    "recipient_refused",
    "cancelled",
    "needs_human_review",
    "unknown",
)

#: Why this intent will not become a delivery. Every row carries one, including
#: the ones that are fine - `send_activation_absent` is the normal answer and
#: naming it beats leaving the field null and letting a reader guess.
DELIVERY_BLOCKED_REASONS = (
    "send_activation_absent",
    "no_email_provider_configured",
    "recipient_not_verified",
    "recipient_domain_not_allowed",
    "recipient_shape_invalid",
    "digest_not_deliverable",
    "cancelled_by_tenant",
    "human_review_required",
    "unknown",
)

#: How a recipient came to be on this intent.
RECIPIENT_SOURCES = (
    "org_membership",
    "controlled_fixture",
    "tenant_requested",
    "needs_human_review",
    "unknown",
)

#: The cadences a digest can be delivered on. Bridged from Gate 104's
#: `CADENCES` rather than restated with different members.
DELIVERY_CADENCES = ("weekly", "daily", "manual_preview", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        DELIVERIES,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        # A label. `organization_id` above is the only authority.
        sa.Column("tenant_id_label", sa.Text(), nullable=True),
        # Which digest, and for which period. `digest_period_key` is what makes
        # "already recorded for this week" answerable without a date range join.
        sa.Column("digest_id", sa.Text(), nullable=True),
        sa.Column("digest_period_key", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        # The recipient, as a handle and a domain. There is no address column.
        sa.Column("recipient_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("recipient_domain", sa.String(length=255), nullable=True),
        sa.Column("recipient_source", sa.String(length=32), nullable=False),
        sa.Column("recipient_verified", sa.Boolean(), nullable=False),
        # What was going to be delivered, described rather than carried.
        sa.Column("subject_line", sa.Text(), nullable=True),
        sa.Column("body_render_hash", sa.String(length=64), nullable=True),
        sa.Column("body_byte_length", sa.Integer(), nullable=True),
        sa.Column("items_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_visible", sa.Integer(), nullable=False, server_default="0"),
        # The state, and why it stops here.
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("blocked_reason", sa.String(length=48), nullable=False),
        sa.Column("blocked_reasons", sa.Text(), nullable=True),
        # The three facts a CHECK enforces below.
        sa.Column(
            "send_attempted", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "provider_contacted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("audit_event_id", sa.Text(), nullable=True),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("delivery_status", DELIVERY_INTENT_STATES),
            name="ck_nf_digest_delivery_intents_status",
        ),
        sa.CheckConstraint(
            _in_list("blocked_reason", DELIVERY_BLOCKED_REASONS),
            name="ck_nf_digest_delivery_intents_blocked_reason",
        ),
        sa.CheckConstraint(
            _in_list("recipient_source", RECIPIENT_SOURCES),
            name="ck_nf_digest_delivery_intents_recipient_source",
        ),
        sa.CheckConstraint(
            _in_list("cadence", DELIVERY_CADENCES),
            name="ck_nf_digest_delivery_intents_cadence",
        ),
        # Nothing left the building. Enforced here so a future send has to be
        # a migration somebody reviews, not a changed default.
        sa.CheckConstraint(
            "NOT send_attempted",
            name="ck_nf_digest_delivery_intents_no_send_attempted",
        ),
        sa.CheckConstraint(
            "NOT provider_contacted",
            name="ck_nf_digest_delivery_intents_no_provider_contacted",
        ),
        sa.CheckConstraint(
            "emails_sent = 0",
            name="ck_nf_digest_delivery_intents_no_emails_sent",
        ),
        # A row may not claim a status Gate 104 reserved for a real delivery.
        sa.CheckConstraint(
            "delivery_status <> 'queued' AND delivery_status <> 'sent'",
            name="ck_nf_digest_delivery_intents_not_a_real_delivery",
        ),
        # A fingerprint is 32 hex characters. An address is not, and this is
        # the column somebody would put one in.
        sa.CheckConstraint(
            "length(recipient_fingerprint) = 32",
            name="ck_nf_digest_delivery_intents_fingerprint_shape",
        ),
        sa.CheckConstraint(
            "recipient_fingerprint NOT LIKE '%@%'",
            name="ck_nf_digest_delivery_intents_fingerprint_is_not_an_address",
        ),
    )
    op.create_index(f"ix_{DELIVERIES}_organization_id", DELIVERIES, ["organization_id"])
    op.create_index(
        f"uq_{DELIVERIES}_live_intent",
        DELIVERIES,
        ["organization_id", "digest_period_key", "recipient_fingerprint"],
        unique=True,
        sqlite_where=sa.text("cancelled_at IS NULL"),
        postgresql_where=sa.text("cancelled_at IS NULL"),
    )

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {DELIVERIES} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {DELIVERIES}_org_isolation ON {DELIVERIES}
            USING (
                organization_id = current_setting('app.current_org_id', true)::uuid
                AND is_demo =
                    current_setting('app.current_org_is_demo', true)::boolean
            )
            """
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"DROP POLICY IF EXISTS {DELIVERIES}_org_isolation ON {DELIVERIES}")
    op.drop_index(f"uq_{DELIVERIES}_live_intent", table_name=DELIVERIES)
    op.drop_index(f"ix_{DELIVERIES}_organization_id", table_name=DELIVERIES)
    op.drop_table(DELIVERIES)
