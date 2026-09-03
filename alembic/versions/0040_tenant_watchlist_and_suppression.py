"""Alembic 0040: the two tables the digest needs to survive a request (Gate 140B/D).

## `nf_source_watchlist_entries`

Gate 138's capability matrix reported this lane absent on all three counts — no
table, no repository, no contract — and it stayed false honestly for two gates.
It is what a tenant's "watch these sources" means, and without it a watchlist is
a thing you can hold in one request and lose in the next.

## `nf_tenant_pursuit_suppressions`

`tenant_pursuit_suppression_service` has existed since Gate 104 with statuses,
reasons, an id builder and a `is_suppressed_for_tenant` the digest builder
already consults. Nothing ever wrote one down.

So "once pursuit starts, the item disappears from future digests" was true
inside a single call and false between them. This is the row that makes it true
across requests.

## Both anchor on organization_id, and neither on tenant_id

`tenant_pursuit_suppression_service` keys its in-memory records on `tenant_id`,
which is a **label** — Gates 109 through 113 settled that it is never authority,
and Gate 137 restated it for bindings.

So these tables anchor on `organization_id`, the column every RLS policy in this
schema compares against, and carry `tenant_id_label` beside it as a label that
narrows a read and never selects one. A caller cannot reach another
organization's suppression by knowing its tenant label.

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

## Suppression retains, never deletes

`source_history_preserved` and `provenance_preserved` are stored `NOT NULL` and
a CHECK requires both true on every row. Suppressing an opportunity hides it
from a view; it must not be a way to make the source record go away, and the
row says so rather than the docstring saying so.

Revision ID: 0040
Revises: 0039
Create Date: 2026-09-03

Gate 140. Demo/dev scope. No live source is called by this migration or by
anything that reads these tables, and no email is sent.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | Sequence[str] | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WATCHLIST = "nf_source_watchlist_entries"
SUPPRESSIONS = "nf_tenant_pursuit_suppressions"

#: Bridged from the source registry's vocabulary rather than restated. A test
#: parses this migration and compares.
WATCHLIST_STATES = (
    "watching",
    "paused",
    "archived",
    "needs_human_review",
    "unknown",
)

#: Where a watchlist entry came from. `controlled_fixture` is the only one this
#: gate can produce - nothing here contacts a registry.
WATCHLIST_SOURCES = (
    "registry_entry",
    "controlled_fixture",
    "tenant_requested",
    "needs_human_review",
    "unknown",
)

SUPPRESSION_STATES = (
    "not_suppressed",
    "suppressed_from_new_digest",
    "suppressed_from_daily_alert",
    "suppressed_from_weekly_digest",
    "human_review_required",
    "unknown",
)

SUPPRESSION_REASONS = (
    "pursuit_started",
    "pursuit_submitted",
    "pursuit_awarded",
    "pursuit_declined",
    "tenant_requested",
    "human_review_pending",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        WATCHLIST,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        # A label. Narrows a read, never selects one.
        sa.Column("tenant_id_label", sa.Text(), nullable=True),
        # The registry id or the controlled fixture id. Text, because a
        # registry id is not a UUID in this schema.
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("jurisdiction", sa.String(length=64), nullable=True),
        sa.Column("program_area", sa.String(length=128), nullable=True),
        sa.Column("watchlist_state", sa.String(length=32), nullable=False),
        sa.Column("watchlist_source", sa.String(length=32), nullable=False),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column("human_review_required", sa.Boolean(), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False),
        sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("watchlist_state", WATCHLIST_STATES),
            name=f"ck_{WATCHLIST}_state",
        ),
        sa.CheckConstraint(
            _in_list("watchlist_source", WATCHLIST_SOURCES),
            name=f"ck_{WATCHLIST}_source",
        ),
        # One live entry per organization and source. A second is a duplicate
        # of the same statement, and an archived one stops blocking a
        # replacement without disappearing - the shape migration 0029 chose.
        sa.Index(
            f"uq_{WATCHLIST}_live",
            "organization_id",
            "source_id",
            unique=True,
            sqlite_where=sa.text("archived_at IS NULL"),
            postgresql_where=sa.text("archived_at IS NULL"),
        ),
    )
    op.create_index(f"ix_{WATCHLIST}_organization_id", WATCHLIST, ["organization_id"])

    op.create_table(
        SUPPRESSIONS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("tenant_id_label", sa.Text(), nullable=True),
        sa.Column("opportunity_id", sa.Text(), nullable=False),
        sa.Column("suppression_status", sa.String(length=48), nullable=False),
        sa.Column("suppression_reason", sa.String(length=48), nullable=False),
        sa.Column("pursuit_record_id", sa.Text(), nullable=True),
        sa.Column("audit_event_id", sa.Text(), nullable=True),
        # Both stored, and both required true. Suppression hides a view; it is
        # not a way to make the source record go away.
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
            _in_list("suppression_status", SUPPRESSION_STATES),
            name=f"ck_{SUPPRESSIONS}_status",
        ),
        sa.CheckConstraint(
            _in_list("suppression_reason", SUPPRESSION_REASONS),
            name=f"ck_{SUPPRESSIONS}_reason",
        ),
        # The refusal that keeps suppression from becoming deletion.
        sa.CheckConstraint(
            "source_history_preserved AND provenance_preserved",
            name=f"ck_{SUPPRESSIONS}_retains_the_record",
        ),
        sa.Index(
            f"uq_{SUPPRESSIONS}_live",
            "organization_id",
            "opportunity_id",
            unique=True,
            sqlite_where=sa.text("lifted_at IS NULL"),
            postgresql_where=sa.text("lifted_at IS NULL"),
        ),
    )
    op.create_index(
        f"ix_{SUPPRESSIONS}_organization_id", SUPPRESSIONS, ["organization_id"]
    )

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for table in (WATCHLIST, SUPPRESSIONS):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"""
                CREATE POLICY {table}_org_isolation ON {table}
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
        for table in (WATCHLIST, SUPPRESSIONS):
            op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")
    op.drop_index(f"ix_{SUPPRESSIONS}_organization_id", table_name=SUPPRESSIONS)
    op.drop_table(SUPPRESSIONS)
    op.drop_index(f"ix_{WATCHLIST}_organization_id", table_name=WATCHLIST)
    op.drop_table(WATCHLIST)
