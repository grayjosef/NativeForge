"""Initial empty revision (NF-000 scaffold — domain tables follow in later tickets).

Revision ID: 0001
Revises:
Create Date: 2026-05-05

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
