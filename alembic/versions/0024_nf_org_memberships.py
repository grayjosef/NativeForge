"""Alembic 0024: nf_org_memberships (the trusted membership record).

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-23

Gate 62. Approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61.
Approved environment: staging/dev proof first. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MEMBERSHIP_STATES = (
    "invited",
    "pending",
    "active",
    "suspended",
    "revoked",
    "expired",
)

# Only these may be written. client_header / dev_header / cloudflare_access /
# email_domain_only are deliberately absent: an untrusted source must not be
# storable as a membership at all.
TRUSTED_SOURCES = ("verified_directory", "operator_approved", "org_owner_approved")

ROLES = (
    "org_owner",
    "org_admin",
    "authorized_representative",
    "grant_lead",
    "reviewer",
    "viewer",
)


def _in_list(col: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{v}'" for v in values)
    return f"{col} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "nf_org_memberships",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("membership_source", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        # Only membership_record is a trusted role source; an IdP group claim is
        # the identity provider's opinion, not this product's record.
        sa.Column(
            "role_source",
            sa.String(length=64),
            nullable=False,
            server_default="membership_record",
        ),
        sa.Column("invited_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("approved_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("state", MEMBERSHIP_STATES), name="ck_nf_org_memberships_state"
        ),
        sa.CheckConstraint(
            _in_list("membership_source", TRUSTED_SOURCES),
            name="ck_nf_org_memberships_source_trusted",
        ),
        sa.CheckConstraint(
            "role IS NULL OR " + _in_list("role", ROLES),
            name="ck_nf_org_memberships_role",
        ),
        sa.CheckConstraint(
            "role_source IN ('membership_record')",
            name="ck_nf_org_memberships_role_source",
        ),
        # An approval-requiring source must name its approver.
        sa.CheckConstraint(
            "membership_source = 'verified_directory' OR approved_by IS NOT NULL",
            name="ck_nf_org_memberships_approver_required",
        ),
        # One membership per identity per organization.
        sa.UniqueConstraint(
            "organization_id", "identity_id", name="uq_nf_org_memberships_org_identity"
        ),
    )
    op.create_index(
        "ix_nf_org_memberships_organization_id",
        "nf_org_memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_nf_org_memberships_identity_id", "nf_org_memberships", ["identity_id"]
    )
    op.create_index("ix_nf_org_memberships_state", "nf_org_memberships", ["state"])


def downgrade() -> None:
    op.drop_index("ix_nf_org_memberships_state", table_name="nf_org_memberships")
    op.drop_index("ix_nf_org_memberships_identity_id", table_name="nf_org_memberships")
    op.drop_index(
        "ix_nf_org_memberships_organization_id", table_name="nf_org_memberships"
    )
    op.drop_table("nf_org_memberships")
