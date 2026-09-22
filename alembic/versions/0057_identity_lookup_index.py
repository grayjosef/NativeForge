"""Alembic 0057: a partial UNIQUE index is not a lookup index (Gate 171AJ).

Migration 0056 made the identity index partial so the graph could hold more
than one provisional opportunity. It fixed that. It also, silently, removed
the index path for every identity lookup:

```sql
-- the query the canonical write path issues
SELECT canonical_id FROM nf_canonical_opportunities
WHERE normalized_opportunity_number = ? AND doc_type = ?
--> SCAN nf_canonical_opportunities
```

A partial index can only serve a query whose predicate IMPLIES the index
predicate. This query does not carry `normalized_opportunity_number <> ''`,
so neither SQLite nor PostgreSQL may use the index, and the lookup became a
full table scan.

Measured: identity lookup 0.09ms -> 9.85ms at 50,000 rows, and linear from
there. Gate 167's `all_probed_lookups_use_an_index` caught it; the full suite
did not, because a scan is correct, just slow.

## Two indexes, because there are two jobs

```text
uq_..._identity          partial, UNIQUE   the CONSTRAINT: one canonical
                                           record per published identity
ix_..._identity_lookup   full, non-unique  the ACCESS PATH: find a record by
                                           number and doc type
```

The constraint stays exactly as 0056 left it - provisional rows still do not
compete for one slot. The lookup index is not unique, so it imposes nothing;
it only gives the planner something to use.

The obvious alternative was to add `AND normalized_opportunity_number <> ''`
to the query. Rejected: it couples every caller to an index predicate, and it
silently returns nothing for the provisional rows 0056 exists to support.
"""

from __future__ import annotations

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | None = None
depends_on: str | None = None

CANONICAL = "nf_canonical_opportunities"
LOOKUP_INDEX = f"ix_{CANONICAL}_identity_lookup"


def upgrade() -> None:
    op.create_index(
        LOOKUP_INDEX,
        CANONICAL,
        ["normalized_opportunity_number", "doc_type"],
    )


def downgrade() -> None:
    op.drop_index(LOOKUP_INDEX, table_name=CANONICAL)
