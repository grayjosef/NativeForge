"""Alembic 0025: organizations enrichment (name, seat cap, timestamps).

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-23

Gate 62. Approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61.
Approved environment: staging/dev proof first. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None



def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("display_name", sa.String(length=255), nullable=True)
    )
    # Gate 51 default seat cap. Sixth seat is blocked unless explicitly overridden.
    op.add_column(
        "organizations",
        sa.Column(
            "seat_cap", sa.Integer(), nullable=False, server_default=sa.text("5")
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # The seat-cap CHECK is PostgreSQL-only, and the reason is worth recording
    # because two obvious approaches both fail on SQLite:
    #
    #   1. op.create_check_constraint -> NotImplementedError, SQLite cannot
    #      ALTER a constraint into an existing table.
    #   2. op.batch_alter_table (copy-and-move) -> breaks, because migration
    #      0002 created triggers (trg_nf_review_artifacts_demo_align_ins and
    #      friends) that reference `organizations`; renaming the table out from
    #      under them fails with "no such table: main.organizations".
    #
    # So the constraint is added only on PostgreSQL, which is the approved
    # production backend. On SQLite the seat cap is enforced in application code
    # (org_tenant_seat_model_service, Gate 51). This asymmetry is deliberate and
    # documented rather than hidden — see docs/operations/390.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_organizations_seat_cap_positive", "organizations", "seat_cap >= 1"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint(
            "ck_organizations_seat_cap_positive", "organizations", type_="check"
        )
    op.drop_column("organizations", "created_at")
    op.drop_column("organizations", "seat_cap")
    op.drop_column("organizations", "display_name")
