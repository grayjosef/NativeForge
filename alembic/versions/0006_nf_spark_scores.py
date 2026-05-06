"""Sprint 4: deterministic Spark scores (nf_spark_scores).

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-08

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import RecommendationTier

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _recommendation_tier_sql() -> str:
    return "recommendation IN (" + ", ".join(
        f"'{t.value}'" for t in RecommendationTier
    ) + ")"


def _sqlite_demo_triggers(connection: Connection, table: str) -> None:
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


def _postgres_trigger(connection: Connection, table: str) -> None:
    connection.execute(
        text(f"DROP TRIGGER IF EXISTS trg_{table}_demo_align ON {table};")
    )
    connection.execute(
        text(
            f"""
CREATE TRIGGER trg_{table}_demo_align
BEFORE INSERT OR UPDATE ON {table}
FOR EACH ROW EXECUTE PROCEDURE nf_check_demo_alignment();
"""
        )
    )


def _postgres_rls(connection: Connection, table: str, policy: str) -> None:
    connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
    connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
    connection.execute(
        text(
            f"""
CREATE POLICY {policy} ON {table}
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
        "nf_spark_scores",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grant_spark_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_sparks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "tribal_profile_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_tribal_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "nofo_extraction_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_nofo_extraction_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scorer_engine", sa.String(64), nullable=False),
        sa.Column("dimension_scores", sa.JSON(), nullable=False),
        sa.Column("weights_used", sa.JSON(), nullable=False),
        sa.Column("composite", sa.Numeric(5, 2), nullable=False),
        sa.Column("recommendation", sa.String(32), nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.Column("rationale_detail", sa.JSON(), nullable=True),
        sa.Column(
            "disqualified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("disqualification_reason", sa.Text(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("override_actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            _recommendation_tier_sql(),
            name="ck_nf_spark_scores_recommendation",
        ),
    )
    op.create_index(
        "ix_nf_spark_scores_org_id",
        "nf_spark_scores",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_spark_scores_grant_spark_created",
        "nf_spark_scores",
        ["grant_spark_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_nf_spark_scores_tribal_profile_id",
        "nf_spark_scores",
        ["tribal_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_spark_scores_nofo_extraction_run_id",
        "nf_spark_scores",
        ["nofo_extraction_run_id"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection, "nf_spark_scores")
    elif is_pg:
        _postgres_trigger(connection, "nf_spark_scores")
        _postgres_rls(connection, "nf_spark_scores", "nf_spark_scores_org_demo_scope")


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_spark_scores_demo_align_upd;")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_spark_scores_demo_align_ins;")
        )
    elif is_pg:
        connection.execute(
            text("DROP POLICY IF EXISTS nf_spark_scores_org_demo_scope ON nf_spark_scores;")
        )
        connection.execute(
            text("ALTER TABLE nf_spark_scores NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(text("ALTER TABLE nf_spark_scores DISABLE ROW LEVEL SECURITY;"))
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_spark_scores_demo_align ON nf_spark_scores;")
        )

    op.drop_table("nf_spark_scores")
