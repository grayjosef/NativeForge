"""Alembic 0070: optional owner on a pursuit task.

nf_pursuit_tasks had no assignment column. Cross-pursuit Mission Control
needs to say who owns open work without inventing a workforce system.
The owner is an existing organization membership, nullable, so every
current task remains valid.

Revision ID: 0070
Revises: 0069
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None

TABLE = "nf_pursuit_tasks"
FK = "fk_nf_pursuit_tasks_owner_membership"
INDEX = "ix_nf_pursuit_tasks_org_owner"


def upgrade() -> None:
    column = sa.Column("owner_membership_id", PGUUID(as_uuid=True), nullable=True)
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        with op.batch_alter_table(TABLE) as batch:
            batch.add_column(column)
            batch.create_foreign_key(
                FK,
                "nf_org_memberships",
                ["owner_membership_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_index(INDEX, ["organization_id", "owner_membership_id"])
        return
    op.add_column(TABLE, column)
    op.create_foreign_key(
        FK,
        TABLE,
        "nf_org_memberships",
        ["owner_membership_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(INDEX, TABLE, ["organization_id", "owner_membership_id"])


def downgrade() -> None:
    is_sqlite = op.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_index(INDEX)
            batch.drop_constraint(FK, type_="foreignkey")
            batch.drop_column("owner_membership_id")
        return
    op.drop_index(INDEX, table_name=TABLE)
    op.drop_constraint(FK, TABLE, type_="foreignkey")
    op.drop_column(TABLE, "owner_membership_id")
