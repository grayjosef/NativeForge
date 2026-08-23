"""Alembic 0027: RLS policies for membership + authority tables.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-23

Gate 62. Approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61.
Approved environment: staging/dev proof first. No production customer claim.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


from sqlalchemy import text  # noqa: E402

# Org-scoped tables added by 0024/0026. nf_identities is deliberately NOT
# org-scoped: an identity exists independently of any organization, and scoping
# it would make cross-org membership lookup impossible.
ORG_SCOPED_TABLES = ("nf_org_memberships", "nf_authority_proof_records")


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as migration 0002 behaves.
        return
    for table in ORG_SCOPED_TABLES:
        conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
        conn.execute(
            text(
                f"""
CREATE POLICY {table}_org_demo_scope ON {table}
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


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table in ORG_SCOPED_TABLES:
        conn.execute(text(f"DROP POLICY IF EXISTS {table}_org_demo_scope ON {table};"))
        conn.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;"))
        conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"))
