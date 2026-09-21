"""Alembic 0054: cross-source opportunity identity (Gate 169B/K/M/P).

Gate 167 gave one opportunity many observations. This lets many CANONICAL
opportunities be related to each other - the same opportunity republished, an
annual recurrence, a forecast that became a posting - without any of them
losing their own evidence.

## A merge is a relationship, never a rewrite

The obvious way to merge two canonical opportunities is to repoint one's rows
at the other and delete it. That is also irreversible: the moment the rows
move, the evidence that they were ever separate is gone, and an incorrect
merge cannot be undone without the raw payloads and a rebuild.

So a merge here is a **SAME_AS row**. Both canonical opportunities keep their
observations, versions and provenance untouched; one is designated primary for
display. Reversing an incorrect merge is deleting a relationship row, and
Gate 169L proves nothing is lost when it happens. Reversibility is structural
rather than a feature somebody has to remember to implement.

## L3 and L4 may not present themselves as settled

```sql
CHECK (identity_layer NOT IN ('L3','L4') OR is_provisional = 1)
```

Migration 0053 enforced this for L4. L2 and L3 were declared by the identity
service and were not storable at all - the CHECK admitted only L1 and L4 - so
this widens the vocabulary to all four layers and extends the provisional rule
to L3 as well.

Both L3 and L4 rest on composites nobody publishes: a normalized title, an
agency matched by name, a temporal window. The identity service is explicit
that agency identity spans three non-matching namespaces and **refuses to
match agencies by name string**. A layer built on that must not be able to
claim it is settled.

## And a SAME_AS may not be minted by a machine at those layers

```sql
CHECK (relationship <> 'SAME_AS'
       OR identity_layer IN ('L1','L2')
       OR decided_by = 'human_review')
```

This is the load-bearing constraint of the gate. "L4 can never silently create
a settled canonical merge" is not a convention here - a fuzzy SAME_AS with no
human decision has **no representation at rest**. Gate 164 established that
making bad state unwritable beats detecting it afterwards.

## Blocking keys exist so fuzzy matching never scans the graph

`nf_opportunity_blocking_keys` maps one opportunity to many deterministic keys
- its normalized number, its funder and fiscal year, a title band. Candidate
generation looks up the key, not the population. The index on
`(key_kind, key_value)` is what makes that bounded, and Gate 169P measures the
candidate set size rather than trusting the design.

## A review decision needs a signer

```sql
CHECK (review_state NOT IN ('approved_merge','rejected_merge')
       OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
```

The same rule migration 0048 applies to source authorization decisions. A
merge approval nobody signed is not a decision, and Gate 169R has to replay
human decisions from persisted facts rather than recomputing them - which is
only possible if the facts carry who decided and when.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: str | Sequence[str] | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL = "nf_canonical_opportunities"
BLOCKING = "nf_opportunity_blocking_keys"
RELATIONSHIPS = "nf_opportunity_identity_relationships"
CANDIDATES = "nf_opportunity_identity_candidates"

#: All four layers the identity service declares. 0053 admitted only L1 and L4.
IDENTITY_LAYERS = ("L1", "L2", "L3", "L4")

#: Layers that rest on composites nobody publishes, and may never be settled.
PROVISIONAL_LAYERS = ("L3", "L4")

#: Layers strong enough for a machine to assert SAME_AS.
SETTLED_LAYERS = ("L1", "L2")

RELATIONSHIPS_VOCAB = (
    "SAME_AS",
    "VERSION_OF",
    "RECURRENCE_OF",
    "FORECAST_OF",
    "REPUBLISHED_FROM",
    "RELATED_TO",
)

MATCH_DECISIONS = (
    "EXACT_MATCH",
    "STRONG_MATCH",
    "PROVISIONAL_MATCH",
    "DISTINCT",
    "VERSION_OF",
    "RECURRENCE_OF",
    "FORECAST_OF",
    "REPUBLISHED_FROM",
    "REVIEW_REQUIRED",
)

DECIDED_BY = ("derived", "human_review")

REVIEW_STATES = (
    "pending",
    "approved_merge",
    "rejected_merge",
    "marked_related",
    "deferred",
)

BLOCKING_KEY_KINDS = (
    "opportunity_number",
    "funder_and_period",
    # A composite of funder, fiscal year and title band. Gate 169O measured
    # `funder_and_period` alone growing 25 -> 125 -> 201 candidates as the
    # graph went 1k -> 5k -> 10k, because a fleet has a bounded number of
    # funders and that bucket therefore grows with the corpus forever. The
    # composite is selective enough to generate candidates from while still
    # catching the republish shape: same funder, same year, same title.
    "funder_period_title",
    "title_band",
    "program_family",
    "source_record_alias",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def _not_in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} NOT IN ({joined})"


def upgrade() -> None:
    # ---- widen the identity layer vocabulary -------------------------
    with op.batch_alter_table(CANONICAL) as batch:
        batch.drop_constraint(f"ck_{CANONICAL}_layer", type_="check")
        batch.create_check_constraint(
            f"ck_{CANONICAL}_layer", _in_list("identity_layer", IDENTITY_LAYERS)
        )
        batch.drop_constraint(f"ck_{CANONICAL}_l4_is_provisional", type_="check")
        # Widened from L4 to both probabilistic layers.
        batch.create_check_constraint(
            f"ck_{CANONICAL}_probabilistic_is_provisional",
            f"{_not_in_list('identity_layer', PROVISIONAL_LAYERS)}"
            " OR is_provisional = 1",
        )

    # ---- blocking keys ----------------------------------------------
    op.create_table(
        BLOCKING,
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("key_kind", sa.Text(), nullable=False),
        sa.Column("key_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "canonical_id", "key_kind", "key_value", name=f"pk_{BLOCKING}"
        ),
        sa.CheckConstraint(
            _in_list("key_kind", BLOCKING_KEY_KINDS), name=f"ck_{BLOCKING}_kind"
        ),
        sa.CheckConstraint("length(key_value) > 0", name=f"ck_{BLOCKING}_value"),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{BLOCKING}_c"
        ),
    )
    # THE index candidate generation depends on. Without it, blocking is a
    # full scan wearing a bounded-lookup costume.
    op.create_index(f"ix_{BLOCKING}_lookup", BLOCKING, ["key_kind", "key_value"])
    op.create_index(f"ix_{BLOCKING}_canonical", BLOCKING, ["canonical_id"])

    # ---- the identity relationship graph ----------------------------
    op.create_table(
        RELATIONSHIPS,
        sa.Column("relationship_id", sa.Text(), primary_key=True),
        sa.Column("from_canonical_id", sa.Text(), nullable=False),
        sa.Column("to_canonical_id", sa.Text(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=False),
        sa.Column("match_decision", sa.Text(), nullable=False),
        sa.Column("identity_layer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer", sa.Text(), nullable=True),
        sa.Column("candidate_id", sa.Text(), nullable=True),
        # A merge designates one side primary for display. Both keep their
        # own observations, versions and provenance.
        sa.Column("primary_canonical_id", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Text(), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("relationship", RELATIONSHIPS_VOCAB),
            name=f"ck_{RELATIONSHIPS}_kind",
        ),
        sa.CheckConstraint(
            _in_list("match_decision", MATCH_DECISIONS),
            name=f"ck_{RELATIONSHIPS}_decision",
        ),
        sa.CheckConstraint(
            _in_list("identity_layer", IDENTITY_LAYERS),
            name=f"ck_{RELATIONSHIPS}_layer",
        ),
        sa.CheckConstraint(
            _in_list("decided_by", DECIDED_BY), name=f"ck_{RELATIONSHIPS}_decided_by"
        ),
        # An opportunity is not related to itself.
        sa.CheckConstraint(
            "from_canonical_id <> to_canonical_id", name=f"ck_{RELATIONSHIPS}_self"
        ),
        # THE constraint of this gate: a fuzzy SAME_AS nobody reviewed has no
        # representation at rest.
        sa.CheckConstraint(
            "relationship <> 'SAME_AS'"
            f" OR {_in_list('identity_layer', SETTLED_LAYERS)}"
            " OR decided_by = 'human_review'",
            name=f"ck_{RELATIONSHIPS}_no_silent_fuzzy_merge",
        ),
        # A human decision names the human.
        sa.CheckConstraint(
            "decided_by <> 'human_review' OR reviewer IS NOT NULL",
            name=f"ck_{RELATIONSHIPS}_human_needs_reviewer",
        ),
        # A revocation names who and why - Gate 169L has to show that
        # reversing a merge is recorded, not silent.
        sa.CheckConstraint(
            "revoked_at IS NULL OR (revoked_by IS NOT NULL"
            " AND revoked_reason IS NOT NULL)",
            name=f"ck_{RELATIONSHIPS}_revocation_is_attributed",
        ),
        sa.ForeignKeyConstraint(
            ["from_canonical_id"],
            [f"{CANONICAL}.canonical_id"],
            name=f"fk_{RELATIONSHIPS}_from",
        ),
        sa.ForeignKeyConstraint(
            ["to_canonical_id"],
            [f"{CANONICAL}.canonical_id"],
            name=f"fk_{RELATIONSHIPS}_to",
        ),
    )
    op.create_index(
        f"uq_{RELATIONSHIPS}_edge",
        RELATIONSHIPS,
        ["from_canonical_id", "to_canonical_id", "relationship"],
        unique=True,
    )
    op.create_index(f"ix_{RELATIONSHIPS}_from", RELATIONSHIPS, ["from_canonical_id"])
    op.create_index(f"ix_{RELATIONSHIPS}_to", RELATIONSHIPS, ["to_canonical_id"])
    op.create_index(
        f"ix_{RELATIONSHIPS}_kind_active",
        RELATIONSHIPS,
        ["relationship", "revoked_at"],
    )

    # ---- reviewable provisional candidates --------------------------
    op.create_table(
        CANDIDATES,
        sa.Column("candidate_id", sa.Text(), primary_key=True),
        # Ordered so (A,B) and (B,A) are one candidate, not two.
        sa.Column("canonical_a", sa.Text(), nullable=False),
        sa.Column("canonical_b", sa.Text(), nullable=False),
        sa.Column("proposed_relationship", sa.Text(), nullable=False),
        sa.Column("match_decision", sa.Text(), nullable=False),
        sa.Column("identity_layer", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column(
            "review_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("proposed_relationship", RELATIONSHIPS_VOCAB),
            name=f"ck_{CANDIDATES}_relationship",
        ),
        sa.CheckConstraint(
            _in_list("match_decision", MATCH_DECISIONS),
            name=f"ck_{CANDIDATES}_decision",
        ),
        sa.CheckConstraint(
            _in_list("identity_layer", IDENTITY_LAYERS),
            name=f"ck_{CANDIDATES}_layer",
        ),
        sa.CheckConstraint(
            _in_list("review_state", REVIEW_STATES), name=f"ck_{CANDIDATES}_state"
        ),
        sa.CheckConstraint(
            "canonical_a <> canonical_b", name=f"ck_{CANDIDATES}_self"
        ),
        sa.CheckConstraint(
            "canonical_a < canonical_b", name=f"ck_{CANDIDATES}_ordered"
        ),
        # The same rule migration 0048 applies to authorization decisions: a
        # resolution nobody signed is not a decision, and Gate 169R replays
        # human decisions from these facts rather than recomputing them.
        sa.CheckConstraint(
            "review_state NOT IN ('approved_merge', 'rejected_merge')"
            " OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name=f"ck_{CANDIDATES}_resolution_needs_signature",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_a"],
            [f"{CANONICAL}.canonical_id"],
            name=f"fk_{CANDIDATES}_a",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_b"],
            [f"{CANONICAL}.canonical_id"],
            name=f"fk_{CANDIDATES}_b",
        ),
    )
    op.create_index(
        f"uq_{CANDIDATES}_pair",
        CANDIDATES,
        ["canonical_a", "canonical_b", "proposed_relationship"],
        unique=True,
    )
    op.create_index(f"ix_{CANDIDATES}_state", CANDIDATES, ["review_state"])
    op.create_index(f"ix_{CANDIDATES}_a", CANDIDATES, ["canonical_a"])
    op.create_index(f"ix_{CANDIDATES}_b", CANDIDATES, ["canonical_b"])


def downgrade() -> None:
    op.drop_table(CANDIDATES)
    op.drop_table(RELATIONSHIPS)
    op.drop_table(BLOCKING)
    with op.batch_alter_table(CANONICAL) as batch:
        batch.drop_constraint(
            f"ck_{CANONICAL}_probabilistic_is_provisional", type_="check"
        )
        batch.create_check_constraint(
            f"ck_{CANONICAL}_l4_is_provisional",
            "identity_layer <> 'L4' OR is_provisional = 1",
        )
        batch.drop_constraint(f"ck_{CANONICAL}_layer", type_="check")
        batch.create_check_constraint(
            f"ck_{CANONICAL}_layer", _in_list("identity_layer", ("L1", "L4"))
        )
