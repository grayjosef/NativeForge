"""Sprint 1: nf_tribal_profiles + tribal_profile_id on nf_audit_events.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-06

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

from nativeforge.domain.enums import SamRegistrationStatus, TribalEntityType

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _entity_check_sql() -> str:
    return "entity_type IN (" + ", ".join(f"'{e.value}'" for e in TribalEntityType) + ")"


def _sam_check_sql() -> str:
    return "sam_registration_status IN (" + ", ".join(
        f"'{s.value}'" for s in SamRegistrationStatus
    ) + ")"


def _sqlite_triggers_nf_tribal(connection: Connection) -> None:
    table = "nf_tribal_profiles"
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


def _postgres_trigger_nf_tribal(connection: Connection) -> None:
    connection.execute(
        text("DROP TRIGGER IF EXISTS trg_nf_tribal_profiles_demo_align ON nf_tribal_profiles;")
    )
    connection.execute(
        text(
            """
CREATE TRIGGER trg_nf_tribal_profiles_demo_align
BEFORE INSERT OR UPDATE ON nf_tribal_profiles
FOR EACH ROW EXECUTE PROCEDURE nf_check_demo_alignment();
"""
        )
    )


def _postgres_rls_nf_tribal(connection: Connection) -> None:
    connection.execute(text("ALTER TABLE nf_tribal_profiles ENABLE ROW LEVEL SECURITY;"))
    connection.execute(text("ALTER TABLE nf_tribal_profiles FORCE ROW LEVEL SECURITY;"))
    connection.execute(
        text(
            """
CREATE POLICY nf_tribal_profiles_org_demo_scope ON nf_tribal_profiles
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
        "nf_tribal_profiles",
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
        sa.Column("legal_name", sa.String(512), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("uei", sa.String(32), nullable=True),
        sa.Column("ein", sa.String(32), nullable=True),
        sa.Column(
            "sam_registration_status",
            sa.String(32),
            nullable=False,
            server_default=sa.text(f"'{SamRegistrationStatus.unknown.value}'"),
        ),
        sa.Column("sam_expiration_date", sa.Date(), nullable=True),
        sa.Column("physical_address", sa.JSON(), nullable=True),
        sa.Column("mailing_address", sa.JSON(), nullable=True),
        sa.Column("service_area_description", sa.String(4096), nullable=True),
        sa.Column("authorized_representative", sa.JSON(), nullable=True),
        sa.Column("grants_manager", sa.JSON(), nullable=True),
        sa.Column("finance_contact", sa.JSON(), nullable=True),
        sa.Column("indirect_cost_rate", sa.JSON(), nullable=True),
        sa.Column("certifications", sa.JSON(), nullable=True),
        sa.Column("standard_narratives", sa.JSON(), nullable=True),
        sa.Column("attachment_index", sa.JSON(), nullable=True),
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
        sa.CheckConstraint(_entity_check_sql(), name="ck_nf_tribal_profiles_entity_type"),
        sa.CheckConstraint(_sam_check_sql(), name="ck_nf_tribal_profiles_sam_status"),
        sa.UniqueConstraint("organization_id", name="uq_nf_tribal_profiles_organization_id"),
    )

    tribal_profile_col = sa.Column(
        "tribal_profile_id",
        sa.Uuid(as_uuid=True),
        nullable=True,
    )
    if is_sqlite:
        with op.batch_alter_table("nf_audit_events") as batch_op:
            batch_op.add_column(tribal_profile_col)
            batch_op.create_foreign_key(
                "fk_nf_audit_events_tribal_profile_id",
                "nf_tribal_profiles",
                ["tribal_profile_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index(
                "ix_nf_audit_events_tribal_profile_id",
                ["tribal_profile_id"],
            )
    else:
        op.add_column("nf_audit_events", tribal_profile_col)
        op.create_foreign_key(
            "fk_nf_audit_events_tribal_profile_id",
            "nf_audit_events",
            "nf_tribal_profiles",
            ["tribal_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_nf_audit_events_tribal_profile_id",
            "nf_audit_events",
            ["tribal_profile_id"],
        )

    if is_sqlite:
        _sqlite_triggers_nf_tribal(connection)
    elif is_pg:
        _postgres_trigger_nf_tribal(connection)
        _postgres_rls_nf_tribal(connection)


def downgrade() -> None:
    connection = op.get_bind()
    is_sqlite = connection.dialect.name == "sqlite"
    is_pg = connection.dialect.name == "postgresql"

    if is_sqlite:
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_tribal_profiles_demo_align_upd;")
        )
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_tribal_profiles_demo_align_ins;")
        )
    elif is_pg:
        connection.execute(
            text("DROP POLICY IF EXISTS nf_tribal_profiles_org_demo_scope ON nf_tribal_profiles;")
        )
        connection.execute(
            text("ALTER TABLE nf_tribal_profiles NO FORCE ROW LEVEL SECURITY;")
        )
        connection.execute(text("ALTER TABLE nf_tribal_profiles DISABLE ROW LEVEL SECURITY;"))
        connection.execute(
            text("DROP TRIGGER IF EXISTS trg_nf_tribal_profiles_demo_align ON nf_tribal_profiles;")
        )

    if is_sqlite:
        with op.batch_alter_table("nf_audit_events") as batch_op:
            batch_op.drop_index("ix_nf_audit_events_tribal_profile_id")
            batch_op.drop_constraint(
                "fk_nf_audit_events_tribal_profile_id",
                type_="foreignkey",
            )
            batch_op.drop_column("tribal_profile_id")
    else:
        op.drop_index("ix_nf_audit_events_tribal_profile_id", table_name="nf_audit_events")
        op.drop_constraint(
            "fk_nf_audit_events_tribal_profile_id",
            "nf_audit_events",
            type_="foreignkey",
        )
        op.drop_column("nf_audit_events", "tribal_profile_id")

    op.drop_table("nf_tribal_profiles")
