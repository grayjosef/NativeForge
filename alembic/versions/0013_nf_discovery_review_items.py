"""Sprint 13: discovery review queue + QC hooks.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import (
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
)

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _review_item_type_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in DiscoveryReviewItemType)
    return f"review_item_type IN ({vals})"


def _review_queue_status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in DiscoveryReviewQueueStatus)
    return f"review_status IN ({vals})"


def _recommended_action_sql() -> str:
    vals = ", ".join(f"'{a.value}'" for a in DiscoveryRecommendedAction)
    return f"(recommended_action IS NULL OR recommended_action IN ({vals}))"


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
        "nf_discovery_review_items",
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
            sa.ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
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
        sa.Column("review_item_type", sa.String(64), nullable=False),
        sa.Column(
            "review_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{DiscoveryReviewQueueStatus.open.value}'"),
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("reason_codes_json", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column("duplicate_risk_score", sa.Integer(), nullable=True),
        sa.Column("native_relevance_score", sa.Integer(), nullable=True),
        sa.Column("recommended_action", sa.String(32), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            _review_item_type_sql(),
            name="ck_nf_discovery_review_items_item_type",
        ),
        sa.CheckConstraint(
            _review_queue_status_sql(),
            name="ck_nf_discovery_review_items_review_status",
        ),
        sa.CheckConstraint(
            _recommended_action_sql(),
            name="ck_nf_discovery_review_items_recommended_action",
        ),
    )
    op.create_index(
        "ix_nf_discovery_review_items_org_status",
        "nf_discovery_review_items",
        ["organization_id", "review_status"],
        unique=False,
    )
    op.create_index(
        "ix_nf_discovery_review_items_org_priority",
        "nf_discovery_review_items",
        ["organization_id", "priority"],
        unique=False,
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection, "nf_discovery_review_items")
    elif is_pg:
        _postgres_trigger(connection, "nf_discovery_review_items")
        _postgres_rls(
            connection,
            "nf_discovery_review_items",
            "nf_discovery_review_items_org_demo_scope",
        )


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_review_items_demo_align_upd;"
            )
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_review_items_demo_align_ins;"
            )
        )
    elif is_pg:
        connection.execute(
            text(
                "DROP POLICY IF EXISTS nf_discovery_review_items_org_demo_scope "
                "ON nf_discovery_review_items;"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE nf_discovery_review_items NO FORCE ROW LEVEL SECURITY;"
            )
        )
        connection.execute(
            text("ALTER TABLE nf_discovery_review_items DISABLE ROW LEVEL SECURITY;")
        )
        connection.execute(
            text(
                "DROP TRIGGER IF EXISTS trg_nf_discovery_review_items_demo_align "
                "ON nf_discovery_review_items;"
            )
        )

    op.drop_table("nf_discovery_review_items")
