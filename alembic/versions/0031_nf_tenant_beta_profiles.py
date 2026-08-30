"""Alembic 0031: nf_tenant_beta_profiles (Gate 123C).

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-30

How a tenant wants NativeForge to behave. Not who the Tribe is.

## Why this is not nf_tribal_profiles

`nf_tribal_profiles` (0003) is the grant-application identity: UEI, EIN, SAM
registration, addresses, contacts, boilerplate narratives. It answers "who is
this Tribe when a form is submitted".

This table answers a different question: which states they operate in, which
applicant classes they may file under, what they want watched, how often they
want a digest, where alerts route. Gate 123A found the two share not one column.

They also differ in the way that decides a schema. Gate 103 tracks a
`fact_status` per field — `verified`, `tenant_supplied`, `demo_fixture`,
`unknown`, `needs_human_review` — because a recognition status somebody guessed
and one somebody confirmed are different objects. `nf_tribal_profiles` has no
such column, and merging would produce a 38-column table where half the rows
carry a fact status and half do not.

## operating_states is not a mailing address

The single most consequential column here. A tenant may operate, serve and be
eligible in a state it is not headquartered in, and Gate 103's
`INFERENCE_PROHIBITED` names `operating_state_from_mailing_address` as a
refusal. State-source matching reads `operating_states` and nothing else.

Stored as JSON rather than a delimited string so a state can never be produced
by splitting an address on a comma.

## Archive, never delete

`archived_at` is set and the row stays. A digest complaint is debugged against
the profile that produced it, and a deleted profile makes that impossible. There
is no DELETE path in the repository and an invariant refuses any result claiming
one.

## No rows are inserted

Nothing writes here. A production write needs `customer_auth_live` and a
verified operational binding, and Gates 115-122 measured both as false. A row
asserting a tenant's recognition status while nobody can be authenticated as
that tenant is a fabricated fact in a table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_tenant_beta_profiles"

# Gate 103's vocabularies, restated because a CHECK constraint cannot import
# Python. A test asserts these match the service's frozensets exactly, so the
# two cannot drift.
RECOGNITION_STATUSES = (
    "federally_recognized",
    "state_recognized",
    "historic_affiliation",
    "unrecognized",
    "unknown",
)

DIGEST_FREQUENCIES = ("weekly", "daily", "none")

FACT_STATUSES = (
    "verified",
    "tenant_supplied",
    "demo_fixture",
    "unknown",
    "needs_human_review",
)

PROFILE_STATUSES = ("draft", "active", "archived", "needs_human_review")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The RLS anchor. Everything else is a preference, a label or an audit
        # fact.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Labels. No foreign key, no uniqueness of their own, never an anchor.
        sa.Column("tenant_id_label", sa.Text(), nullable=False),
        sa.Column("customer_org_id_label", sa.Text(), nullable=True),
        # -- the facts, each with a status ---------------------------------
        sa.Column("recognition_status", sa.String(length=32), nullable=False),
        sa.Column(
            "recognition_status_fact_status", sa.String(length=32), nullable=False
        ),
        # JSON, not a delimited string: a state must never be produced by
        # splitting an address on a comma.
        sa.Column("operating_states", sa.JSON(), nullable=False),
        sa.Column("operating_states_fact_status", sa.String(length=32), nullable=False),
        sa.Column("service_area", sa.Text(), nullable=True),
        sa.Column("applicant_classes", sa.JSON(), nullable=False),
        sa.Column(
            "applicant_classes_fact_status", sa.String(length=32), nullable=False
        ),
        # -- the preferences ------------------------------------------------
        sa.Column("programs", sa.JSON(), nullable=False),
        sa.Column("departments", sa.JSON(), nullable=False),
        sa.Column("priority_topics", sa.JSON(), nullable=False),
        sa.Column("excluded_topics", sa.JSON(), nullable=False),
        sa.Column("source_watchlist_preferences", sa.JSON(), nullable=False),
        sa.Column("digest_frequency", sa.String(length=16), nullable=False),
        sa.Column("routing_rules", sa.JSON(), nullable=False),
        sa.Column("custom_alerts", sa.JSON(), nullable=False),
        # -- lifecycle and audit --------------------------------------------
        sa.Column("profile_status", sa.String(length=32), nullable=False),
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
        # Matches the 0003 and 0027 policy shape, which scopes on org AND demo.
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
            _in_list("recognition_status", RECOGNITION_STATUSES),
            name="ck_nf_tenant_beta_recognition_status",
        ),
        sa.CheckConstraint(
            _in_list("digest_frequency", DIGEST_FREQUENCIES),
            name="ck_nf_tenant_beta_digest_frequency",
        ),
        sa.CheckConstraint(
            _in_list("profile_status", PROFILE_STATUSES),
            name="ck_nf_tenant_beta_profile_status",
        ),
        sa.CheckConstraint(
            _in_list("recognition_status_fact_status", FACT_STATUSES),
            name="ck_nf_tenant_beta_recognition_fact_status",
        ),
        sa.CheckConstraint(
            _in_list("operating_states_fact_status", FACT_STATUSES),
            name="ck_nf_tenant_beta_operating_states_fact_status",
        ),
        sa.CheckConstraint(
            _in_list("applicant_classes_fact_status", FACT_STATUSES),
            name="ck_nf_tenant_beta_applicant_classes_fact_status",
        ),
        # An archived profile says when. Without the timestamp the status is an
        # assertion nothing can order.
        sa.CheckConstraint(
            "profile_status <> 'archived' OR archived_at IS NOT NULL",
            name="ck_nf_tenant_beta_archived_needs_timestamp",
        ),
        # An unknown recognition status is never a settled fact. This is the
        # constraint that stops a guess being written as established.
        sa.CheckConstraint(
            "recognition_status <> 'unknown' OR "
            "recognition_status_fact_status IN ('unknown', 'needs_human_review')",
            name="ck_nf_tenant_beta_unknown_recognition_is_unestablished",
        ),
    )

    # One live profile per organization. An archived row stays for the audit
    # trail and does not block a replacement.
    op.create_index(
        "uq_nf_tenant_beta_profile_active",
        TABLE,
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
        sqlite_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_nf_tenant_beta_profile_organization", TABLE, ["organization_id"]
    )

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002, 0027 and 0029
        # behave.
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
    op.drop_index("ix_nf_tenant_beta_profile_organization", table_name=TABLE)
    op.drop_index("uq_nf_tenant_beta_profile_active", table_name=TABLE)
    op.drop_table(TABLE)
