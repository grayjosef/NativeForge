"""Alembic 0069: durable funder interactions for a tenant pursuit.

NativeForge already stores who a notice named (0068) and the work of a
pursuit (0007). It had nowhere to store what this organization *did* with
those people: a question submitted, a clarification received, a webinar
attended. That history is institutional memory, not a field on the
opportunity, and it must not live in disposable UI JSON.

Rows are tenant-scoped. A contact id is optional and set-null on delete so
an extracted contact being superseded does not erase the conversation. The
funder name is copied at write time so later pursuits with the same agency
can find prior interactions without a fuzzy merge of people.

Revision ID: 0069
Revises: 0068
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None

TABLE = "nf_funder_interactions"

INTERACTION_TYPES = (
    "question_submitted",
    "email",
    "phone_call",
    "technical_assistance",
    "office_hours",
    "webinar",
    "applicant_conference",
    "pre_application_meeting",
    "clarification_received",
    "amendment_communication",
    "other",
)

INTERACTION_STATUSES = ("open", "awaiting_reply", "answered", "closed")


def _check(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{v}'" for v in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("grant_spark_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("grant_pursuit_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("contact_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("funder_agency", sa.String(length=512), nullable=False),
        sa.Column("funder_agency_norm", sa.String(length=512), nullable=False),
        sa.Column("program_name", sa.String(length=512), nullable=True),
        sa.Column("interaction_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.String(length=512), nullable=True),
        sa.Column("owner_label", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_spark_id"], ["nf_grant_sparks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["grant_pursuit_id"], ["nf_grant_pursuits.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["nf_opportunity_contacts.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            _check("interaction_type", INTERACTION_TYPES),
            name="ck_nf_funder_interactions_type",
        ),
        sa.CheckConstraint(
            _check("status", INTERACTION_STATUSES),
            name="ck_nf_funder_interactions_status",
        ),
        sa.CheckConstraint(
            "length(trim(funder_agency)) > 0",
            name="ck_nf_funder_interactions_agency_present",
        ),
    )
    op.create_index(
        "ix_nf_funder_interactions_org_agency",
        TABLE,
        ["organization_id", "funder_agency_norm"],
    )
    op.create_index(
        "ix_nf_funder_interactions_org_occurred",
        TABLE,
        ["organization_id", "occurred_at"],
    )

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    predicate = (
        "(organization_id = current_setting('app.current_org_id', true)::uuid"
        " AND is_demo = current_setting('app.current_org_is_demo', true)::boolean)"
    )
    policy = f"{TABLE}_org_isolation"
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {policy} ON {TABLE}")
    op.execute(
        f"CREATE POLICY {policy} ON {TABLE} FOR ALL "
        f"USING {predicate} WITH CHECK {predicate}"
    )


def downgrade() -> None:
    op.drop_index("ix_nf_funder_interactions_org_occurred", table_name=TABLE)
    op.drop_index("ix_nf_funder_interactions_org_agency", table_name=TABLE)
    op.drop_table(TABLE)
