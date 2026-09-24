"""Alembic 0060: normalized eligibility, organisation capability, and matches.

Gate 174's survey found the same shape Gate 173 did, one layer deeper: a real
Stage 7 eligibility stack exists - fit dimensions, a confidence service, a
missing-data service, a no-claim-without-evidence guard, an exclusion-evidence
service with real restriction phrases - and none of it can reach a canonical
opportunity. Worse, it consumes the STAGE 6 relevance preview, which Gate 173
established is itself unwired. The whole eligibility-to-relevance chain floats
free of the graph.

So three tables, each justified by an access path 174L names rather than by
JSON being inconvenient.

```text
nf_opportunity_eligibility_requirements  what the funder requires, normalized
nf_organization_capability_profiles      what an applicant has, versioned
nf_tenant_eligibility_matches            the answer, and which versions made it
```

## Why a requirement is a row

"Show me every opportunity with an unmet matching-funds requirement" and
"show me everything that disqualifies us" are the two questions an operator
asks every week. Both are indexed predicates over requirement KIND and
POLARITY, and neither can be served by a JSON blob on the opportunity.

## The constraints that carry the design

`ck_..._exclusion_is_representable` is the point of the polarity column. A
model that stores only who MAY apply represents "tribal governments are not
eligible" as the ABSENCE of a tribal class from a list - byte-identical to
"nobody wrote the list down". The polarity makes those different rows.

`ck_..._keeps_the_original_text` refuses a normalized requirement that has
discarded what the funder actually wrote. Our normalization is a reading; the
text is the fact, and only one of them survives a dispute with a programme
officer.

`ck_..._unknown_is_not_pursuable` and
`ck_..._exclusion_blocks_a_pursuable_result` put the two rules that matter
into the schema. A match that applied a disqualifier and still came out
ELIGIBLE is unrepresentable, not merely discouraged.

`ck_..._names_its_profile_version` exists because an eligibility answer is a
claim about a moment. When a Tribe obtains a UEI, yesterday's
CONDITIONALLY_ELIGIBLE does not become wrong - it becomes an answer about a
superseded profile, and the row says which one.

## Scope

Requirements are GLOBAL - parsed once per opportunity, never per tenant.
Matches are the only per-tenant rows, and they reference the global
normalization rather than repeating it. `ck_..._match_consumed_global`
records that structurally.

Preserves 0056 provisional identity, 0057 identity access path, 0058 source
operations events and 0059 relevance and coverage.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | None = None
depends_on: str | None = None

REQUIREMENTS = "nf_opportunity_eligibility_requirements"
PROFILES = "nf_organization_capability_profiles"
MATCHES = "nf_tenant_eligibility_matches"

REQUIREMENT_KINDS = (
    "APPLICANT_TYPE",
    "LEGAL_ENTITY_TYPE",
    "GEOGRAPHIC",
    "BENEFICIARY",
    "POPULATION",
    "PARTNERSHIP",
    "MATCHING_FUNDS",
    "REGISTRATION",
    "EXPERIENCE",
    "OWNERSHIP_OR_CONTROL",
    "GOVERNMENT_STATUS",
    "RECOGNITION_OR_DESIGNATION",
    "SPECIAL_DESIGNATION",
    "DEADLINE",
    "OTHER_CONDITION",
)

POLARITIES = ("INCLUSION", "EXCLUSION")

ELIGIBILITY_RESULTS = (
    "ELIGIBLE",
    "LIKELY_ELIGIBLE",
    "CONDITIONALLY_ELIGIBLE",
    "INELIGIBLE",
    "UNKNOWN",
    "REVIEW_REQUIRED",
)

#: Results that mean "may pursue". UNKNOWN and REVIEW_REQUIRED are absent.
PURSUABLE = ("ELIGIBLE", "LIKELY_ELIGIBLE", "CONDITIONALLY_ELIGIBLE")

VERIFICATION_STATES = (
    "SELF_DECLARED",
    "DOCUMENT_PROVIDED",
    "VERIFIED_BY_AUTHORITY",
    "UNANSWERED",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def _not_in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} NOT IN ({rendered})"


def upgrade() -> None:
    # ---------------- requirements (GLOBAL) --------------------------
    op.create_table(
        REQUIREMENTS,
        sa.Column("requirement_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("requirement_kind", sa.String(length=48), nullable=False),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("normalized_value_json", sa.Text(), nullable=False),
        # Never dropped. Our normalization is a reading; this is the fact.
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("applies_to_entity_classes_json", sa.Text(), nullable=True),
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        sa.Column("document_ref", sa.Text(), nullable=True),
        sa.Column("section_ref", sa.Text(), nullable=True),
        sa.Column("page_ref", sa.Integer(), nullable=True),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("confidence_class", sa.String(length=32), nullable=True),
        sa.Column("is_structural", sa.Boolean(), nullable=False),
        sa.Column("is_addressable", sa.Boolean(), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("requirement_kind", REQUIREMENT_KINDS),
            name=f"ck_{REQUIREMENTS}_kind",
        ),
        # The 174G column. A disqualifier is a row, not an absence.
        sa.CheckConstraint(
            _in_list("polarity", POLARITIES),
            name=f"ck_{REQUIREMENTS}_exclusion_is_representable",
        ),
        sa.CheckConstraint(
            "length(original_text) > 0",
            name=f"ck_{REQUIREMENTS}_keeps_the_original_text",
        ),
        sa.CheckConstraint(
            "length(normalized_value_json) > 0",
            name=f"ck_{REQUIREMENTS}_has_a_normalized_value",
        ),
        # A requirement is a claim about a source and must point at one.
        sa.CheckConstraint(
            "raw_payload_sha256 IS NOT NULL OR evidence_ids_json IS NOT NULL",
            name=f"ck_{REQUIREMENTS}_is_traceable",
        ),
        sa.CheckConstraint(
            "page_ref IS NULL OR page_ref >= 1",
            name=f"ck_{REQUIREMENTS}_page_is_a_page",
        ),
        sa.CheckConstraint(
            "is_current = 0 OR superseded_at IS NULL",
            name=f"ck_{REQUIREMENTS}_current_is_not_superseded",
        ),
    )
    # 174L: requirements by opportunity, disqualifiers by opportunity.
    op.create_index(
        f"ix_{REQUIREMENTS}_canonical", REQUIREMENTS, ["canonical_id", "is_current"]
    )
    op.create_index(
        f"ix_{REQUIREMENTS}_canonical_polarity",
        REQUIREMENTS,
        ["canonical_id", "polarity", "is_current"],
    )
    op.create_index(
        f"ix_{REQUIREMENTS}_kind", REQUIREMENTS, ["requirement_kind", "is_current"]
    )

    # ---------------- organisation profiles --------------------------
    op.create_table(
        PROFILES,
        sa.Column("profile_id", sa.String(length=64), primary_key=True),
        sa.Column("organization_id", sa.Text(), nullable=False),
        sa.Column("profile_version", sa.String(length=64), nullable=False),
        sa.Column("profile_schema_version", sa.String(length=32), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("fields_json", sa.Text(), nullable=False),
        sa.Column("answered_count", sa.Integer(), nullable=False),
        sa.Column("unanswered_count", sa.Integer(), nullable=False),
        # Gate 177 writes this. Gate 174 cannot, and the CHECK says so.
        sa.Column("authority_verification_performed", sa.Boolean(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("answered_count >= 0", name=f"ck_{PROFILES}_answered"),
        sa.CheckConstraint("unanswered_count >= 0", name=f"ck_{PROFILES}_unanswered"),
        sa.CheckConstraint(
            "length(content_digest) = 64", name=f"ck_{PROFILES}_digest_length"
        ),
        sa.CheckConstraint(
            "is_current = 0 OR superseded_at IS NULL",
            name=f"ck_{PROFILES}_current_is_not_superseded",
        ),
    )
    op.create_index(
        f"ix_{PROFILES}_organization", PROFILES, ["organization_id", "is_current"]
    )
    op.create_index(f"ix_{PROFILES}_version", PROFILES, ["profile_version"])

    # ---------------- matches (the only per-tenant rows) -------------
    op.create_table(
        MATCHES,
        sa.Column("match_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Text(), nullable=False),
        # An answer is a claim about a moment. These say which moment.
        sa.Column("profile_version", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("eligibility_result", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("satisfied_count", sa.Integer(), nullable=False),
        sa.Column("unsatisfied_count", sa.Integer(), nullable=False),
        sa.Column("unknown_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("applied_exclusion_count", sa.Integer(), nullable=False),
        sa.Column("requirement_count", sa.Integer(), nullable=False),
        sa.Column("conditions_to_obtain_json", sa.Text(), nullable=True),
        sa.Column("review_reasons_json", sa.Text(), nullable=True),
        sa.Column("supporting_evidence_ids_json", sa.Text(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("consumed_global_normalization", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("eligibility_result", ELIGIBILITY_RESULTS),
            name=f"ck_{MATCHES}_result",
        ),
        # The load-bearing pair.
        sa.CheckConstraint(
            "applied_exclusion_count = 0 OR "
            + _not_in_list("eligibility_result", PURSUABLE),
            name=f"ck_{MATCHES}_exclusion_blocks_a_pursuable_result",
        ),
        sa.CheckConstraint(
            "eligibility_result <> 'UNKNOWN' OR "
            + _not_in_list("eligibility_result", PURSUABLE),
            name=f"ck_{MATCHES}_unknown_is_not_pursuable",
        ),
        # Every requirement lands somewhere. A match that loses one has an
        # answer nobody can reconstruct.
        sa.CheckConstraint(
            "satisfied_count + unsatisfied_count + unknown_count + review_count "
            "= requirement_count",
            name=f"ck_{MATCHES}_every_requirement_is_accounted_for",
        ),
        sa.CheckConstraint(
            "length(profile_version) > 0",
            name=f"ck_{MATCHES}_names_its_profile_version",
        ),
        sa.CheckConstraint(
            "eligibility_result <> 'CONDITIONALLY_ELIGIBLE' "
            "OR conditions_to_obtain_json IS NOT NULL",
            name=f"ck_{MATCHES}_conditional_names_its_condition",
        ),
        # 174K, structurally.
        sa.CheckConstraint(
            "consumed_global_normalization = 1",
            name=f"ck_{MATCHES}_match_consumed_global",
        ),
        sa.CheckConstraint(
            "is_current = 0 OR superseded_at IS NULL",
            name=f"ck_{MATCHES}_current_is_not_superseded",
        ),
    )
    # 174L: result by tenant+opportunity, review-required matches, and the
    # per-opportunity fan-out.
    op.create_index(
        f"ix_{MATCHES}_tenant_canonical",
        MATCHES,
        ["tenant_id", "canonical_id", "is_current"],
    )
    op.create_index(
        f"ix_{MATCHES}_tenant_result", MATCHES, ["tenant_id", "eligibility_result"]
    )
    op.create_index(f"ix_{MATCHES}_review", MATCHES, ["review_required", "is_current"])
    op.create_index(f"ix_{MATCHES}_canonical", MATCHES, ["canonical_id", "is_current"])


def downgrade() -> None:
    op.drop_index(f"ix_{MATCHES}_canonical", table_name=MATCHES)
    op.drop_index(f"ix_{MATCHES}_review", table_name=MATCHES)
    op.drop_index(f"ix_{MATCHES}_tenant_result", table_name=MATCHES)
    op.drop_index(f"ix_{MATCHES}_tenant_canonical", table_name=MATCHES)
    op.drop_table(MATCHES)

    op.drop_index(f"ix_{PROFILES}_version", table_name=PROFILES)
    op.drop_index(f"ix_{PROFILES}_organization", table_name=PROFILES)
    op.drop_table(PROFILES)

    op.drop_index(f"ix_{REQUIREMENTS}_kind", table_name=REQUIREMENTS)
    op.drop_index(f"ix_{REQUIREMENTS}_canonical_polarity", table_name=REQUIREMENTS)
    op.drop_index(f"ix_{REQUIREMENTS}_canonical", table_name=REQUIREMENTS)
    op.drop_table(REQUIREMENTS)
