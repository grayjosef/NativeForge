"""Alembic 0062: early signals, program recurrence, and award coverage misses.

Gate 176 built its model in memory. Schema is added here for one reason: 176K
requires eight indexed access paths over 100,000 historical instances, and an
access path cannot be indexed if it does not exist. JSON being inconvenient
would not have been a reason.

Four tables:

```text
nf_early_funding_signals        one observed trace, never an opportunity
nf_program_recurrences          one program's cadence, derived from cycles
nf_program_recurrence_cycles    the observed cycles a cadence rests on
nf_award_coverage_misses        an award with no solicitation we ever saw
nf_coverage_gap_signal_links    which signals back which coverage gap
```

## The refusals become unrepresentable

Gate 176's promises are enforced in Python by `signal_invariant_failures` and
friends. A verifier that only checks the Python can be defeated by any writer
that bypasses it, so the load-bearing ones are restated as CHECK constraints:

`ck_..._signal_has_evidence` - a signal with no payload hash, no document
reference and no human willing to sign it is not evidence and cannot be
stored. `ASSERTED_BY_HUMAN` is the only confidence class that stands alone.

`ck_..._signal_never_creates_an_opportunity` and
`ck_..._signal_never_auto_onboards` pin those columns to false. They exist as
columns at all so that a reader of the row sees the refusal stated, and so
that any attempt to flip one fails at the database rather than in review.

`ck_..._expectation_needs_enough_history` - EXPECTED or POSSIBLE below three
observed cycles is a forecast from a coincidence. This is the constraint that
makes "insufficient history not forecast" a property of the store.

`ck_..._demo_award_never_counts_toward_real_metrics` - every award row in this
repository is a Gate 138 demo fixture on the protected demo organisation.
Without this, the coverage scorecard would report 2,757 fabricated failures,
and the one number whose job is to be uncomfortable would become noise.

`ck_..._miss_needs_zero_observed_solicitations` - a miss exists only when
nothing was seen. Anything else inflates the count.

Coverage gap links carry a foreign key to the signal table, so a gap backed by
a signal that does not exist cannot be written at all.

Preserves 0056 through 0061.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | None = None
depends_on: str | None = None

SIGNALS = "nf_early_funding_signals"
RECURRENCES = "nf_program_recurrences"
CYCLES = "nf_program_recurrence_cycles"
MISSES = "nf_award_coverage_misses"
GAP_LINKS = "nf_coverage_gap_signal_links"

SIGNAL_TYPES = (
    "AWARD_WITHOUT_SOLICITATION",
    "AMENDMENT_WITHOUT_ORIGINAL",
    "PROGRAM_REFERENCE_WITHOUT_SOURCE",
    "EXPECTED_RECURRING_PROGRAM_ABSENT",
    "BUDGET_FUNDING_REFERENCE",
    "CALENDAR_FUNDING_REFERENCE",
    "FEDERAL_REGISTER_PRENOTICE",
    "AGENCY_PREANNOUNCEMENT",
    "GRANTEE_ANNOUNCEMENT",
    "SOURCE_REFERENCES_UNMONITORED_PUBLISHER",
    "DEADLINE_WITHOUT_OPPORTUNITY",
    "PROGRAM_CYCLE_DEVIATION",
    "OTHER_SIGNAL",
)

SIGNAL_STATES = (
    "OBSERVED",
    "CORROBORATED",
    "UNDER_REVIEW",
    "LINKED_TO_OPPORTUNITY",
    "DISMISSED",
    "STALE",
    "RESOLVED",
    "UNKNOWN",
)

#: States in which a signal may carry an opportunity link.
LINK_BEARING_STATES = ("LINKED_TO_OPPORTUNITY", "RESOLVED")

#: States in which a signal is still an open question for somebody. These
#: define the partial index behind the triage queue, so they must match the
#: repository's WHERE clause exactly or SQLite will ignore the index.
OPEN_SIGNAL_STATES = ("OBSERVED", "CORROBORATED", "UNDER_REVIEW", "UNKNOWN")

CONFIDENCE_CLASSES = (
    "OBSERVED_FACT",
    "DERIVED_FACT",
    "INFERRED_FACT",
    "ASSERTED_BY_HUMAN",
    "UNKNOWN_CONFIDENCE",
)

AMBIGUITY_CLASSES = (
    "NO_AMBIGUITY",
    "PROGRAM_AMBIGUOUS",
    "FUNDER_AMBIGUOUS",
    "TEMPORAL_AMBIGUOUS",
    "AMOUNT_AMBIGUOUS",
)

RECURRENCE_CLASSES = ("ANNUAL", "BIENNIAL", "PERIODIC", "IRREGULAR", "UNKNOWN")

EXPECTATION_STATES = (
    "EXPECTED",
    "POSSIBLE",
    "INSUFFICIENT_HISTORY",
    "IRREGULAR",
    "UNKNOWN",
)

#: Expectation states that project a window somebody could be late for.
FORECASTING_STATES = ("EXPECTED", "POSSIBLE")

#: Below this many observed cycles, a cadence is a coincidence.
MINIMUM_CYCLES_FOR_CADENCE = 3

#: How we know two instances are the same program. Title similarity is not
#: here on purpose: a cadence from a name collision is worse than none.
IDENTITY_BASES = (
    "assistance_listing",
    "program_number",
    "stable_source_path",
    "program_authority",
)

MISS_RESOLUTIONS = (
    "UNRESOLVED",
    "SOLICITATION_FOUND_LATE",
    "PUBLISHER_ONBOARDED",
    "NOT_A_COMPETITIVE_AWARD",
    "OUT_OF_SCOPE",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # ---------------- signals ----------------------------------------
    op.create_table(
        SIGNALS,
        sa.Column("signal_id", sa.String(length=64), primary_key=True),
        sa.Column("signal_type", sa.String(length=48), nullable=False),
        sa.Column("signal_state", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("program_key", sa.Text(), nullable=True),
        sa.Column("program_name", sa.Text(), nullable=True),
        sa.Column("funder_name", sa.Text(), nullable=True),
        # Evidence. One of these must be present, or a human must sign it.
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("document_ref", sa.Text(), nullable=True),
        sa.Column("supporting_text", sa.Text(), nullable=False),
        # A SUGGESTION about identity, never an identity.
        sa.Column("possible_opportunity_number", sa.Text(), nullable=True),
        sa.Column("confidence_class", sa.String(length=32), nullable=False),
        sa.Column("ambiguity_class", sa.String(length=32), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("is_miss_evidence", sa.Boolean(), nullable=False),
        sa.Column("is_forward_looking", sa.Boolean(), nullable=False),
        sa.Column("linked_canonical_id", sa.Text(), nullable=True),
        sa.Column("linked_gap_id", sa.Text(), nullable=True),
        # Stated on the row so nothing downstream can read it as licence.
        sa.Column("creates_opportunity", sa.Boolean(), nullable=False),
        sa.Column("auto_onboarding_permitted", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("signal_type", SIGNAL_TYPES), name=f"ck_{SIGNALS}_type"
        ),
        sa.CheckConstraint(
            _in_list("signal_state", SIGNAL_STATES), name=f"ck_{SIGNALS}_state"
        ),
        sa.CheckConstraint(
            _in_list("confidence_class", CONFIDENCE_CLASSES),
            name=f"ck_{SIGNALS}_confidence",
        ),
        sa.CheckConstraint(
            _in_list("ambiguity_class", AMBIGUITY_CLASSES),
            name=f"ck_{SIGNALS}_ambiguity",
        ),
        # A claim about the world needs something behind it.
        sa.CheckConstraint(
            "raw_payload_sha256 IS NOT NULL OR document_ref IS NOT NULL "
            "OR confidence_class = 'ASSERTED_BY_HUMAN'",
            name=f"ck_{SIGNALS}_signal_has_evidence",
        ),
        sa.CheckConstraint(
            "length(trim(supporting_text)) > 0",
            name=f"ck_{SIGNALS}_signal_quotes_something",
        ),
        # The two refusals, pinned.
        sa.CheckConstraint(
            "creates_opportunity = 0",
            name=f"ck_{SIGNALS}_signal_never_creates_an_opportunity",
        ),
        sa.CheckConstraint(
            "auto_onboarding_permitted = 0",
            name=f"ck_{SIGNALS}_signal_never_auto_onboards",
        ),
        # A link must point at an opportunity, and only where it belongs.
        sa.CheckConstraint(
            "signal_state <> 'LINKED_TO_OPPORTUNITY' "
            "OR linked_canonical_id IS NOT NULL",
            name=f"ck_{SIGNALS}_linked_signal_names_an_opportunity",
        ),
        sa.CheckConstraint(
            "linked_canonical_id IS NULL OR "
            + _in_list("signal_state", LINK_BEARING_STATES),
            name=f"ck_{SIGNALS}_link_only_in_link_bearing_states",
        ),
    )
    # 176K: signals by program, by source, the open queue, and the links.
    op.create_index(
        f"ix_{SIGNALS}_program", SIGNALS, ["program_key", "signal_type"]
    )
    op.create_index(f"ix_{SIGNALS}_source", SIGNALS, ["source_id", "signal_state"])
    # The open queue is a MINORITY of any healthy population, so this index
    # is partial: it covers only the four open states and stays small while
    # the resolved history it helps us skip grows without bound. Ordered by
    # observed_at because a triage queue a human cannot order is not a queue.
    op.create_index(
        f"ix_{SIGNALS}_open",
        SIGNALS,
        ["observed_at", "review_required"],
        sqlite_where=sa.text(_in_list("signal_state", OPEN_SIGNAL_STATES)),
    )
    op.create_index(f"ix_{SIGNALS}_linked", SIGNALS, ["linked_canonical_id"])
    op.create_index(f"ix_{SIGNALS}_gap", SIGNALS, ["linked_gap_id"])

    # ---------------- recurrence -------------------------------------
    op.create_table(
        RECURRENCES,
        sa.Column("recurrence_id", sa.String(length=64), primary_key=True),
        sa.Column("program_key", sa.Text(), nullable=False),
        sa.Column("program_name", sa.Text(), nullable=True),
        sa.Column("funder_name", sa.Text(), nullable=True),
        sa.Column("identity_basis", sa.String(length=48), nullable=True),
        sa.Column("recurrence_class", sa.String(length=24), nullable=False),
        sa.Column("expectation_state", sa.String(length=32), nullable=False),
        sa.Column("history_count", sa.Integer(), nullable=False),
        sa.Column("mean_interval_days", sa.Float(), nullable=True),
        sa.Column("interval_spread_days", sa.Float(), nullable=True),
        sa.Column("expected_window_start", sa.Date(), nullable=True),
        sa.Column("expected_window_end", sa.Date(), nullable=True),
        sa.Column("title_changed", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("recurrence_class", RECURRENCE_CLASSES),
            name=f"ck_{RECURRENCES}_class",
        ),
        sa.CheckConstraint(
            _in_list("expectation_state", EXPECTATION_STATES),
            name=f"ck_{RECURRENCES}_expectation",
        ),
        sa.CheckConstraint(
            "history_count >= 0", name=f"ck_{RECURRENCES}_history_is_a_count"
        ),
        # The one that makes "insufficient history not forecast" structural.
        sa.CheckConstraint(
            "expectation_state NOT IN ('EXPECTED', 'POSSIBLE') "
            f"OR history_count >= {MINIMUM_CYCLES_FOR_CADENCE}",
            name=f"ck_{RECURRENCES}_expectation_needs_enough_history",
        ),
        # A window only exists where something is expected.
        sa.CheckConstraint(
            "expected_window_end IS NULL OR "
            + _in_list("expectation_state", FORECASTING_STATES),
            name=f"ck_{RECURRENCES}_window_needs_an_expectation",
        ),
        # A cadence needs at least two points to be a cadence at all.
        sa.CheckConstraint(
            "mean_interval_days IS NULL OR history_count >= 2",
            name=f"ck_{RECURRENCES}_cadence_needs_cycles",
        ),
        # Identity from a name collision yields UNKNOWN, never a cadence.
        sa.CheckConstraint(
            _in_list("identity_basis", IDENTITY_BASES)
            + " OR recurrence_class = 'UNKNOWN'",
            name=f"ck_{RECURRENCES}_cadence_needs_a_decisive_identity",
        ),
    )
    # 176K: expected-but-absent is the query the customer is paying for.
    op.create_index(
        f"ix_{RECURRENCES}_absent",
        RECURRENCES,
        ["expectation_state", "expected_window_end"],
    )
    op.create_index(f"ix_{RECURRENCES}_program", RECURRENCES, ["program_key"])

    op.create_table(
        CYCLES,
        sa.Column("recurrence_id", sa.String(length=64), nullable=False),
        sa.Column("cycle_ordinal", sa.Integer(), nullable=False),
        sa.Column("open_date", sa.Date(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("canonical_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint(
            "recurrence_id", "cycle_ordinal", name=f"pk_{CYCLES}"
        ),
        sa.ForeignKeyConstraint(
            ["recurrence_id"],
            [f"{RECURRENCES}.recurrence_id"],
            name=f"fk_{CYCLES}_recurrence",
        ),
        sa.CheckConstraint(
            "cycle_ordinal >= 1", name=f"ck_{CYCLES}_ordinal_is_an_ordinal"
        ),
    )
    # 176K: program recurrence history lookup.
    op.create_index(
        f"ix_{CYCLES}_history", CYCLES, ["recurrence_id", "open_date"]
    )

    # ---------------- award coverage misses ---------------------------
    op.create_table(
        MISSES,
        sa.Column("miss_id", sa.String(length=64), primary_key=True),
        sa.Column("award_ref", sa.Text(), nullable=False),
        sa.Column("award_number", sa.Text(), nullable=True),
        sa.Column("funder_name", sa.Text(), nullable=True),
        sa.Column("program_key", sa.Text(), nullable=True),
        sa.Column("program_name", sa.Text(), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("publisher_key", sa.Text(), nullable=True),
        sa.Column("resolution", sa.String(length=32), nullable=False),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # WHERE we looked. Without this the miss is unfalsifiable.
        sa.Column("searched_source_ids_json", sa.Text(), nullable=False),
        sa.Column("observed_solicitation_count", sa.Integer(), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        # Provenance of the AWARD, not of the miss.
        sa.Column("award_is_demo_fixture", sa.Boolean(), nullable=False),
        sa.Column("counts_toward_real_metrics", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["signal_id"], [f"{SIGNALS}.signal_id"], name=f"fk_{MISSES}_signal"
        ),
        sa.CheckConstraint(
            _in_list("resolution", MISS_RESOLUTIONS), name=f"ck_{MISSES}_resolution"
        ),
        # A miss exists only when nothing was observed.
        sa.CheckConstraint(
            "observed_solicitation_count = 0",
            name=f"ck_{MISSES}_miss_needs_zero_observed_solicitations",
        ),
        # The Gate 176 guard, made structural.
        sa.CheckConstraint(
            "award_is_demo_fixture = 0 OR counts_toward_real_metrics = 0",
            name=f"ck_{MISSES}_demo_award_never_counts_toward_real_metrics",
        ),
        sa.CheckConstraint(
            "length(trim(searched_source_ids_json)) > 0",
            name=f"ck_{MISSES}_miss_says_where_it_looked",
        ),
        sa.CheckConstraint(
            "resolution <> 'UNRESOLVED' OR resolved_by IS NULL",
            name=f"ck_{MISSES}_unresolved_miss_names_no_decider",
        ),
    )
    # 176K: the miss queue, split real from demo.
    op.create_index(
        f"ix_{MISSES}_queue", MISSES, ["resolution", "counts_toward_real_metrics"]
    )
    op.create_index(f"ix_{MISSES}_program", MISSES, ["program_key"])
    op.create_index(f"ix_{MISSES}_signal", MISSES, ["signal_id"])

    # ---------------- coverage gap linkage ----------------------------
    op.create_table(
        GAP_LINKS,
        sa.Column("gap_id", sa.Text(), nullable=False),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("gap_id", "signal_id", name=f"pk_{GAP_LINKS}"),
        # A gap backed by a signal that does not exist is unrepresentable.
        sa.ForeignKeyConstraint(
            ["signal_id"],
            [f"{SIGNALS}.signal_id"],
            name=f"fk_{GAP_LINKS}_signal",
        ),
    )
    # 176K: coverage gap linkage, from either end.
    op.create_index(f"ix_{GAP_LINKS}_gap", GAP_LINKS, ["gap_id"])
    op.create_index(f"ix_{GAP_LINKS}_signal", GAP_LINKS, ["signal_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{GAP_LINKS}_signal", table_name=GAP_LINKS)
    op.drop_index(f"ix_{GAP_LINKS}_gap", table_name=GAP_LINKS)
    op.drop_table(GAP_LINKS)

    op.drop_index(f"ix_{MISSES}_signal", table_name=MISSES)
    op.drop_index(f"ix_{MISSES}_program", table_name=MISSES)
    op.drop_index(f"ix_{MISSES}_queue", table_name=MISSES)
    op.drop_table(MISSES)

    op.drop_index(f"ix_{CYCLES}_history", table_name=CYCLES)
    op.drop_table(CYCLES)

    op.drop_index(f"ix_{RECURRENCES}_program", table_name=RECURRENCES)
    op.drop_index(f"ix_{RECURRENCES}_absent", table_name=RECURRENCES)
    op.drop_table(RECURRENCES)

    op.drop_index(f"ix_{SIGNALS}_gap", table_name=SIGNALS)
    op.drop_index(f"ix_{SIGNALS}_linked", table_name=SIGNALS)
    op.drop_index(f"ix_{SIGNALS}_open", table_name=SIGNALS)
    op.drop_index(f"ix_{SIGNALS}_source", table_name=SIGNALS)
    op.drop_index(f"ix_{SIGNALS}_program", table_name=SIGNALS)
    op.drop_table(SIGNALS)
