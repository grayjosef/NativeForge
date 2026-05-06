"""Sprint 12: discovery intake runs + intake candidates (audit trail).

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    DiscoveryIntakeMode,
    DiscoveryIntakeRunStatus,
    SparkFreshnessStatus,
)

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _run_status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in DiscoveryIntakeRunStatus)
    return f"run_status IN ({vals})"


def _intake_mode_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in DiscoveryIntakeMode)
    return f"intake_mode IN ({vals})"


def _candidate_status_sql() -> str:
    vals = ", ".join(f"'{c.value}'" for c in DiscoveryCandidateStatus)
    return f"candidate_status IN ({vals})"


def _candidate_freshness_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in SparkFreshnessStatus)
    return f"(freshness_status IS NULL OR freshness_status IN ({vals}))"


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
        "nf_discovery_intake_runs",
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
        sa.Column(
            "source_registry_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_opportunity_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "run_schema_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "run_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{DiscoveryIntakeRunStatus.created.value}'"),
        ),
        sa.Column("intake_mode", sa.String(32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "candidate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "accepted_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "duplicate_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "rejected_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("run_summary_json", sa.JSON(), nullable=True),
        sa.Column("error_summary_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(_run_status_sql(), name="ck_nf_discovery_intake_runs_run_status"),
        sa.CheckConstraint(_intake_mode_sql(), name="ck_nf_discovery_intake_runs_intake_mode"),
    )
    op.create_index(
        "ix_nf_discovery_intake_runs_org_source_started",
        "nf_discovery_intake_runs",
        ["organization_id", "source_registry_id", "started_at"],
        unique=False,
    )

    op.create_table(
        "nf_discovery_intake_candidates",
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
        sa.Column(
            "intake_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_discovery_intake_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_registry_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("candidate_status", sa.String(32), nullable=False),
        sa.Column("raw_candidate_json", sa.JSON(), nullable=False),
        sa.Column("normalized_candidate_json", sa.JSON(), nullable=True),
        sa.Column("normalization_errors_json", sa.JSON(), nullable=True),
        sa.Column("duplicate_key", sa.String(128), nullable=True),
        sa.Column(
            "duplicate_of_spark_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_spark_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("native_relevance_score", sa.Integer(), nullable=True),
        sa.Column("native_relevance_reasons_json", sa.JSON(), nullable=True),
        sa.Column("freshness_status", sa.String(32), nullable=True),
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
        sa.CheckConstraint(
            _candidate_status_sql(),
            name="ck_nf_discovery_intake_candidates_status",
        ),
        sa.CheckConstraint(
            _candidate_freshness_sql(),
            name="ck_nf_discovery_intake_candidates_freshness",
        ),
    )
    op.create_index(
        "ix_nf_discovery_intake_candidates_run_id",
        "nf_discovery_intake_candidates",
        ["intake_run_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_discovery_intake_candidates_org_id",
        "nf_discovery_intake_candidates",
        ["organization_id"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection, "nf_discovery_intake_runs")
        _sqlite_demo_triggers(connection, "nf_discovery_intake_candidates")
    elif is_pg:
        _postgres_trigger(connection, "nf_discovery_intake_runs")
        _postgres_rls(
            connection,
            "nf_discovery_intake_runs",
            "nf_discovery_intake_runs_org_demo_scope",
        )
        _postgres_trigger(connection, "nf_discovery_intake_candidates")
        _postgres_rls(
            connection,
            "nf_discovery_intake_candidates",
            "nf_discovery_intake_candidates_org_demo_scope",
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_candidates_demo_align_upd;"
            )
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_candidates_demo_align_ins;"
            )
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_runs_demo_align_upd;"
            )
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_runs_demo_align_ins;"
            )
        )
    elif is_pg:
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_discovery_intake_candidates_org_demo_scope "
                "ON nf_discovery_intake_candidates;"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE nf_discovery_intake_candidates NO FORCE ROW LEVEL SECURITY;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_discovery_intake_candidates DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_candidates_demo_align "
                "ON nf_discovery_intake_candidates;"
            )
        )
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_discovery_intake_runs_org_demo_scope "
                "ON nf_discovery_intake_runs;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_discovery_intake_runs NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text("ALTER TABLE nf_discovery_intake_runs DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_intake_runs_demo_align "
                "ON nf_discovery_intake_runs;"
            )
        )

    op.drop_table("nf_discovery_intake_candidates")
    op.drop_table("nf_discovery_intake_runs")
