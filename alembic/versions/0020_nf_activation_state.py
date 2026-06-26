"""M7/M8: nf_activation_state + nf_auto_publish_config (durable workspace flags).

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nf_activation_state",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "live_publish_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "live_attribution_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "auto_publish_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "kill_switch_engaged",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("current_auto_publish_config_version", sa.Integer(), nullable=True),
        sa.Column(
            "state_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("updated_by_actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("updated_by_actor_role", sa.String(length=32), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", name="uq_nf_activation_state_org"),
    )
    op.create_index(
        "ix_nf_activation_state_organization_id",
        "nf_activation_state",
        ["organization_id"],
    )

    op.create_table(
        "nf_auto_publish_config",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config_payload", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_by_actor_role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id",
            "version",
            name="uq_nf_auto_publish_config_org_version",
        ),
    )
    op.create_index(
        "ix_nf_auto_publish_config_organization_id",
        "nf_auto_publish_config",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_nf_auto_publish_config_organization_id", "nf_auto_publish_config")
    op.drop_table("nf_auto_publish_config")
    op.drop_index("ix_nf_activation_state_organization_id", "nf_activation_state")
    op.drop_table("nf_activation_state")
