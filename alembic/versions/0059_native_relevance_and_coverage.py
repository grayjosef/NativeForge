"""Alembic 0059: durable Native relevance, its evidence, and the coverage universe.

Gate 173's survey found a real Native relevance stack already in the tree -
eight labels, a deterministic evaluator, confidence bands, review triggers and
two guards - and established the fact that decided this gate:

```text
none of it can reach a canonical opportunity. Every relevance module in the
repository sees fixture dictionaries and nothing else.
```

So the schema here is not a second relevance engine. It is the binding that
lets relevance be a property OF an opportunity in the Gate 167 graph, and it
is four tables because 173P names four access paths that JSON in a column
cannot serve.

## Why each table exists

```text
nf_opportunity_relevance_assessments   one current answer per opportunity
nf_opportunity_relevance_evidence      the rows that answer has to cite
nf_source_coverage_universe            publishers, and whether we watch them
nf_source_coverage_gap_signals         traces that funding existed elsewhere
```

An assessment is queried BY CLASS ("show me everything NATIVE_ELIGIBLE"), by
review state ("what needs a human"), and by unknown ("what have we not
settled"). Those are three indexed predicates over a hundred thousand rows,
and they are the reason this is a table rather than a JSON blob hanging off
the canonical row.

## What the constraints are actually for

`ck_..._decisive_needs_evidence` is the one that matters. A decisive
classification with `evidence_count = 0` is unrepresentable - not discouraged,
not validated in a service that someone can bypass, but refused by the
database. An intelligence product's worst output is a confident sentence with
nothing behind it, and this is the last place that can be stopped.

`ck_..._uncertain_asks_for_review` is its twin: UNCERTAIN is a request for a
human, so a row that is uncertain and asks for nobody is a contradiction.

`ck_..._pending_review_has_no_source` keeps the authorization boundary intact.
A publisher in DISCOVERED_PENDING_REVIEW is one nobody has approved, so it
cannot already have a source collecting from it. Gates 162-171 made source
authorization a human decision; a coverage layer that could quietly attach a
source to a newly noticed publisher would have undone all of it.

## Scope

Assessments and coverage are GLOBAL, deliberately. Native relevance is a
property of the opportunity, not of who is looking at it, and a per-tenant
copy would be the same answer stored a thousand times and eventually
disagreeing with itself. Tenant matching consumes these rows; it does not
duplicate them, and `ck_..._is_global` makes that structural.

Preserves 0056 provisional identity, 0057 identity access path and 0058
source operations events.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | None = None
depends_on: str | None = None

ASSESSMENTS = "nf_opportunity_relevance_assessments"
EVIDENCE = "nf_opportunity_relevance_evidence"
UNIVERSE = "nf_source_coverage_universe"
GAPS = "nf_source_coverage_gap_signals"

RELEVANCE_CLASSES = (
    "NATIVE_SPECIFIC",
    "NATIVE_PRIORITY",
    "NATIVE_ELIGIBLE",
    "BROADLY_ELIGIBLE_NATIVE_RELEVANT",
    "NATIVE_BENEFICIARY_RELEVANT",
    "INDIRECTLY_RELEVANT",
    "UNCERTAIN",
    "NOT_RELEVANT",
)

CANDIDATE_STATES = ("CANDIDATE", "NOT_CANDIDATE", "UNKNOWN")

CONFIDENCE_LEVELS = ("HIGH", "MODERATE", "LOW", "NONE")

EVIDENCE_TYPES = (
    "APPLICANT_ELIGIBILITY",
    "BENEFICIARY_POPULATION",
    "GEOGRAPHIC_RELEVANCE",
    "PROGRAM_PURPOSE",
    "AGENCY_CONTEXT",
    "PROGRAM_HISTORY",
    "PRIOR_NATIVE_AWARDS",
    "STATUTORY_LANGUAGE",
    "SOURCE_CONTEXT",
    "SECTOR_ALIGNMENT",
    "DOCUMENT_REFERENCE",
    "OTHER_EVIDENCE",
)

CONFIDENCE_CLASSES = (
    "OBSERVED",
    "DERIVED",
    "INFERRED",
    "ASSERTED_BY_HUMAN",
    "UNKNOWN_CONFIDENCE",
)

AMBIGUITY_CLASSES = (
    "NO_AMBIGUITY",
    "ENTITY_CLASS_AMBIGUOUS",
    "SCOPE_AMBIGUOUS",
    "TEMPORAL_AMBIGUOUS",
    "CONTEXT_AMBIGUOUS",
    "CONFLICTING_SOURCES",
)

SOURCE_FAMILIES = (
    "FEDERAL",
    "STATE",
    "LOCAL",
    "TRIBAL",
    "FOUNDATION",
    "CORPORATE",
    "UNIVERSITY",
    "NONPROFIT",
    "PRIVATE",
    "REGIONAL_AUTHORITY",
    "UTILITY",
    "SPECIAL_PURPOSE",
    "OTHER_FAMILY",
)

COVERAGE_STATES = (
    "KNOWN_MONITORED",
    "KNOWN_NOT_MONITORED",
    "DISCOVERED_PENDING_REVIEW",
    "PARTIALLY_COVERED",
    "BLOCKED",
    "RETIRED",
    "UNKNOWN_COVERAGE",
)

GAP_SIGNAL_TYPES = (
    "AWARD_WITHOUT_SOLICITATION",
    "AMENDMENT_WITHOUT_ORIGINAL",
    "PROGRAM_REFERENCED_SOURCE_UNMONITORED",
    "DEADLINE_WITHOUT_OPPORTUNITY",
    "GRANTEE_ANNOUNCEMENT_UNSEEN_PROGRAM",
    "BUDGET_REFERENCES_FUTURE_FUNDING",
    "UNKNOWN_PUBLISHER_REFERENCED",
    "RECURRING_PROGRAM_ABSENT",
)

GAP_STATES = ("open", "resolved", "dismissed")

#: Classes that assert something about the world. UNCERTAIN is excluded
#: because "we do not know" is the one answer that needs no evidence.
DECISIVE_CLASSES = tuple(c for c in RELEVANCE_CLASSES if c != "UNCERTAIN")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # ---------------- assessments -----------------------------------
    op.create_table(
        ASSESSMENTS,
        sa.Column("assessment_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("ontology_version", sa.String(length=32), nullable=False),
        sa.Column("relevance_class", sa.String(length=48), nullable=False),
        sa.Column("candidate_state", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("review_reasons_json", sa.Text(), nullable=True),
        sa.Column("reasons_json", sa.Text(), nullable=True),
        sa.Column("entity_classes_json", sa.Text(), nullable=True),
        sa.Column("sectors_json", sa.Text(), nullable=True),
        # Denormalised so "is this claim backed" is a column predicate the
        # CHECK below can act on, rather than a join nobody runs.
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("ranking_score", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("relevance_class", RELEVANCE_CLASSES),
            name=f"ck_{ASSESSMENTS}_class",
        ),
        sa.CheckConstraint(
            _in_list("candidate_state", CANDIDATE_STATES),
            name=f"ck_{ASSESSMENTS}_candidate_state",
        ),
        sa.CheckConstraint(
            _in_list("confidence", CONFIDENCE_LEVELS),
            name=f"ck_{ASSESSMENTS}_confidence",
        ),
        sa.CheckConstraint(
            "evidence_count >= 0", name=f"ck_{ASSESSMENTS}_evidence_count"
        ),
        # The load-bearing one. A decisive claim with nothing behind it is
        # unrepresentable, not merely discouraged.
        sa.CheckConstraint(
            f"relevance_class NOT IN "
            f"({', '.join(repr(c) for c in DECISIVE_CLASSES)}) "
            f"OR evidence_count > 0",
            name=f"ck_{ASSESSMENTS}_decisive_needs_evidence",
        ),
        # UNCERTAIN is a request for a human. One that asks for nobody is a
        # contradiction.
        sa.CheckConstraint(
            "relevance_class <> 'UNCERTAIN' OR review_required = true",
            name=f"ck_{ASSESSMENTS}_uncertain_asks_review",
        ),
        # 173H: global relevance never carries a tenant.
        sa.CheckConstraint("scope = 'GLOBAL'", name=f"ck_{ASSESSMENTS}_is_global"),
        sa.CheckConstraint(
            "is_current = false OR superseded_at IS NULL",
            name=f"ck_{ASSESSMENTS}_current_not_superseded",
        ),
    )
    # 173P: by class, by review, by unknown, and latest-per-opportunity.
    op.create_index(
        f"ix_{ASSESSMENTS}_class", ASSESSMENTS, ["relevance_class", "is_current"]
    )
    op.create_index(
        f"ix_{ASSESSMENTS}_review", ASSESSMENTS, ["review_required", "is_current"]
    )
    op.create_index(
        f"ix_{ASSESSMENTS}_canonical_current",
        ASSESSMENTS,
        ["canonical_id", "is_current"],
    )
    op.create_index(
        f"ix_{ASSESSMENTS}_canonical_computed",
        ASSESSMENTS,
        ["canonical_id", "computed_at"],
    )

    # ---------------- evidence ---------------------------------------
    op.create_table(
        EVIDENCE,
        sa.Column("evidence_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("evidence_type", sa.String(length=48), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("observation_id", sa.Text(), nullable=True),
        sa.Column("version_id", sa.Text(), nullable=True),
        sa.Column("field_name", sa.Text(), nullable=True),
        sa.Column("section_ref", sa.Text(), nullable=True),
        sa.Column("page_ref", sa.Integer(), nullable=True),
        sa.Column("document_ref", sa.Text(), nullable=True),
        sa.Column("evidence_value_json", sa.Text(), nullable=False),
        sa.Column("confidence_class", sa.String(length=32), nullable=False),
        sa.Column("ambiguity_class", sa.String(length=32), nullable=False),
        sa.Column("supports_classes_json", sa.Text(), nullable=True),
        sa.Column("ontology_version", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("evidence_type", EVIDENCE_TYPES), name=f"ck_{EVIDENCE}_type"
        ),
        sa.CheckConstraint(
            _in_list("confidence_class", CONFIDENCE_CLASSES),
            name=f"ck_{EVIDENCE}_confidence",
        ),
        sa.CheckConstraint(
            _in_list("ambiguity_class", AMBIGUITY_CLASSES),
            name=f"ck_{EVIDENCE}_ambiguity",
        ),
        # Evidence must be traceable to bytes. A human assertion is allowed to
        # have no payload because a person is the origin; nothing else is.
        sa.CheckConstraint(
            "raw_payload_sha256 IS NOT NULL OR confidence_class = 'ASSERTED_BY_HUMAN'",
            name=f"ck_{EVIDENCE}_is_traceable_to_a_payload",
        ),
        sa.CheckConstraint(
            "page_ref IS NULL OR page_ref >= 1", name=f"ck_{EVIDENCE}_page_is_a_page"
        ),
        sa.CheckConstraint(
            "length(evidence_value_json) > 0", name=f"ck_{EVIDENCE}_value_is_not_empty"
        ),
    )
    op.create_index(f"ix_{EVIDENCE}_canonical", EVIDENCE, ["canonical_id"])
    op.create_index(
        f"ix_{EVIDENCE}_canonical_type", EVIDENCE, ["canonical_id", "evidence_type"]
    )
    op.create_index(f"ix_{EVIDENCE}_payload", EVIDENCE, ["raw_payload_sha256"])

    # ---------------- coverage universe -------------------------------
    op.create_table(
        UNIVERSE,
        sa.Column("publisher_key", sa.Text(), primary_key=True),
        sa.Column("family", sa.String(length=32), nullable=False),
        sa.Column("publisher_name", sa.Text(), nullable=True),
        sa.Column("coverage_state", sa.String(length=32), nullable=False),
        sa.Column("source_ids_json", sa.Text(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, default=0),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("why_json", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("family", SOURCE_FAMILIES), name=f"ck_{UNIVERSE}_family"
        ),
        sa.CheckConstraint(
            _in_list("coverage_state", COVERAGE_STATES), name=f"ck_{UNIVERSE}_state"
        ),
        sa.CheckConstraint("source_count >= 0", name=f"ck_{UNIVERSE}_source_count"),
        # A publisher we claim to collect from has to name a source doing it.
        sa.CheckConstraint(
            "coverage_state NOT IN ('KNOWN_MONITORED', 'PARTIALLY_COVERED') "
            "OR source_count > 0",
            name=f"ck_{UNIVERSE}_monitored_names_a_source",
        ),
        # The authorization boundary, in the schema. A publisher awaiting
        # review cannot already have a source attached to it.
        sa.CheckConstraint(
            "coverage_state <> 'DISCOVERED_PENDING_REVIEW' OR source_count = 0",
            name=f"ck_{UNIVERSE}_pending_review_has_no_source",
        ),
        # And a decision has to have a decider.
        sa.CheckConstraint(
            "coverage_state NOT IN "
            "('KNOWN_MONITORED', 'KNOWN_NOT_MONITORED', 'PARTIALLY_COVERED', "
            "'BLOCKED', 'RETIRED') "
            "OR decided_by IS NOT NULL",
            name=f"ck_{UNIVERSE}_decision_names_its_decider",
        ),
    )
    op.create_index(f"ix_{UNIVERSE}_state", UNIVERSE, ["coverage_state"])
    op.create_index(
        f"ix_{UNIVERSE}_family_state", UNIVERSE, ["family", "coverage_state"]
    )

    # ---------------- gap signals --------------------------------------
    op.create_table(
        GAPS,
        sa.Column("gap_id", sa.String(length=64), primary_key=True),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("family", sa.String(length=32), nullable=True),
        sa.Column("publisher_key", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("canonical_id", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.Text(), nullable=True),
        sa.Column("evidence_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("gap_state", sa.String(length=16), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_count", sa.Integer(), nullable=False, default=1),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("signal_type", GAP_SIGNAL_TYPES), name=f"ck_{GAPS}_type"
        ),
        sa.CheckConstraint(_in_list("gap_state", GAP_STATES), name=f"ck_{GAPS}_state"),
        sa.CheckConstraint("detection_count >= 1", name=f"ck_{GAPS}_detection_count"),
        sa.CheckConstraint(
            "latest_detected_at >= first_detected_at", name=f"ck_{GAPS}_ordering"
        ),
        sa.CheckConstraint(
            "length(recommended_action) > 0", name=f"ck_{GAPS}_action_is_not_empty"
        ),
        # A claim that we missed funding needs something behind it.
        sa.CheckConstraint(
            "evidence_ref IS NOT NULL OR canonical_id IS NOT NULL",
            name=f"ck_{GAPS}_has_an_evidence_reference",
        ),
        sa.CheckConstraint(
            "gap_state <> 'resolved' OR resolved_at IS NOT NULL",
            name=f"ck_{GAPS}_resolved_has_a_time",
        ),
    )
    op.create_index(f"ix_{GAPS}_source", GAPS, ["source_id"])
    op.create_index(f"ix_{GAPS}_open", GAPS, ["gap_state", "signal_type"])
    op.create_index(f"ix_{GAPS}_publisher", GAPS, ["publisher_key"])


def downgrade() -> None:
    op.drop_index(f"ix_{GAPS}_publisher", table_name=GAPS)
    op.drop_index(f"ix_{GAPS}_open", table_name=GAPS)
    op.drop_index(f"ix_{GAPS}_source", table_name=GAPS)
    op.drop_table(GAPS)

    op.drop_index(f"ix_{UNIVERSE}_family_state", table_name=UNIVERSE)
    op.drop_index(f"ix_{UNIVERSE}_state", table_name=UNIVERSE)
    op.drop_table(UNIVERSE)

    op.drop_index(f"ix_{EVIDENCE}_payload", table_name=EVIDENCE)
    op.drop_index(f"ix_{EVIDENCE}_canonical_type", table_name=EVIDENCE)
    op.drop_index(f"ix_{EVIDENCE}_canonical", table_name=EVIDENCE)
    op.drop_table(EVIDENCE)

    op.drop_index(f"ix_{ASSESSMENTS}_canonical_computed", table_name=ASSESSMENTS)
    op.drop_index(f"ix_{ASSESSMENTS}_canonical_current", table_name=ASSESSMENTS)
    op.drop_index(f"ix_{ASSESSMENTS}_review", table_name=ASSESSMENTS)
    op.drop_index(f"ix_{ASSESSMENTS}_class", table_name=ASSESSMENTS)
    op.drop_table(ASSESSMENTS)
