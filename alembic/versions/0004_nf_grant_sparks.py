"""Sprint 2: nf_grant_sparks (grant opportunity / discovery layer).

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import GrantAwardType, GrantPipelineStage, GrantSparkSource

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _source_check_sql() -> str:
    return "source IN (" + ", ".join(f"'{s.value}'" for s in GrantSparkSource) + ")"


def _award_type_check_sql() -> str:
    return "award_type IN (" + ", ".join(f"'{a.value}'" for a in GrantAwardType) + ")"


def _pipeline_check_sql() -> str:
    return "pipeline_stage IN (" + ", ".join(f"'{p.value}'" for p in GrantPipelineStage) + ")"


def _sqlite_triggers_nf_grant_sparks(connection: Connection) -> None:
    table = "nf_grant_sparks"
    connection.execute(
        text(
            f"""
CREATE TRIGGER trg_{table}_demo_align_ins
BEFORE INSERT ON {table}
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN NEW.is_demo != (
      SELECT CASE WHEN org_type = 'demo' THEN 1 ELSE 0 END
      FROM organizations WHERE id = NEW.organization_id
    )
    THEN RAISE(ABORT, 'nf is_demo does not match organizations.org_type')
  END;
END;
"""
        )
    )
    connection.execute(
        text(
            f"""
CREATE TRIGGER trg_{table}_demo_align_upd
BEFORE UPDATE ON {table}
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN NEW.is_demo != (
      SELECT CASE WHEN org_type = 'demo' THEN 1 ELSE 0 END
      FROM organizations WHERE id = NEW.organization_id
    )
    THEN RAISE(ABORT, 'nf is_demo does not match organizations.org_type')
  END;
END;
"""
        )
    )


def _postgres_trigger_nf_grant_sparks(connection: Connection) -> None:
    connection.execute(
        text("DROP TRIGGER IF EXISTS trg_nf_grant_sparks_demo_align ON nf_grant_sparks;")
    )
    connection.execute(
        text(
            """
CREATE TRIGGER trg_nf_grant_sparks_demo_align
BEFORE INSERT OR UPDATE ON nf_grant_sparks
FOR EACH ROW EXECUTE PROCEDURE nf_check_demo_alignment();
"""
        )
    )


def _postgres_rls_nf_grant_sparks(connection: Connection) -> None:
    connection.execute(text("ALTER TABLE nf_grant_sparks ENABLE ROW LEVEL SECURITY;"))
    connection.execute(text("ALTER TABLE nf_grant_sparks FORCE ROW LEVEL SECURITY;"))
    connection.execute(
        text(
            """
CREATE POLICY nf_grant_sparks_org_demo_scope ON nf_grant_sparks
FOR ALL
USING (
  organization_id = current_setting('app.current_org_id', true)::uuid
  AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
)
WITH CHECK (
  organization_id = current_setting('app.current_org_id', true)::uuid
  AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
);
"""
        )
    )


def upgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    op.create_table(
        "nf_grant_sparks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=False),
        sa.Column("agency", sa.String(512), nullable=False),
        sa.Column("sub_agency", sa.String(512), nullable=True),
        sa.Column("program_name", sa.String(512), nullable=True),
        sa.Column("opportunity_title", sa.String(512), nullable=False),
        sa.Column("opportunity_number", sa.String(128), nullable=True),
        sa.Column("cfda_assistance_listing", sa.String(64), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("funding_floor", sa.Numeric(18, 2), nullable=True),
        sa.Column("funding_ceiling", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_program_funding", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_awards", sa.Integer(), nullable=True),
        sa.Column("award_type", sa.String(32), nullable=False),
        sa.Column(
            "match_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("match_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "match_waiver_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "indirect_cost_allowable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("posted_date", sa.Date(), nullable=True),
        sa.Column("loi_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performance_period_start", sa.Date(), nullable=True),
        sa.Column("performance_period_end", sa.Date(), nullable=True),
        sa.Column("raw_nofo_text", sa.Text(), nullable=True),
        sa.Column("raw_nofo_url", sa.String(2048), nullable=True),
        sa.Column("eligibility_tags", sa.JSON(), nullable=True),
        sa.Column(
            "tribal_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "pipeline_stage",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{GrantPipelineStage.new.value}'"),
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(_source_check_sql(), name="ck_nf_grant_sparks_source"),
        sa.CheckConstraint(_award_type_check_sql(), name="ck_nf_grant_sparks_award_type"),
        sa.CheckConstraint(
            _pipeline_check_sql(),
            name="ck_nf_grant_sparks_pipeline_stage",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "source",
            "source_id",
            name="uq_nf_grant_sparks_org_source_source_id",
        ),
    )
    op.create_index(
        "ix_nf_grant_sparks_organization_id",
        "nf_grant_sparks",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_grant_sparks_org_deadline",
        "nf_grant_sparks",
        ["organization_id", "application_deadline"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_triggers_nf_grant_sparks(connection)
    elif is_pg:
        _postgres_trigger_nf_grant_sparks(connection)
        _postgres_rls_nf_grant_sparks(connection)


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_grant_sparks_demo_align_upd;")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_grant_sparks_demo_align_ins;")
        )
    elif is_pg:
        connection.execute(
            text("DROP POLICY IF EXISTS nf_grant_sparks_org_demo_scope ON nf_grant_sparks;")
        )
        connection.execute(
            text("ALTER TABLE nf_grant_sparks NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(text("ALTER TABLE nf_grant_sparks DISABLE ROW LEVEL SECURITY;"))
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_grant_sparks_demo_align ON nf_grant_sparks;")
        )

    op.drop_index("ix_nf_grant_sparks_org_deadline", table_name="nf_grant_sparks")
    op.drop_index("ix_nf_grant_sparks_organization_id", table_name="nf_grant_sparks")
    op.drop_table("nf_grant_sparks")
