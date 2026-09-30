"""Harden nf_grant_sparks RLS against empty app.current_org_is_demo GUC.

Revision ID: 0072
Revises: 0071

After ``connection.commit()`` (e.g. canonical batch persist), local GUCs revert
to ``''``. Policies that cast ``current_setting(..., true)::boolean`` abort the
transaction with ``invalid input syntax for type boolean: ""`` during grant-spark
duplicate lookup under FORCE RLS.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0072"
down_revision: str | Sequence[str] | None = "0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ORG_ID = "app.current_org_id"
_IS_DEMO = "app.current_org_is_demo"

_POLICY = "nf_grant_sparks_org_demo_scope"
_TABLE = "nf_grant_sparks"

_USING = f"""
organization_id = NULLIF(current_setting('{_ORG_ID}', true), '')::uuid
AND is_demo = NULLIF(current_setting('{_IS_DEMO}', true), '')::boolean
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"DROP POLICY IF EXISTS {_POLICY} ON {_TABLE}"))
    op.execute(
        sa.text(
            f"""
CREATE POLICY {_POLICY} ON {_TABLE}
FOR ALL
USING ({_USING})
WITH CHECK ({_USING});
"""
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"DROP POLICY IF EXISTS {_POLICY} ON {_TABLE}"))
    op.execute(
        sa.text(
            f"""
CREATE POLICY {_POLICY} ON {_TABLE}
FOR ALL
USING (
  organization_id = current_setting('{_ORG_ID}', true)::uuid
  AND is_demo = current_setting('{_IS_DEMO}', true)::boolean
)
WITH CHECK (
  organization_id = current_setting('{_ORG_ID}', true)::uuid
  AND is_demo = current_setting('{_IS_DEMO}', true)::boolean
);
"""
        )
    )
