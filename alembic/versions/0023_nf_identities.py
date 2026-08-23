"""Alembic 0023: nf_identities (verified OIDC subject -> internal id).

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-23

Gate 62. Approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61.
Approved environment: staging/dev proof first. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None



def upgrade() -> None:
    op.create_table(
        "nf_identities",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The verified OIDC subject. Unique per issuer, never per email: an email
        # can be reassigned, a subject cannot.
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "verification_source",
            sa.String(length=64),
            nullable=False,
            server_default="oidc_token_signature",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "verification_source IN ('oidc_token_signature')",
            name="ck_nf_identities_verification_source",
        ),
        sa.UniqueConstraint(
            "issuer", "subject", name="uq_nf_identities_issuer_subject"
        ),
    )
    op.create_index("ix_nf_identities_subject", "nf_identities", ["subject"])
    op.create_index("ix_nf_identities_email", "nf_identities", ["email"])


def downgrade() -> None:
    op.drop_index("ix_nf_identities_email", table_name="nf_identities")
    op.drop_index("ix_nf_identities_subject", table_name="nf_identities")
    op.drop_table("nf_identities")
