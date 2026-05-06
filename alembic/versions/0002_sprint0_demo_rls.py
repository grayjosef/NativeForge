"""Sprint 0: organizations, nf_review_artifacts, nf_audit_events, triggers, PG RLS.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _sqlite_demo_triggers(connection: Connection) -> None:
    for table in ("nf_review_artifacts", "nf_audit_events"):
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


def _postgres_demo_trigger_function(connection: Connection) -> None:
    connection.execute(
        text(
            """
CREATE OR REPLACE FUNCTION nf_check_demo_alignment()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.is_demo IS DISTINCT FROM (
    SELECT (org_type = 'demo') FROM organizations WHERE id = NEW.organization_id
  ) THEN
    RAISE EXCEPTION 'nf is_demo/org_type mismatch for %', NEW.organization_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )
    for table in ("nf_review_artifacts", "nf_audit_events"):
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


def _postgres_rls(connection: Connection) -> None:
    for table in ("nf_review_artifacts", "nf_audit_events"):
        connection.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
        connection.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
        connection.execute(
            text(
                f"""
CREATE POLICY {table}_org_demo_scope ON {table}
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
        "organizations",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_type", sa.String(16), nullable=False),
        sa.CheckConstraint(
            "org_type IN ('real', 'demo')",
            name="ck_organizations_org_type",
        ),
    )

    op.create_table(
        "nf_review_artifacts",
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
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False),
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
            "review_status IN ("
            "'draft','pending_review','approved','rejected','finalized')",
            name="ck_nf_review_artifacts_status",
        ),
    )
    op.create_index(
        "ix_nf_review_artifacts_organization_id",
        "nf_review_artifacts",
        ["organization_id"],
    )

    op.create_table(
        "nf_audit_events",
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
            "review_artifact_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_review_artifacts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_nf_audit_events_organization_id",
        "nf_audit_events",
        ["organization_id"],
    )
    op.create_index(
        "ix_nf_audit_events_review_artifact_id",
        "nf_audit_events",
        ["review_artifact_id"],
    )

    if is_sqlite:
        _sqlite_demo_triggers(connection)
    elif is_pg:
        _postgres_demo_trigger_function(connection)
        _postgres_rls(connection)


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        for table in ("nf_review_artifacts", "nf_audit_events"):
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{table}_demo_align_upd;")
            )
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{table}_demo_align_ins;")
            )
    elif is_pg:
        for table in ("nf_review_artifacts", "nf_audit_events"):
            connection.execute(
                text(f"DROP POLICY IF EXISTS {table}_org_demo_scope ON {table};")
            )
            connection.execute(
                text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
            )
            connection.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"))
        for table in ("nf_review_artifacts", "nf_audit_events"):
            connection.execute(
                text(f"DROP TRIGGER IF EXISTS trg_{table}_demo_align ON {table};")
            )
        connection.execute(text("DROP FUNCTION IF EXISTS nf_check_demo_alignment();"))

    op.drop_table("nf_audit_events")
    op.drop_table("nf_review_artifacts")
    op.drop_table("organizations")
