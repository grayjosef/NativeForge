"""Alembic 0065: durable customer decisions, and the paths a dashboard reads.

The Gate 179 survey found the existing decision tables recording a time and
nothing else:

```text
nf_source_watchlist_entries     457 rows   records_actor = false
nf_tenant_pursuit_suppressions  124 rows   records_actor = false
```

A dismissal nobody is recorded as having made cannot be reviewed or
explained to the person who later asks why an opportunity they were eligible
for never appeared.

Two tables:

```text
nf_customer_opportunity_decisions  the CURRENT decision, one per org+opportunity
nf_customer_decision_history       every decision that came before it
```

Current state and history are separate tables on purpose. The dashboard asks
"what is this organisation watching" on every page load and must not walk a
history to find out; the history exists because "why did this stop appearing"
is a question somebody asks months later.

## The constraints

`ck_..._decision_names_its_actor` - every human decision names who made it
and when. This is the survey's finding made unrepresentable.

`ck_..._decision_names_its_opportunity` - a decision about nothing in
particular cannot be stored. The canonical id is how the decision is tied to
the graph, and a decision without one is the hand-made-spark problem wearing
a different hat.

The primary key is (organization_id, canonical_id), so one organisation has
exactly one current decision per opportunity and a second write updates
rather than accumulating duplicates that disagree.

Preserves 0056 through 0064.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | None = None
depends_on: str | None = None

DECISIONS = "nf_customer_opportunity_decisions"
HISTORY = "nf_customer_decision_history"

DECISION_STATES = ("NEW", "WATCHED", "DISMISSED", "PURSUING")

#: States a human must have chosen. NEW is the absence of a decision.
HUMAN_DECIDED = ("WATCHED", "DISMISSED", "PURSUING")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        DECISIONS,
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("decision_state", sa.String(length=16), nullable=False),
        sa.Column("previous_state", sa.String(length=16), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        # One current decision per organisation per opportunity. A second
        # write updates it rather than adding a duplicate that disagrees.
        sa.PrimaryKeyConstraint(
            "organization_id", "canonical_id", name=f"pk_{DECISIONS}"
        ),
        sa.CheckConstraint(
            _in_list("decision_state", DECISION_STATES), name=f"ck_{DECISIONS}_state"
        ),
        sa.CheckConstraint(
            "previous_state IS NULL OR " + _in_list("previous_state", DECISION_STATES),
            name=f"ck_{DECISIONS}_previous_state",
        ),
        # The survey's finding, made unrepresentable.
        sa.CheckConstraint(
            f"{_in_list('decision_state', HUMAN_DECIDED)} = 0 "
            "OR (actor_id IS NOT NULL AND decided_at IS NOT NULL)",
            name=f"ck_{DECISIONS}_decision_names_its_actor",
        ),
        sa.CheckConstraint(
            "length(trim(canonical_id)) > 0",
            name=f"ck_{DECISIONS}_decision_names_its_opportunity",
        ),
    )
    # 179E/179J: the three questions a dashboard asks on every page load.
    op.create_index(
        f"ix_{DECISIONS}_org_state", DECISIONS, ["organization_id", "decision_state"]
    )
    op.create_index(
        f"ix_{DECISIONS}_opportunity", DECISIONS, ["canonical_id", "decision_state"]
    )

    op.create_table(
        HISTORY,
        sa.Column("history_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("decision_state", sa.String(length=16), nullable=False),
        sa.Column("previous_state", sa.String(length=16), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            _in_list("decision_state", DECISION_STATES), name=f"ck_{HISTORY}_state"
        ),
    )
    # "Why did this stop appearing" - asked about one opportunity, months on.
    op.create_index(
        f"ix_{HISTORY}_org_opportunity",
        HISTORY,
        ["organization_id", "canonical_id", "superseded_at"],
    )


def downgrade() -> None:
    op.drop_index(f"ix_{HISTORY}_org_opportunity", table_name=HISTORY)
    op.drop_table(HISTORY)

    op.drop_index(f"ix_{DECISIONS}_opportunity", table_name=DECISIONS)
    op.drop_index(f"ix_{DECISIONS}_org_state", table_name=DECISIONS)
    op.drop_table(DECISIONS)
