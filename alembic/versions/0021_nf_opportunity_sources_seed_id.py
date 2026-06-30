"""SH: nf_opportunity_sources seed_id identity (registry re-key off URL).

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nf_opportunity_sources",
        sa.Column("seed_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "nf_opportunity_sources",
        sa.Column("canonical_source_id", sa.String(length=256), nullable=True),
    )
    op.create_index(
        "ix_nf_opportunity_sources_seed_id",
        "nf_opportunity_sources",
        ["seed_id"],
        unique=False,
    )
    op.create_index(
        "uq_nf_opportunity_sources_org_seed_id",
        "nf_opportunity_sources",
        ["organization_id", "seed_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_nf_opportunity_sources_org_seed_id",
        table_name="nf_opportunity_sources",
    )
    op.drop_index(
        "ix_nf_opportunity_sources_seed_id",
        table_name="nf_opportunity_sources",
    )
    op.drop_column("nf_opportunity_sources", "canonical_source_id")
    op.drop_column("nf_opportunity_sources", "seed_id")
