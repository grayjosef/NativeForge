"""Sprint 14: discovery review assigned_to as plain text (operator handle).

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE nf_discovery_review_items "
                "ALTER COLUMN assigned_to TYPE VARCHAR(512) "
                "USING assigned_to::text"
            )
        )
    else:
        with op.batch_alter_table("nf_discovery_review_items") as batch_op:
            batch_op.alter_column(
                "assigned_to",
                existing_type=sa.Uuid(),
                type_=sa.String(length=512),
                existing_nullable=True,
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE nf_discovery_review_items "
                "ALTER COLUMN assigned_to TYPE UUID "
                "USING CASE WHEN assigned_to IS NULL OR trim(assigned_to) = '' "
                "THEN NULL ELSE assigned_to::uuid END"
            )
        )
    else:
        with op.batch_alter_table("nf_discovery_review_items") as batch_op:
            batch_op.alter_column(
                "assigned_to",
                existing_type=sa.String(length=512),
                type_=sa.Uuid(),
                existing_nullable=True,
            )
