"""Alembic 0029: nf_tenant_customer_org_bindings (Gate 113).

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-29

The store Gate 110 decided on, built empty.

Anchored on ``organization_id`` because that is the only identity this database
enforces: every RLS policy reads
``organization_id = current_setting('app.current_org_id', true)::uuid``.

``tenant_id`` and ``customer_org_id`` are ``text`` and carry no foreign key,
deliberately. They are labels. A label with a foreign key becomes an identity
space by accident, which is the whole problem Gates 109-112 exist to prevent.

No rows are inserted. Gate 110 reported ``migration_safe_now: False`` for three
reasons - no customer auth to supply a verifier, no persistence to write into,
no verified binding to store. Those are reasons not to *store a verified
binding*; none of them is a reason the table cannot exist. It stays empty until
somebody can be a verifier.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_tenant_customer_org_bindings"

# Gate 109's vocabulary, restated here because a CHECK constraint cannot import
# Python. A test asserts these match the service's frozensets exactly, so the
# two cannot drift.
BINDING_STATUSES = (
    "unbound",
    "pending_review",
    "demo_fixture",
    "verified_binding",
    "conflict",
    "revoked",
    "unknown",
)

BINDING_SOURCES = (
    "human_entered",
    "admin_verified",
    "migration_import",
    "demo_fixture",
    "system_inferred_blocked",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The RLS anchor. Everything else on this row is a label or an audit fact.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Labels. No foreign key, no uniqueness of their own, never an anchor.
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("customer_org_id", sa.Text(), nullable=False),
        sa.Column("binding_status", sa.String(length=32), nullable=False),
        sa.Column("binding_source", sa.String(length=32), nullable=False),
        sa.Column("binding_confidence", sa.String(length=16), nullable=False),
        sa.Column(
            "verified_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Matches the 0027 policy shape, which scopes on org AND demo.
        sa.Column(
            "is_demo", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "blocked_reasons", sa.JSON(), nullable=False, server_default="[]"
        ),
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
            _in_list("binding_status", BINDING_STATUSES),
            name="ck_nf_binding_status",
        ),
        sa.CheckConstraint(
            _in_list("binding_source", BINDING_SOURCES),
            name="ck_nf_binding_source",
        ),
        # A verified binding names its verifier and when. Without both it is an
        # assertion wearing the word "verified".
        sa.CheckConstraint(
            "binding_status <> 'verified_binding' OR ("
            "verified_at IS NOT NULL AND verified_by_identity_id IS NOT NULL)",
            name="ck_nf_binding_verified_needs_verifier",
        ),
        # A demo binding is never production verification, so it never carries a
        # verifier at all.
        sa.CheckConstraint(
            "binding_status <> 'demo_fixture' OR ("
            "verified_at IS NULL AND verified_by_identity_id IS NULL)",
            name="ck_nf_binding_demo_has_no_verifier",
        ),
    )

    # One live binding per (organization, tenant label, customer label). A
    # revoked row stays for the audit trail and does not block a new one.
    op.create_index(
        "uq_nf_binding_active",
        TABLE,
        ["organization_id", "tenant_id", "customer_org_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index("ix_nf_binding_organization", TABLE, ["organization_id"])

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002 and 0027 behave.
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
        conn.execute(
            text(f"DROP POLICY IF EXISTS {TABLE}_org_demo_scope ON {TABLE};")
        )
    op.drop_index("ix_nf_binding_organization", table_name=TABLE)
    op.drop_index("uq_nf_binding_active", table_name=TABLE)
    op.drop_table(TABLE)
