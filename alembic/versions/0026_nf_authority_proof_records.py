"""Alembic 0026: nf_authority_proof_records (Gate 52 lifecycle).

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-23

Gate 62. Approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61.
Approved environment: staging/dev proof first. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROOF_STATES = (
    "not_started",
    "requested",
    "submitted",
    "under_review",
    "verified",
    "rejected",
    "expired",
    "revoked",
)


def upgrade() -> None:
    joined = ", ".join(f"'{s}'" for s in PROOF_STATES)
    op.create_table(
        "nf_authority_proof_records",
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
        sa.Column("proof_types", sa.JSON(), nullable=True),
        sa.Column("verified_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            f"state IN ({joined})", name="ck_nf_authority_proof_state"
        ),
        # A verified record must name its verifier. Verification by nobody is not
        # verification (Gate 52).
        sa.CheckConstraint(
            "state <> 'verified' OR verified_by IS NOT NULL",
            name="ck_nf_authority_proof_verifier_required",
        ),
    )
    op.create_index(
        "ix_nf_authority_proof_organization_id",
        "nf_authority_proof_records",
        ["organization_id"],
    )
    op.create_index(
        "ix_nf_authority_proof_identity_id",
        "nf_authority_proof_records",
        ["identity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nf_authority_proof_identity_id", table_name="nf_authority_proof_records"
    )
    op.drop_index(
        "ix_nf_authority_proof_organization_id", table_name="nf_authority_proof_records"
    )
    op.drop_table("nf_authority_proof_records")
