"""Initial empty revision (NF-000 scaffold — domain tables follow in later tickets).

Revision ID: 0001
Revises:
Create Date: 2026-05-05

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
