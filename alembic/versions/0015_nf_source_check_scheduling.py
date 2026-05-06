"""Sprint 15: source check scheduling + freshness monitoring + check runs table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    SourceCheckMode,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
)

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _last_check_status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in SourceLastCheckStatus)
    return f"(last_check_status IS NULL OR last_check_status IN ({vals}))"


def _source_health_status_sql() -> str:
    vals = ", ".join(f"'{h.value}'" for h in SourceHealthStatus)
    return f"(source_health_status IS NULL OR source_health_status IN ({vals}))"


def _check_run_status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in SourceCheckRunStatus)
    return f"check_status IN ({vals})"


def _check_mode_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in SourceCheckMode)
    return f"check_mode IN ({vals})"


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

    cols = [
        sa.Column("check_interval_days", sa.Integer(), nullable=True),
        sa.Column("next_check_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_status", sa.String(length=32), nullable=True),
        sa.Column("last_check_run_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("last_check_summary_json", sa.JSON(), nullable=True),
        sa.Column(
            "consecutive_failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "consecutive_empty_check_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("source_health_status", sa.String(length=32), nullable=True),
        sa.Column("freshness_checked_at", sa.DateTime(timezone=True), nullable=True),
    ]

    if is_sqlite:
        with op.batch_alter_table("nf_opportunity_sources") as batch_op:
            for c in cols:
                batch_op.add_column(c)
            batch_op.create_check_constraint(
                "ck_nf_opportunity_sources_last_check_status",
                _last_check_status_sql(),
            )
            batch_op.create_check_constraint(
                "ck_nf_opportunity_sources_source_health_status",
                _source_health_status_sql(),
            )
    else:
        for c in cols:
            op.add_column("nf_opportunity_sources", c)
        op.create_check_constraint(
            "ck_nf_opportunity_sources_last_check_status",
            "nf_opportunity_sources",
            _last_check_status_sql(),
        )
        op.create_check_constraint(
            "ck_nf_opportunity_sources_source_health_status",
            "nf_opportunity_sources",
            _source_health_status_sql(),
        )

    op.create_table(
        "nf_source_check_runs",
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
        sa.Column("check_mode", sa.String(length=32), nullable=False),
        sa.Column(
            "check_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text(f"'{SourceCheckRunStatus.running.value}'"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "checked_for_period_start",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "checked_for_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "opportunities_seen_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "new_candidates_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "accepted_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "duplicate_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "rejected_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "review_items_created_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("operator_notes", sa.Text(), nullable=True),
        sa.Column("result_summary_json", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(_check_run_status_sql(), name="ck_nf_source_check_runs_status"),
        sa.CheckConstraint(_check_mode_sql(), name="ck_nf_source_check_runs_mode"),
    )
    op.create_index(
        "ix_nf_source_check_runs_org_source_started",
        "nf_source_check_runs",
        ["organization_id", "source_registry_id", "started_at"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection, "nf_source_check_runs")
    elif is_pg:
        _postgres_trigger(connection, "nf_source_check_runs")
        _postgres_rls(
            connection,
            "nf_source_check_runs",
            "nf_source_check_runs_org_demo_scope",
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_source_check_runs_demo_align_upd;"
            )
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_source_check_runs_demo_align_ins;"
            )
        )
    elif is_pg:
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_source_check_runs_org_demo_scope "
                "ON nf_source_check_runs;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_source_check_runs NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text("ALTER TABLE nf_source_check_runs DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_source_check_runs_demo_align "
                "ON nf_source_check_runs;"
            )
        )

    op.drop_index("ix_nf_source_check_runs_org_source_started", table_name="nf_source_check_runs")
    op.drop_table("nf_source_check_runs")

    constraint_names = (
        "ck_nf_opportunity_sources_source_health_status",
        "ck_nf_opportunity_sources_last_check_status",
    )
    col_names = (
        "freshness_checked_at",
        "source_health_status",
        "consecutive_empty_check_count",
        "consecutive_failure_count",
        "last_check_summary_json",
        "last_check_run_id",
        "last_check_status",
        "next_check_due_at",
        "check_interval_days",
    )

    if is_sqlite:
        with op.batch_alter_table("nf_opportunity_sources") as batch_op:
            for cn in constraint_names:
                batch_op.drop_constraint(cn, type_="check")
            for col in col_names:
                batch_op.drop_column(col)
    else:
        for cn in constraint_names:
            op.drop_constraint(cn, "nf_opportunity_sources", type_="check")
        for col in col_names:
            op.drop_column("nf_opportunity_sources", col)
