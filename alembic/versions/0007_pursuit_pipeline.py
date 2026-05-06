"""Sprint 5: grant pursuits, tasks, calendar events.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    PursuitCalendarKind,
    PursuitTaskStatus,
    PursuitWorkflowStatus,
)

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pursuit_status_sql() -> str:
    return "status IN (" + ", ".join(
        f"'{s.value}'" for s in PursuitWorkflowStatus
    ) + ")"


def _task_status_sql() -> str:
    return "status IN (" + ", ".join(
        f"'{s.value}'" for s in PursuitTaskStatus
    ) + ")"


def _calendar_kind_sql() -> str:
    return "kind IN (" + ", ".join(
        f"'{k.value}'" for k in PursuitCalendarKind
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
        "nf_grant_pursuits",
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
            "spark_score_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_spark_scores.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=PursuitWorkflowStatus.active.value,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
            _pursuit_status_sql(),
            name="ck_nf_grant_pursuits_status",
        ),
        sa.UniqueConstraint(
            "grant_spark_id",
            name="uq_nf_grant_pursuits_grant_spark_id",
        ),
    )
    op.create_index(
        "ix_nf_grant_pursuits_org_id",
        "nf_grant_pursuits",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "nf_pursuit_tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grant_pursuit_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_pursuits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=PursuitTaskStatus.pending.value,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "spark_requirement_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_spark_requirements.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
            _task_status_sql(),
            name="ck_nf_pursuit_tasks_status",
        ),
    )
    op.create_index(
        "ix_nf_pursuit_tasks_grant_pursuit_id",
        "nf_pursuit_tasks",
        ["grant_pursuit_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_pursuit_tasks_org_id",
        "nf_pursuit_tasks",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "nf_pursuit_calendar_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grant_pursuit_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_pursuits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("occurs_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "pursuit_task_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_pursuit_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
            _calendar_kind_sql(),
            name="ck_nf_pursuit_calendar_events_kind",
        ),
    )
    op.create_index(
        "ix_nf_pursuit_calendar_pursuit_occurs",
        "nf_pursuit_calendar_events",
        ["grant_pursuit_id", "occurs_at"],
        unique=False,
    )
    op.create_index(
        "ix_nf_pursuit_calendar_org_occurs",
        "nf_pursuit_calendar_events",
        ["organization_id", "occurs_at"],
        unique=False,
    )

    for tbl in (
        "nf_grant_pursuits",
        "nf_pursuit_tasks",
        "nf_pursuit_calendar_events",
    ):
        if is_sqlite:
            _sqlite_demo_triggers(connection, tbl)
        elif is_pg:
            _postgres_trigger(connection, tbl)
            pol = (
                "nf_grant_pursuits_org_demo_scope"
                if tbl == "nf_grant_pursuits"
                else (
                    "nf_pursuit_tasks_org_demo_scope"
                    if tbl == "nf_pursuit_tasks"
                    else "nf_pursuit_calendar_events_org_demo_scope"
                )
            )
            _postgres_rls(connection, tbl, pol)


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    for tbl, pol in (
        ("nf_pursuit_calendar_events", "nf_pursuit_calendar_events_org_demo_scope"),
        ("nf_pursuit_tasks", "nf_pursuit_tasks_org_demo_scope"),
        ("nf_grant_pursuits", "nf_grant_pursuits_org_demo_scope"),
    ):
        if is_sqlite:
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_upd;")
            )
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_ins;")
            )
        elif is_pg:
            connection.execute(text(f"DROP POLICY IF EXISTS {pol} ON {tbl};"))
            connection.execute(text(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;"))
            connection.execute(text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;"))
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align ON {tbl};")
            )

    op.drop_table("nf_pursuit_calendar_events")
    op.drop_table("nf_pursuit_tasks")
    op.drop_table("nf_grant_pursuits")
