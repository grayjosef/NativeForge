"""Alembic 0071: commercial intent and provisioning requests (identity-scoped).

Tracks demo-user activation toward a real organization workspace without
conflating commercial intent with paid entitlement or Tribal authority.

Preserves 0056 through 0070.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

TABLE = "nf_commercial_provisioning_requests"

LIFECYCLE = (
    "commercial_intent",
    "entitlement_pending",
    "provisioning",
    "organization_setup",
    "active",
    "blocked_ambiguous_org",
    "cancelled",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("request_id", sa.String(length=64), primary_key=True),
        sa.Column("identity_id", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=40), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("requested_org_display_name", sa.Text(), nullable=True),
        sa.Column("requested_org_hint", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Text(), nullable=True),
        sa.Column("operator_actor", sa.Text(), nullable=True),
        sa.Column("blocked_reasons_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
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
            _in_list("lifecycle_status", LIFECYCLE),
            name=f"ck_{TABLE}_lifecycle_status",
        ),
    )
    op.create_index(
        f"ix_{TABLE}_identity_updated",
        TABLE,
        ["identity_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_identity_updated", table_name=TABLE)
    op.drop_table(TABLE)
