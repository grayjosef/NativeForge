"""Alembic 0032: nf_awarded_grants (Gate 124B).

Where an awarded grant lives. Not a pursuit, and not a projection.

## Three tables that are not this one

```text
nf_grant_sparks        a discovered opportunity                  0004
nf_grant_pursuits      one being chased                          0007
nf_spark_requirements  what a NOFO asks of an applicant, before  0005
```

All three are pursuit-side. Gate 91 exists to keep them apart from an award, and
Gate 124A found no awarded-grant table at all — nine services, ~3,800 lines of
contract, and nowhere to put a row.

## projected burden is not an active obligation

The rule this table must not break, in the form it takes in code:

```text
pursuit_reporting_burden_projection_service
  every field prefixed `projected_`
  every result carries `is_active_obligation: False`
```

A projection is what a NOFO *suggests* will be required if you win. An
obligation is what an award *does* require now. `active_obligation_status` is
its own column, derived from this award's own extraction status and never from
anything on the pursuit side.

## Lineage is text, and text is not a reason

`source_pursuit_id` and `source_opportunity_id` record where an award came from.
Both are `text` with **no foreign key**, deliberately:

```text
a foreign key would make a pursuit's existence a precondition for an award,
and an award can arrive for something nobody pursued in this system
```

They are also never a reason to create an award. Gate 91's separation means a
pursuit reaching "submitted" produces no row here; a human recording an award
does.

## Archive, never delete

`archived_at` is set and the row stays. `mistaken_award` is an award status, not
a deletion — an award recorded and later found not to exist is a fact about what
happened, and a funder's audit does not accept "we removed it".

## No rows are inserted

Nothing writes here. A production write needs `customer_auth_live` and a
verified operational binding, and Gates 115-123 measured both as false.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_awarded_grants"

# Gate 91/108 vocabularies, restated because a CHECK constraint cannot import
# Python. A test asserts these match the services' frozensets exactly, so the
# two cannot drift.
AWARD_STATUSES = (
    "draft_award_record",
    "active_award",
    "closeout_pending",
    "closed",
    "cancelled",
    "mistaken_award",
    "unknown",
)

# What this award actually obliges the tenant to do, now. Separate from any
# projection, and separate from the award's own status: an award can be active
# and its obligations not yet established.
ACTIVE_OBLIGATION_STATUSES = (
    "no_obligations_established",
    "obligations_established",
    "obligations_closed",
    "needs_human_review",
    "unknown",
)

# Gate 103's status vocabulary, reused: a fact somebody guessed and one somebody
# confirmed are different objects.
FACT_STATUSES = (
    "verified",
    "tenant_supplied",
    "demo_fixture",
    "unknown",
    "needs_human_review",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The RLS anchor. Everything else is a label, a fact or an audit trail.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Optional context, never authority. An award belongs to an
        # organization; a beta profile is how that organization wants to be
        # served.
        sa.Column(
            "tenant_beta_profile_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_tenant_beta_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Labels. No foreign key, never an anchor.
        sa.Column("tenant_id_label", sa.Text(), nullable=True),
        sa.Column("customer_org_id_label", sa.Text(), nullable=True),
        # Lineage. Text, no foreign key: a foreign key would make a pursuit's
        # existence a precondition for an award, and an award can arrive for
        # something nobody pursued in this system.
        sa.Column("source_pursuit_id", sa.Text(), nullable=True),
        sa.Column("source_opportunity_id", sa.Text(), nullable=True),
        # -- the award ------------------------------------------------------
        sa.Column("award_number", sa.Text(), nullable=True),
        sa.Column("award_title", sa.Text(), nullable=False),
        sa.Column("funder_name", sa.Text(), nullable=True),
        sa.Column("program_name", sa.Text(), nullable=True),
        sa.Column("award_status", sa.String(length=32), nullable=False),
        # Numeric, not float: an award amount is money and a float is a
        # rounding error waiting for an audit.
        sa.Column("award_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("award_currency", sa.String(length=3), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        # -- the obligation, which is not the award's status ----------------
        sa.Column("active_obligation_status", sa.String(length=32), nullable=False),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        # -- lifecycle and audit --------------------------------------------
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Set once, never cleared. Archiving is one-way.
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Matches the 0003/0027/0031 policy shape, which scopes on org AND demo.
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            _in_list("award_status", AWARD_STATUSES),
            name="ck_nf_awarded_grants_award_status",
        ),
        sa.CheckConstraint(
            _in_list("active_obligation_status", ACTIVE_OBLIGATION_STATUSES),
            name="ck_nf_awarded_grants_obligation_status",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_awarded_grants_fact_status",
        ),
        # An award title is the one thing that cannot be unknown: a row nobody
        # can name is a row nobody can act on.
        sa.CheckConstraint(
            "length(trim(award_title)) > 0",
            name="ck_nf_awarded_grants_title_not_blank",
        ),
        # A period that ends before it starts is a data-entry error, not a
        # short award.
        sa.CheckConstraint(
            "period_start IS NULL OR period_end IS NULL OR period_end >= period_start",
            name="ck_nf_awarded_grants_period_order",
        ),
        # Money without a currency is a number. Both or neither.
        sa.CheckConstraint(
            "(award_amount IS NULL) = (award_currency IS NULL)",
            name="ck_nf_awarded_grants_amount_needs_currency",
        ),
        # An amount nobody established cannot be recorded as settled. The same
        # rule Gate 123 applied to recognition status.
        sa.CheckConstraint(
            "award_amount IS NOT NULL OR "
            "fact_status IN ('unknown', 'needs_human_review', 'demo_fixture')",
            name="ck_nf_awarded_grants_unknown_amount_is_unestablished",
        ),
        # Obligations cannot be established while nobody has established
        # anything about the award. This is the constraint that stops a
        # projected burden being written in as an active obligation.
        sa.CheckConstraint(
            "active_obligation_status <> 'obligations_established' OR "
            "fact_status IN ('verified', 'tenant_supplied')",
            name="ck_nf_awarded_grants_obligations_need_established_facts",
        ),
    )

    # One live award per organization and award number. A cancelled or mistaken
    # award stays for the audit trail and does not block a corrected one.
    op.create_index(
        "uq_nf_awarded_grants_active_number",
        TABLE,
        ["organization_id", "award_number"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL AND award_number IS NOT NULL"),
        sqlite_where=sa.text("archived_at IS NULL AND award_number IS NOT NULL"),
    )
    op.create_index("ix_nf_awarded_grants_organization", TABLE, ["organization_id"])
    op.create_index("ix_nf_awarded_grants_period_end", TABLE, ["period_end"])

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002, 0027, 0029 and
        # 0031 behave.
        return
    conn.execute(text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;"))
    conn.execute(text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;"))
    conn.execute(
        text(
            f"""
CREATE POLICY {TABLE}_org_demo_scope ON {TABLE}
  USING (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
  WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  );
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"DROP POLICY IF EXISTS {TABLE}_org_demo_scope ON {TABLE};"))
    op.drop_index("ix_nf_awarded_grants_period_end", table_name=TABLE)
    op.drop_index("ix_nf_awarded_grants_organization", table_name=TABLE)
    op.drop_index("uq_nf_awarded_grants_active_number", table_name=TABLE)
    op.drop_table(TABLE)
