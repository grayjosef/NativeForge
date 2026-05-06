"""Sprint 3: NOFO extraction runs, spark requirements, audit link.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import SparkRequirementKind

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _spark_req_kind_sql() -> str:
    return "requirement_type IN (" + ", ".join(
        f"'{k.value}'" for k in SparkRequirementKind
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
        "nf_nofo_extraction_runs",
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
            "review_artifact_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_review_artifacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("extractor_engine", sa.String(64), nullable=False),
        sa.Column("source_text_digest", sa.String(64), nullable=False),
        sa.Column("nofo_summary", sa.Text(), nullable=False),
        sa.Column("structured_requirements", sa.JSON(), nullable=False),
        sa.Column("checklist_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_nf_nofo_runs_spark_created",
        "nf_nofo_extraction_runs",
        ["grant_spark_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "nf_spark_requirements",
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
            "extraction_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_nofo_extraction_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("requirement_type", sa.String(32), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("page_limit", sa.Integer(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            _spark_req_kind_sql(),
            name="ck_nf_spark_requirements_kind",
        ),
    )
    op.create_index(
        "ix_nf_spark_requirements_extraction_run_id",
        "nf_spark_requirements",
        ["extraction_run_id"],
        unique=False,
    )

    extraction_run_col = sa.Column(
        "extraction_run_id",
        sa.Uuid(as_uuid=True),
        nullable=True,
    )
    if is_sqlite:
        with op.batch_alter_table("nf_audit_events") as batch_op:
            batch_op.add_column(extraction_run_col)
            batch_op.create_foreign_key(
                "fk_nf_audit_events_extraction_run_id",
                "nf_nofo_extraction_runs",
                ["extraction_run_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_nf_audit_events_extraction_run_id",
                ["extraction_run_id"],
            )
    else:
        op.add_column("nf_audit_events", extraction_run_col)
        op.create_foreign_key(
            "fk_nf_audit_events_extraction_run_id",
            "nf_audit_events",
            "nf_nofo_extraction_runs",
            ["extraction_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_nf_audit_events_extraction_run_id",
            "nf_audit_events",
            ["extraction_run_id"],
        )

    for tbl in ("nf_nofo_extraction_runs", "nf_spark_requirements"):
        if is_sqlite:
            _sqlite_demo_triggers(connection, tbl)
        elif is_pg:
            _postgres_trigger(connection, tbl)
            pol = (
                "nf_nofo_extraction_runs_org_demo_scope"
                if tbl == "nf_nofo_extraction_runs"
                else "nf_spark_requirements_org_demo_scope"
            )
            _postgres_rls(connection, tbl, pol)


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    for tbl in ("nf_spark_requirements", "nf_nofo_extraction_runs"):
        if is_sqlite:
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_upd;")
            )
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_ins;")
            )
        elif is_pg:
            pol = (
                "nf_spark_requirements_org_demo_scope"
                if tbl == "nf_spark_requirements"
                else "nf_nofo_extraction_runs_org_demo_scope"
            )
            connection.execute(text(f"DROP POLICY IF EXISTS {pol} ON {tbl};"))
            connection.execute(text(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;"))
            connection.execute(text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;"))
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align ON {tbl};")
            )

    if is_sqlite:
        with op.batch_alter_table("nf_audit_events") as batch_op:
            batch_op.drop_index("ix_nf_audit_events_extraction_run_id")
            batch_op.drop_constraint(
                "fk_nf_audit_events_extraction_run_id",
                type_="foreignkey",
            )
            batch_op.drop_column("extraction_run_id")
    else:
        op.drop_index(
            "ix_nf_audit_events_extraction_run_id",
            table_name="nf_audit_events",
        )
        op.drop_constraint(
            "fk_nf_audit_events_extraction_run_id",
            "nf_audit_events",
            type_="foreignkey",
        )
        op.drop_column("nf_audit_events", "extraction_run_id")

    op.drop_table("nf_spark_requirements")
    op.drop_table("nf_nofo_extraction_runs")
