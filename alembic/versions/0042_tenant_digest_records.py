"""Alembic 0042: the digest a delivery intent names (Gate 151B).

## The gap this closes, measured

```text
nf_digest_delivery_intents rows        71
  of those, naming a digest_id         71
  digest records they point at          0
```

Every delivery intent in the database names a digest. Not one of those digests
was stored anywhere. Seventy-one rows asserting "we intended to deliver digest
X" where X could not be re-read.

A tenant misses a deadline and asks what NativeForge told them. The intent could
say a digest was queued, with four items visible and two suppressed. The digest
could say nothing, because it did not exist. For a product whose purpose is
award compliance, that is the wrong half of the record to have kept.

## The payload, not the rendering

`digest_payload_json` holds the normalized digest — items, counts, caveats,
suppressions. There is no rendered-body column, and that is deliberate:

```text
the payload   is what the digest IS
the body      is one rendering of it, for one channel, at one moment
```

A table holding something shaped like an email is how a preview-only lane
quietly becomes a delivery lane. The renderer can re-render from the payload and
check `payload_sha256`, which proves the same thing without keeping the artefact.

## No address, ever — the same rule, one table over

0041 wrote it down: a delivery queue is the most downstream thing there is, so
it stores a fingerprint and a domain and "has no column an address could live
in". A digest record is upstream of that and needs neither, so it has neither.
A column that does not exist cannot be filled by a later mistake.

## The counts that must keep agreeing

Gate 140's invariant is `items_total == visible + suppressed + unchanged`. A
records table storing only the visible count would let that invariant stop being
checkable after the fact, which is the failure this gate exists to close. So all
four counts are stored and CHECKed:

```sql
CHECK (items_total >= items_visible + items_suppressed)
CHECK (items_visible >= 0 AND items_suppressed >= 0)
CHECK (items_human_review >= 0)
```

## Nothing here was delivered

```sql
CHECK (delivery_status <> 'sent')
CHECK (NOT email_delivery_live)
CHECK (NOT source_monitoring_live)
```

`queued` is permitted on this table and refused on 0041's, which looks backwards
until you read Gate 104: the builder owns `queued` for a digest whose delivery
was recorded, and 0041 refuses it because an *intent* is not a position in a send
queue. A digest record may carry the builder's own status; it still asserts
nothing left the building, because two other CHECKs say the capabilities are off.

## One live record per organization and digest

A partial unique index on `(organization_id, digest_id)` where
`archived_at IS NULL`. The digest id is already deterministic — sha256 over
tenant, cadence and period, with no clock in it since Gate 142 — so it is a real
key rather than a surrogate, and persisting the same period twice is a defect
rather than a second row.

Archive is a state, not a delete: an audit of a missed deadline needs the digest
that was current at the time, not only the current one.

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-12

Gate 151. Demo/dev scope. No email is sent by this migration or by anything
that reads this table, no provider is contacted, no live source is called, and
no object store is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | Sequence[str] | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECORDS = "nf_tenant_digest_records"

#: Bridged from Gate 104's `CADENCES` rather than restated with different
#: members, the same way 0041 bridged them.
DIGEST_CADENCES = ("weekly", "daily", "manual_preview", "unknown")

#: What happened to this digest. `preview_only` is the normal answer and the
#: one every row carries today; `queued` records that a dry-run intent was
#: written against it, which is still not a send.
DIGEST_DELIVERY_STATES = (
    "preview_only",
    "queued",
    "cancelled",
    "needs_human_review",
    "unknown",
)

#: The campaign's fact vocabulary. `tenant_supplied` is permitted by the
#: constraint because the column means what it means everywhere else - but
#: nothing writes it, because Gate 148's guard refuses customer data without a
#: consent record that does not exist.
FACT_STATUSES = ("demo_fixture", "tenant_supplied", "verified", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        RECORDS,
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
        # Deterministic: sha256 over tenant, cadence and period. No clock.
        sa.Column("digest_id", sa.Text(), nullable=False),
        sa.Column("digest_period_key", sa.Text(), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        # The digest itself, normalized. Not a rendering of it.
        sa.Column("digest_payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("snapshot_ids", sa.JSON(), nullable=True),
        # The four counts, so Gate 140's invariant stays checkable afterwards.
        sa.Column("items_total", sa.Integer(), nullable=False),
        sa.Column("items_visible", sa.Integer(), nullable=False),
        sa.Column("items_suppressed", sa.Integer(), nullable=False),
        sa.Column("items_unchanged", sa.Integer(), nullable=False),
        # The honesty counts. Dropping any of these would let a digest look
        # more certain after the fact than it was at the time.
        sa.Column("items_human_review", sa.Integer(), nullable=False),
        sa.Column("items_with_unverified_deadlines", sa.Integer(), nullable=False),
        sa.Column(
            "items_with_unknown_reporting_burden", sa.Integer(), nullable=False
        ),
        sa.Column("caveats_json", sa.JSON(), nullable=True),
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        # Stored so the record states the capabilities were off when it was
        # written, rather than a reader inferring it from the date.
        sa.Column(
            "email_delivery_live",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "source_monitoring_live",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # -- the counts keep agreeing -----------------------------------------
        sa.CheckConstraint(
            "items_total >= items_visible + items_suppressed",
            name=f"ck_{RECORDS}_counts_agree",
        ),
        sa.CheckConstraint(
            "items_visible >= 0 AND items_suppressed >= 0 "
            "AND items_unchanged >= 0 AND items_total >= 0",
            name=f"ck_{RECORDS}_counts_non_negative",
        ),
        sa.CheckConstraint(
            "items_human_review >= 0 "
            "AND items_with_unverified_deadlines >= 0 "
            "AND items_with_unknown_reporting_burden >= 0",
            name=f"ck_{RECORDS}_honesty_counts_non_negative",
        ),
        # -- nothing here was delivered ---------------------------------------
        sa.CheckConstraint(
            "delivery_status <> 'sent'",
            name=f"ck_{RECORDS}_never_sent",
        ),
        sa.CheckConstraint(
            "NOT email_delivery_live",
            name=f"ck_{RECORDS}_email_delivery_off",
        ),
        sa.CheckConstraint(
            "NOT source_monitoring_live",
            name=f"ck_{RECORDS}_source_monitoring_off",
        ),
        # -- the vocabularies --------------------------------------------------
        sa.CheckConstraint(
            _in_list("cadence", DIGEST_CADENCES),
            name=f"ck_{RECORDS}_cadence",
        ),
        sa.CheckConstraint(
            _in_list("delivery_status", DIGEST_DELIVERY_STATES),
            name=f"ck_{RECORDS}_delivery_status",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name=f"ck_{RECORDS}_fact_status",
        ),
        # A demo fixture is never anything but a demo fixture.
        sa.CheckConstraint(
            "(NOT is_demo) OR fact_status = 'demo_fixture'",
            name=f"ck_{RECORDS}_demo_is_fixture",
        ),
        # A hash that is not a sha256 is not a hash somebody can check.
        sa.CheckConstraint(
            "length(payload_sha256) = 64",
            name=f"ck_{RECORDS}_payload_sha256_shape",
        ),
    )

    op.create_index(
        f"ix_{RECORDS}_organization_id", RECORDS, ["organization_id"]
    )
    op.create_index(
        f"ix_{RECORDS}_digest_id", RECORDS, ["organization_id", "digest_id"]
    )
    # One live record per organization and digest. The id is deterministic, so
    # a second live row for the same period is a defect rather than a version.
    op.create_index(
        f"uq_{RECORDS}_live_digest",
        RECORDS,
        ["organization_id", "digest_id"],
        unique=True,
        sqlite_where=sa.text("archived_at IS NULL"),
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute(f"ALTER TABLE {RECORDS} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {RECORDS}_org_isolation ON {RECORDS}
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
        op.execute(f"DROP POLICY IF EXISTS {RECORDS}_org_isolation ON {RECORDS}")
    op.drop_index(f"uq_{RECORDS}_live_digest", table_name=RECORDS)
    op.drop_index(f"ix_{RECORDS}_digest_id", table_name=RECORDS)
    op.drop_index(f"ix_{RECORDS}_organization_id", table_name=RECORDS)
    op.drop_table(RECORDS)
