"""Sprint 18: operator action ledger + resolution workflow.

Revision ID: 0018
Revises: 0015
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    OperatorActionCreatedFrom,
    OperatorActionResolutionCode,
    OperatorActionStatus,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
)

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in OperatorActionStatus)
    return f"status IN ({vals})"


def _item_type_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OperatorDecisionItemType)
    return f"item_type IN ({vals})"


def _action_sql() -> str:
    vals = ", ".join(f"'{a.value}'" for a in OperatorDecisionAction)
    return f'"action" IN ({vals})'


def _severity_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in OperatorDecisionSeverity)
    return f"severity IN ({vals})"


def _resolution_code_sql() -> str:
    vals = ", ".join(f"'{r.value}'" for r in OperatorActionResolutionCode)
    return "(resolution_code IS NULL OR resolution_code IN (" + vals + "))"


def _created_from_sql() -> str:
    vals = ", ".join(f"'{c.value}'" for c in OperatorActionCreatedFrom)
    return f"created_from IN ({vals})"


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
        "nf_operator_actions",
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
        sa.Column("decision_id", sa.String(length=256), nullable=False),
        sa.Column("decision_schema_version", sa.String(length=80), nullable=True),
        sa.Column("source_decision_item_json", sa.JSON(), nullable=True),
        sa.Column("action_title", sa.String(length=512), nullable=False),
        sa.Column("action_summary", sa.Text(), nullable=True),
        sa.Column("operator_action", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text(f"'{OperatorDecisionSeverity.medium.value}'"),
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text(f"'{OperatorActionStatus.open.value}'"),
        ),
        sa.Column("assigned_to", sa.String(length=512), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deferred_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("operator_notes", sa.Text(), nullable=True),
        sa.Column("resolution_code", sa.String(length=80), nullable=True),
        sa.Column(
            "source_registry_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "review_item_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_discovery_review_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "intake_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_discovery_intake_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "intake_candidate_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_discovery_intake_candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "grant_spark_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_check_run_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_source_check_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("coverage_gap_id", sa.String(length=256), nullable=True),
        sa.Column(
            "created_from",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text(
                f"'{OperatorActionCreatedFrom.decision_pack.value}'"
            ),
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
        sa.CheckConstraint(_status_sql(), name="ck_nf_operator_actions_status"),
        sa.CheckConstraint(_item_type_sql(), name="ck_nf_operator_actions_item_type"),
        sa.CheckConstraint(_action_sql(), name="ck_nf_operator_actions_action"),
        sa.CheckConstraint(_severity_sql(), name="ck_nf_operator_actions_severity"),
        sa.CheckConstraint(
            _resolution_code_sql(),
            name="ck_nf_operator_actions_resolution_code",
        ),
        sa.CheckConstraint(
            _created_from_sql(),
            name="ck_nf_operator_actions_created_from",
        ),
    )
    op.create_index(
        "ix_nf_operator_actions_org_demo_status",
        "nf_operator_actions",
        ["organization_id", "is_demo", "status"],
        unique=False,
    )
    op.create_index(
        "ix_nf_operator_actions_org_demo_severity",
        "nf_operator_actions",
        ["organization_id", "is_demo", "severity"],
        unique=False,
    )
    op.create_index(
        "ix_nf_operator_actions_org_demo_assigned",
        "nf_operator_actions",
        ["organization_id", "is_demo", "assigned_to"],
        unique=False,
    )
    op.create_index(
        "ix_nf_operator_actions_org_demo_source",
        "nf_operator_actions",
        ["organization_id", "is_demo", "source_registry_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_operator_actions_org_demo_decision",
        "nf_operator_actions",
        ["organization_id", "is_demo", "decision_id"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection, "nf_operator_actions")
    elif is_pg:
        _postgres_trigger(connection, "nf_operator_actions")
        _postgres_rls(
            connection,
            "nf_operator_actions",
            "nf_operator_actions_org_demo_scope",
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_operator_actions_demo_align_upd;")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_operator_actions_demo_align_ins;")
        )
    elif is_pg:
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_operator_actions_org_demo_scope "
                "ON nf_operator_actions;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_operator_actions NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text("ALTER TABLE nf_operator_actions DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_operator_actions_demo_align "
                "ON nf_operator_actions;"
            )
        )

    for ix in (
        "ix_nf_operator_actions_org_demo_decision",
        "ix_nf_operator_actions_org_demo_source",
        "ix_nf_operator_actions_org_demo_assigned",
        "ix_nf_operator_actions_org_demo_severity",
        "ix_nf_operator_actions_org_demo_status",
    ):
        op.drop_index(ix, table_name="nf_operator_actions")
    op.drop_table("nf_operator_actions")
