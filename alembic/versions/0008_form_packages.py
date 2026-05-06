"""Sprint 6: review-gated form packages + SF-424 preview snapshot.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-10

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "nf_form_packages",
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
            "review_artifact_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_review_artifacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_demo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("package_engine", sa.String(64), nullable=False),
        sa.Column("sf424_preview", sa.JSON(), nullable=False),
        sa.Column("input_digest", sa.String(64), nullable=False),
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
        sa.UniqueConstraint(
            "grant_pursuit_id",
            name="uq_nf_form_packages_grant_pursuit_id",
        ),
    )
    op.create_index(
        "ix_nf_form_packages_org_id",
        "nf_form_packages",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_nf_form_packages_review_artifact_id",
        "nf_form_packages",
        ["review_artifact_id"],
        unique=False,
    )

    tbl = "nf_form_packages"
    if is_sqlite:
        _sqlite_demo_triggers(connection, tbl)
    elif is_pg:
        _postgres_trigger(connection, tbl)
        _postgres_rls(connection, tbl, "nf_form_packages_org_demo_scope")


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    tbl = "nf_form_packages"
    if is_sqlite:
        connection.execute(text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_upd;"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align_ins;"))
    elif is_pg:
        connection.execute(
            text(f"DROP POLICY IF EXISTS nf_form_packages_org_demo_scope ON {tbl};")
        )
        connection.execute(text(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;"))
        connection.execute(text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;"))
        connection.execute(text(f"DROP TRIGGER IF EXISTS trg_{tbl}_demo_align ON {tbl};"))

    op.drop_table("nf_form_packages")
