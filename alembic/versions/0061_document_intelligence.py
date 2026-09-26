"""Alembic 0061: documents as versioned evidence, their facts, and conflicts.

Gate 175's survey established the gap in one measurement:

```text
no_table_binds_a_document_to_a_canonical_opportunity = true
```

`nf_award_documents` exists and holds 876 archived rows of `financial_report`
and `award_letter` hanging off `awarded_grant_id` and `award_requirement_id`.
Those are POST-AWARD compliance artifacts. A NOFO, an appendix and an FAQ are
PRE-AWARD evidence about an opportunity nobody has won, and filing a funder's
eligibility language against a grant that does not exist would conflate two
lifecycle stages permanently.

Three tables:

```text
nf_opportunity_documents          versioned documents, keyed by content
nf_opportunity_document_facts     what each document says, and where
nf_opportunity_document_conflicts what two documents disagree about
```

## Identity is the content hash

A document id derives from `(canonical_id, content_sha256)`. The same URL
serving changed bytes is a NEW row; the same bytes at a second URL is the SAME
row with another location. Keying on the URL would make an agency's mirror
look like an amendment and make a silent republication invisible.

## The constraint that matters most

`ck_..._absence_is_meaningful_only_when_parsed`. A document whose parser does
not support its media type must never be recorded as though an absent fact
meant the funder imposed none. `UNSUPPORTED` and `PARTIAL` can never carry
that flag, so "we could not read this" cannot decay into "there is nothing to
read".

`ck_..._fact_needs_a_document` and `ck_..._fact_quotes_its_source` make an
uncitable fact unrepresentable: a value with no document and no quoted text
cannot be shown to anybody who disputes it.

`ck_..._winner_needs_a_selecting_rule` is the anti-silent-resolution rule. A
conflict may only name a winner under a rule that selects one, and
`FAQ_CLARIFIES` is deliberately not such a rule - a clarification adds meaning
without erasing the original.

`ck_..._no_self_supersession` catches the degenerate cycle directly; longer
cycles are caught by the chain builder, which the phase exercises.

Preserves 0056 through 0060.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | None = None
depends_on: str | None = None

DOCUMENTS = "nf_opportunity_documents"
FACTS = "nf_opportunity_document_facts"
CONFLICTS = "nf_opportunity_document_conflicts"

DOCUMENT_STATES = (
    "NOT_FETCHED",
    "FETCHED",
    "PARSE_PENDING",
    "PARSED",
    "PARTIAL",
    "UNSUPPORTED",
    "FAILED",
    "REVIEW_REQUIRED",
)

#: The only state in which an absent fact means the funder said nothing.
ABSENCE_IS_MEANINGFUL = ("PARSED",)

FACT_KINDS = (
    "ELIGIBILITY",
    "DEADLINE",
    "FUNDING_AMOUNT",
    "AWARD_FLOOR",
    "AWARD_CEILING",
    "ESTIMATED_AWARDS",
    "COST_SHARE",
    "PERIOD_OF_PERFORMANCE",
    "GEOGRAPHY",
    "CONTACT",
    "SUBMISSION_METHOD",
    "REQUIRED_DOCUMENTS",
    "EVALUATION_CRITERIA",
    "PROGRAM_PURPOSE",
    "NATIVE_RELEVANCE",
    "SPECIAL_REQUIREMENT",
)

EXTRACTION_METHODS = (
    "EXTRACTED_BY_RULE",
    "EXTRACTED_BY_PARSER",
    "ASSERTED_BY_HUMAN",
)

CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")

RESOLUTION_RULES = (
    "AMENDMENT_SUPERSEDES",
    "NOTICE_OUTRANKS_SUMMARY",
    "FAQ_CLARIFIES",
    "UNRESOLVED",
)

#: Rules that may name a winner. FAQ_CLARIFIES is absent on purpose.
SELECTS_A_WINNER = ("AMENDMENT_SUPERSEDES", "NOTICE_OUTRANKS_SUMMARY")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def _not_in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} NOT IN ({rendered})"


def upgrade() -> None:
    # ---------------- documents --------------------------------------
    op.create_table(
        DOCUMENTS,
        sa.Column("document_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(length=48), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("location_ref", sa.Text(), nullable=True),
        # Identity. Not the URL.
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("media_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("document_state", sa.String(length=32), nullable=False),
        sa.Column("extraction_method", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_ordinal", sa.Integer(), nullable=False),
        sa.Column("supersedes_document_id", sa.String(length=64), nullable=True),
        sa.Column("amended_by_document_id", sa.String(length=64), nullable=True),
        sa.Column("clarifies_document_id", sa.String(length=64), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("known_gaps_json", sa.Text(), nullable=True),
        sa.Column("absence_is_meaningful", sa.Boolean(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("document_state", DOCUMENT_STATES),
            name=f"ck_{DOCUMENTS}_state",
        ),
        sa.CheckConstraint(
            "version_ordinal >= 1", name=f"ck_{DOCUMENTS}_version_is_a_version"
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count >= 1",
            name=f"ck_{DOCUMENTS}_page_count_is_pages",
        ),
        # The load-bearing one. "We could not read this" must never decay
        # into "there is nothing to read".
        sa.CheckConstraint(
            "absence_is_meaningful = false OR "
            + _in_list("document_state", ABSENCE_IS_MEANINGFUL),
            name=f"ck_{DOCUMENTS}_absence_meaningful_only_when_parsed",
        ),
        # A fetched document has bytes.
        sa.CheckConstraint(
            "document_state = 'NOT_FETCHED' OR content_sha256 IS NOT NULL",
            name=f"ck_{DOCUMENTS}_fetched_document_has_content",
        ),
        sa.CheckConstraint(
            "document_state <> 'PARSED' OR extraction_method IS NOT NULL",
            name=f"ck_{DOCUMENTS}_parsed_document_named_its_parser",
        ),
        sa.CheckConstraint(
            "supersedes_document_id IS NULL OR supersedes_document_id <> document_id",
            name=f"ck_{DOCUMENTS}_no_self_supersession",
        ),
        sa.CheckConstraint(
            "clarifies_document_id IS NULL OR clarifies_document_id <> document_id",
            name=f"ck_{DOCUMENTS}_no_self_clarification",
        ),
    )
    # 175L: documents by opportunity, latest versions, the amendment chain.
    op.create_index(
        f"ix_{DOCUMENTS}_canonical", DOCUMENTS, ["canonical_id", "is_latest"]
    )
    op.create_index(
        f"ix_{DOCUMENTS}_canonical_type",
        DOCUMENTS,
        ["canonical_id", "document_type"],
    )
    op.create_index(f"ix_{DOCUMENTS}_supersedes", DOCUMENTS, ["supersedes_document_id"])
    op.create_index(f"ix_{DOCUMENTS}_content", DOCUMENTS, ["content_sha256"])

    # ---------------- facts ------------------------------------------
    op.create_table(
        FACTS,
        sa.Column("fact_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=48), nullable=True),
        sa.Column("fact_kind", sa.String(length=48), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        # The funder's own words. A value without them cannot be defended.
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("section_ref", sa.Text(), nullable=True),
        sa.Column("page_ref", sa.Integer(), nullable=True),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_in_list("fact_kind", FACT_KINDS), name=f"ck_{FACTS}_kind"),
        sa.CheckConstraint(
            _in_list("extraction_method", EXTRACTION_METHODS),
            name=f"ck_{FACTS}_method",
        ),
        sa.CheckConstraint(
            _in_list("confidence", CONFIDENCE_LEVELS), name=f"ck_{FACTS}_confidence"
        ),
        sa.CheckConstraint(
            "length(document_id) > 0", name=f"ck_{FACTS}_fact_needs_a_document"
        ),
        sa.CheckConstraint(
            "length(source_text) > 0", name=f"ck_{FACTS}_fact_quotes_its_source"
        ),
        sa.CheckConstraint(
            "length(value_json) > 0", name=f"ck_{FACTS}_fact_has_a_value"
        ),
        sa.CheckConstraint(
            "page_ref IS NULL OR page_ref >= 1", name=f"ck_{FACTS}_page_is_a_page"
        ),
    )
    # 175L: facts by document, facts by opportunity, citations by kind.
    op.create_index(f"ix_{FACTS}_document", FACTS, ["document_id"])
    op.create_index(f"ix_{FACTS}_canonical", FACTS, ["canonical_id"])
    op.create_index(f"ix_{FACTS}_canonical_kind", FACTS, ["canonical_id", "fact_kind"])

    # ---------------- conflicts ---------------------------------------
    op.create_table(
        CONFLICTS,
        sa.Column("conflict_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("fact_kind", sa.String(length=48), nullable=False),
        sa.Column("fact_id_a", sa.String(length=64), nullable=False),
        sa.Column("fact_id_b", sa.String(length=64), nullable=False),
        # Both, always. A conflict that kept one value is not a conflict
        # record, it is a silent resolution with extra steps.
        sa.Column("value_a_json", sa.Text(), nullable=False),
        sa.Column("value_b_json", sa.Text(), nullable=False),
        sa.Column("resolution_rule", sa.String(length=48), nullable=False),
        sa.Column("winning_fact_id", sa.String(length=64), nullable=True),
        sa.Column("why", sa.Text(), nullable=False),
        sa.Column("is_material", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("resolution_rule", RESOLUTION_RULES),
            name=f"ck_{CONFLICTS}_rule",
        ),
        sa.CheckConstraint(
            "fact_id_a <> fact_id_b", name=f"ck_{CONFLICTS}_two_distinct_facts"
        ),
        # The anti-silent-resolution rule.
        sa.CheckConstraint(
            "winning_fact_id IS NULL OR "
            + _in_list("resolution_rule", SELECTS_A_WINNER),
            name=f"ck_{CONFLICTS}_winner_needs_a_sel_rule",
        ),
        sa.CheckConstraint(
            _not_in_list("resolution_rule", SELECTS_A_WINNER)
            + " OR winning_fact_id IS NOT NULL",
            name=f"ck_{CONFLICTS}_sel_rule_names_a_winner",
        ),
        # A clarification never overwrites.
        sa.CheckConstraint(
            "resolution_rule <> 'FAQ_CLARIFIES' OR winning_fact_id IS NULL",
            name=f"ck_{CONFLICTS}_clarif_does_not_overwrite",
        ),
        sa.CheckConstraint(
            "resolution_rule <> 'UNRESOLVED' OR review_required = true",
            name=f"ck_{CONFLICTS}_unresolved_asks_for_review",
        ),
        sa.CheckConstraint("length(why) > 0", name=f"ck_{CONFLICTS}_says_why"),
    )
    op.create_index(f"ix_{CONFLICTS}_canonical", CONFLICTS, ["canonical_id"])
    op.create_index(
        f"ix_{CONFLICTS}_review", CONFLICTS, ["review_required", "is_material"]
    )


def downgrade() -> None:
    op.drop_index(f"ix_{CONFLICTS}_review", table_name=CONFLICTS)
    op.drop_index(f"ix_{CONFLICTS}_canonical", table_name=CONFLICTS)
    op.drop_table(CONFLICTS)

    op.drop_index(f"ix_{FACTS}_canonical_kind", table_name=FACTS)
    op.drop_index(f"ix_{FACTS}_canonical", table_name=FACTS)
    op.drop_index(f"ix_{FACTS}_document", table_name=FACTS)
    op.drop_table(FACTS)

    op.drop_index(f"ix_{DOCUMENTS}_content", table_name=DOCUMENTS)
    op.drop_index(f"ix_{DOCUMENTS}_supersedes", table_name=DOCUMENTS)
    op.drop_index(f"ix_{DOCUMENTS}_canonical_type", table_name=DOCUMENTS)
    op.drop_index(f"ix_{DOCUMENTS}_canonical", table_name=DOCUMENTS)
    op.drop_table(DOCUMENTS)
