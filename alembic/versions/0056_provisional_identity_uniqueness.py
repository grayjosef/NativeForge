"""Alembic 0056: one provisional record per graph was not the intent (Gate 171J).

Gate 167 gave the canonical table this:

```sql
CREATE UNIQUE INDEX uq_nf_canonical_opportunities_identity
  ON nf_canonical_opportunities (normalized_opportunity_number, doc_type)
```

Correct for every source that existed when it was written. Grants.gov
publishes an opportunity number on every record, so the pair was distinct per
opportunity and the index said what it meant: one canonical record per
published identity.

## What a document source does to it

A source that publishes no opportunity number gets an L4 provisional identity.
Migration 0053 already anticipated that - `ck_..._l1_needs_number` permits an
empty number precisely when the layer is not L1. But every such row stores
`normalized_opportunity_number = ''` and `doc_type = 'unknown'`, so they all
collide on ONE index entry.

**The graph could hold exactly one provisional opportunity, ever.** The second
was an IntegrityError. Gate 171 found it the moment a second source family
arrived: the first BIA page landed, and every subsequent document-shaped
record was refused by an index that had silently become a singleton.

At a thousand sources that is not an edge case. Most agency program pages
publish no opportunity number.

## The fix is to say what was always meant

Uniqueness applies to a PUBLISHED identity. A record with no published number
has no published identity to be unique on, and its uniqueness is already
guaranteed by `canonical_id` - the primary key, derived from the L4 fuzzy key.

So the index becomes partial:

```sql
... WHERE normalized_opportunity_number <> ''
```

L1 keeps exactly the guarantee it had. L3/L4 rows stop competing for one slot.

Nothing about provisional semantics is loosened: `ck_..._probabilistic_is_
provisional` still forces `is_provisional` on L3 and L4, a provisional record
still cannot settle without a recorded human decision, and promotion to L1
still changes the canonical id.

Both dialects get a real partial index - SQLite and PostgreSQL both support
`CREATE UNIQUE INDEX ... WHERE`, so this is not a SQLite-shaped workaround.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | None = None
depends_on: str | None = None

CANONICAL = "nf_canonical_opportunities"
INDEX_NAME = f"uq_{CANONICAL}_identity"

#: Only rows that carry a published number participate. An empty number is not
#: a value that can collide with another empty number, because neither is an
#: identity.
PARTIAL_WHERE = sa.text("normalized_opportunity_number <> ''")


def upgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=CANONICAL)
    op.create_index(
        INDEX_NAME,
        CANONICAL,
        ["normalized_opportunity_number", "doc_type"],
        unique=True,
        sqlite_where=PARTIAL_WHERE,
        postgresql_where=PARTIAL_WHERE,
    )


def downgrade() -> None:
    # Reinstating the total index can fail where more than one provisional
    # record exists - which is the whole point of this migration. It is not
    # silently made possible here.
    op.drop_index(INDEX_NAME, table_name=CANONICAL)
    op.create_index(
        INDEX_NAME,
        CANONICAL,
        ["normalized_opportunity_number", "doc_type"],
        unique=True,
    )
