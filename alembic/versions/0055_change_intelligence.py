"""Alembic 0055: durable change events and conflict state (Gate 170B/G/I).

Gate 168's writer already computes the diff between two versions and stores
`changed_fields_json` on the version row. That answers "which fields moved".
It cannot answer "was the deadline shortened or extended", "how much should an
operator care", "which source proved it", or "do two sources still disagree
about this field, and since when".

So this adds two stores and **no second diff**. The existing comparison stays
the only comparison; these tables record what it found, typed and queryable.

## A change event names one field moving between two versions

```text
change_event_id = sha256(canonical_id | prior_version_id | new_version_id | field)
```

Derived, like every other identifier in this graph, so replaying the same
evidence produces the same event id and collides with itself. Gate 170G
requires zero duplicate events on replay; that is a primary-key collision
rather than a comparison somebody has to remember to write.

```sql
CHECK (length(raw_payload_sha256) = 64)
```

A change event must name the bytes that prove it. The same rule migrations
0053 applied to observations and field provenance: a claim tracing to nothing
has no representation at rest.

## Materiality carries the rule that decided it

```sql
CHECK (materiality = 'UNKNOWN' OR length(materiality_rule) > 0)
```

"This change is CRITICAL" is not reviewable. "This change is CRITICAL because
`deadline_shortened`" is. A classification with no rule behind it is an
opinion, and an operator woken at 2am deserves better than an opinion.

## Conflict state is a row with a beginning

Gate 167 records two provenance rows when two sources disagree. That preserves
the facts but says nothing about *when* the disagreement started, whether it
is still live, or whether anybody resolved it. `first_detected_at` and
`last_observed_at` make a conflict something with a duration - which is what
turns "these sources disagree" into "these sources have disagreed about this
deadline for eleven days".

```sql
CHECK (conflict_state <> 'RESOLVED_CONFLICT'
       OR (resolved_at IS NOT NULL
           AND resolved_by IS NOT NULL
           AND resolution_evidence_json IS NOT NULL))
```

A resolution nobody signed, with no evidence, is not a resolution. The same
discipline migration 0048 applies to authorization decisions and 0054 applies
to identity merges.

## One conflict row per field, not per disagreement

The unique index is `(canonical_id, field_name)`. A field is either contested
or it is not; two sources flapping back and forth is one ongoing conflict with
a moving `last_observed_at`, not a new row each time. Without that, a
repeatedly-polled pair of disagreeing sources would manufacture a conflict row
per poll - which at thousands of sources is the whole point of getting this
right.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: str | Sequence[str] | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL = "nf_canonical_opportunities"
VERSIONS = "nf_opportunity_versions"
OBSERVATIONS = "nf_opportunity_source_observations"
EVENTS = "nf_opportunity_change_events"
CONFLICTS = "nf_opportunity_field_conflicts"

#: The change taxonomy Gate 170B names. `UNKNOWN_CHANGE` is a real answer for
#: a field the taxonomy does not model - inventing a type would be worse.
CHANGE_TYPES = (
    "TITLE_CHANGED",
    "STATUS_CHANGED",
    "OPEN_DATE_CHANGED",
    "DEADLINE_CHANGED",
    "DEADLINE_EXTENDED",
    "DEADLINE_SHORTENED",
    "FUNDING_MIN_CHANGED",
    "FUNDING_MAX_CHANGED",
    "ELIGIBILITY_CHANGED",
    "AGENCY_CHANGED",
    "OPPORTUNITY_NUMBER_CHANGED",
    "DOCUMENT_ADDED",
    "DOCUMENT_REMOVED",
    "DOCUMENT_REPLACED",
    "SOURCE_URL_CHANGED",
    "ASSISTANCE_LISTINGS_CHANGED",
    "FORECAST_TO_POSTED",
    "POSTED_TO_CLOSED",
    "REOPENED",
    "CANCELLED",
    "AMENDMENT_PUBLISHED",
    "CONFLICT_INTRODUCED",
    "CONFLICT_RESOLVED",
    "FIRST_OBSERVED",
    "UNKNOWN_CHANGE",
)

MATERIALITY = (
    "CRITICAL",
    "MATERIAL",
    "INFORMATIONAL",
    "NON_MATERIAL",
    "UNKNOWN",
)

CONFLICT_STATES = (
    "NO_CONFLICT",
    "OPEN_CONFLICT",
    "RESOLVED_CONFLICT",
    "REVIEW_REQUIRED",
)

#: Deadline shapes from the Gate 92G research pass. Carried on the event so a
#: per-region or dual deadline change is never reported as a single national
#: date moving.
DEADLINE_SHAPES = (
    "single",
    "dual",
    "per_region",
    "phased",
    "revised",
    "multi_year",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    # ------------------------------------------------ change events
    op.create_table(
        EVENTS,
        sa.Column("change_event_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        # NULL for a first observation: there is no prior version, and a
        # sentinel would make "first seen" indistinguishable from a change
        # from nothing.
        sa.Column("prior_version_id", sa.Text(), nullable=True),
        sa.Column("new_version_id", sa.Text(), nullable=False),
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("materiality", sa.Text(), nullable=False),
        # The named rule that decided the class. Not optional for anything
        # other than UNKNOWN.
        sa.Column("materiality_rule", sa.Text(), nullable=True),
        sa.Column("prior_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("raw_payload_sha256", sa.Text(), nullable=False),
        sa.Column("deadline_shape", sa.Text(), nullable=True),
        # When the graph noticed, and the date the change is about - which are
        # different things and must not be conflated.
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_date", sa.Text(), nullable=True),
        # Gate 170H: a second source reporting the SAME semantic change
        # corroborates it rather than creating a second event.
        sa.Column(
            "corroborating_source_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("corroborated_by_json", sa.Text(), nullable=True),
        sa.Column("first_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("change_type", CHANGE_TYPES), name=f"ck_{EVENTS}_type"
        ),
        sa.CheckConstraint(
            _in_list("materiality", MATERIALITY), name=f"ck_{EVENTS}_materiality"
        ),
        sa.CheckConstraint(
            "deadline_shape IS NULL OR "
            + _in_list("deadline_shape", DEADLINE_SHAPES),
            name=f"ck_{EVENTS}_deadline_shape",
        ),
        # A change event names the bytes that prove it.
        sa.CheckConstraint(
            "length(raw_payload_sha256) = 64", name=f"ck_{EVENTS}_evidence"
        ),
        # A classification with no rule behind it is an opinion.
        sa.CheckConstraint(
            "materiality = 'UNKNOWN' OR (materiality_rule IS NOT NULL "
            "AND length(materiality_rule) > 0)",
            name=f"ck_{EVENTS}_materiality_is_rule_backed",
        ),
        # A change is between two DIFFERENT versions, or a first observation.
        sa.CheckConstraint(
            "prior_version_id IS NULL OR prior_version_id <> new_version_id",
            name=f"ck_{EVENTS}_versions_differ",
        ),
        sa.CheckConstraint(
            "corroborating_source_count >= 1", name=f"ck_{EVENTS}_corroboration"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{EVENTS}_c"
        ),
        sa.ForeignKeyConstraint(
            ["new_version_id"], [f"{VERSIONS}.version_id"], name=f"fk_{EVENTS}_v"
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            [f"{OBSERVATIONS}.observation_id"],
            name=f"fk_{EVENTS}_o",
        ),
    )
    # Idempotency at rest: one event per (version pair, field).
    op.create_index(
        f"uq_{EVENTS}_identity",
        EVENTS,
        ["canonical_id", "prior_version_id", "new_version_id", "field_name"],
        unique=True,
    )
    op.create_index(
        f"ix_{EVENTS}_canonical", EVENTS, ["canonical_id", "detected_at"]
    )
    op.create_index(f"ix_{EVENTS}_materiality", EVENTS, ["materiality", "detected_at"])
    op.create_index(f"ix_{EVENTS}_type", EVENTS, ["change_type", "detected_at"])
    op.create_index(f"ix_{EVENTS}_field", EVENTS, ["canonical_id", "field_name"])
    op.create_index(f"ix_{EVENTS}_version", EVENTS, ["new_version_id"])
    op.create_index(f"ix_{EVENTS}_payload", EVENTS, ["raw_payload_sha256"])

    # --------------------------------------------- conflict state
    op.create_table(
        CONFLICTS,
        sa.Column("conflict_id", sa.Text(), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column(
            "conflict_state",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'OPEN_CONFLICT'"),
        ),
        # Every competing value with the source that asserts it. The facts
        # themselves stay in field provenance; this is the disagreement.
        sa.Column("competing_values_json", sa.Text(), nullable=False),
        sa.Column("competing_source_count", sa.Integer(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolution_rule", sa.Text(), nullable=True),
        sa.Column("resolution_evidence_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            _in_list("conflict_state", CONFLICT_STATES),
            name=f"ck_{CONFLICTS}_state",
        ),
        # A resolution nobody signed, with no evidence, is not a resolution.
        sa.CheckConstraint(
            "conflict_state <> 'RESOLVED_CONFLICT' OR (resolved_at IS NOT NULL "
            "AND resolved_by IS NOT NULL AND resolution_evidence_json IS NOT NULL)",
            name=f"ck_{CONFLICTS}_resolution_is_attributed",
        ),
        # A conflict needs at least two sides.
        sa.CheckConstraint(
            "conflict_state = 'NO_CONFLICT' OR competing_source_count >= 2",
            name=f"ck_{CONFLICTS}_needs_two_sides",
        ),
        sa.ForeignKeyConstraint(
            ["canonical_id"], [f"{CANONICAL}.canonical_id"], name=f"fk_{CONFLICTS}_c"
        ),
    )
    # One row per contested field, whatever the poll count.
    op.create_index(
        f"uq_{CONFLICTS}_field",
        CONFLICTS,
        ["canonical_id", "field_name"],
        unique=True,
    )
    op.create_index(f"ix_{CONFLICTS}_state", CONFLICTS, ["conflict_state"])
    op.create_index(
        f"ix_{CONFLICTS}_open", CONFLICTS, ["conflict_state", "last_observed_at"]
    )


def downgrade() -> None:
    op.drop_table(CONFLICTS)
    op.drop_table(EVENTS)
