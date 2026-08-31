"""Alembic 0033: nf_award_requirements (Gate 125B).

Where an award's obligations live. The other half of awarded tracking.

## What was missing

Gate 108 built the requirement model, the calendar and the proof audit — three
services, roughly 1,150 lines. Gate 124 gave awards a table and deliberately
left this half, because a requirement recurs: quarterly financial reports,
annual performance reports, a closeout package. One award produces dozens of
rows with their own due dates and their own proof trail.

## Two identifiers, and neither is redundant

```text
organization_id    the RLS predicate's left side. The anchor.
awarded_grant_id   a row relationship. Not an authority.
```

Carrying only `awarded_grant_id` would be the substitution Gates 110-113 exist
to refuse: the policy is `organization_id = current_setting(...)::uuid`, so a
table without that column cannot be scoped at all, and reaching the organization
through a join would make every policy here depend on a policy there.

Carrying only `organization_id` would lose the award, and a compliance calendar
is a list of requirements *for an award*.

`ON DELETE CASCADE` is safe because nothing deletes an award. Archiving sets
`archived_at` and the row stays.

## A projection is not an obligation, and neither is a guess

Gate 108 derives this from provenance, in one line:

```python
is_active_obligation = extraction in ACTIVE_CAPABLE_EXTRACTION_STATUSES
```

`requirement_source` is that provenance. `active_obligation` and
`projected_burden` are the derivation, persisted so a query can filter on them,
and `ck_nf_award_requirements_not_both_obligation_and_projection` refuses the
contradiction the two columns would otherwise permit. Nothing accepts either as
input.

```text
requirement_source                    active  projected
human_entered / evidence_extracted    true    false
projected_from_nofo                   false   true
unsupported_document_type             false   false
unknown / needs_human_review          false   false
```

## An estimate is not a date

`DUE_DATE_STATUSES` has six values and `DATE_CALCULABLE_STATUSES` has two —
`verified` and `calculated`. `estimated` is deliberately outside it. A date you
cannot count down to must not be counted down, and a compliance calendar that
treats an estimate as a deadline is worse than one with a gap in it.

## proof_document_ref points at nothing

There is no document store. `award_document_store_service` does not exist and
Gate 108's doc 598 lists building one as a later action. The column holds a
reference so a requirement can record which document was filed, and the
reference resolves to nothing today. Document storage stays false, and a
separate flag says so rather than the presence of this column implying it.

## No rows are inserted

A production write needs `customer_auth_live` and a verified operational
binding, and Gates 115-124 measured both as false.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_award_requirements"

# Gate 108 vocabularies, restated because a CHECK constraint cannot import
# Python. A test asserts each matches the service's frozenset exactly, so the
# two cannot drift.
REQUIREMENT_TYPES = (
    "financial_report",
    "narrative_report",
    "performance_measure",
    "audit",
    "closeout",
    "match_documentation",
    "drawdown",
    "reimbursement",
    "budget_revision",
    "subrecipient_report",
    "vendor_documentation",
    "board_or_council_resolution",
    "document_retention",
    "other",
    "unknown",
)

REQUIREMENT_STATUSES = (
    "not_started",
    "in_progress",
    "submitted",
    "accepted",
    "rejected",
    "overdue",
    "waived",
    "not_applicable",
    "needs_human_review",
    "unknown",
)

# Where the requirement came from. Gate 108 calls this extraction_status and
# derives the whole projected-versus-active boundary from it.
REQUIREMENT_SOURCES = (
    "human_entered",
    "evidence_extracted",
    "projected_from_nofo",
    "unsupported_document_type",
    "needs_human_review",
    "unknown",
)

# The two that can carry an obligation. Everything else cannot.
ACTIVE_CAPABLE_SOURCES = ("human_entered", "evidence_extracted")

DUE_DATE_STATUSES = (
    "verified",
    "calculated",
    "estimated",
    "unknown",
    "unsupported",
    "needs_human_review",
)

# The two a calendar may count down to. `estimated` is deliberately absent.
DATE_CALCULABLE_STATUSES = ("verified", "calculated")

PROOF_STATUSES = (
    "not_submitted",
    "proof_missing",
    "proof_attached",
    "proof_accepted",
    "proof_rejected",
    "unknown",
)

SUBMISSION_STATUSES = (
    "not_submitted",
    "submitted",
    "accepted",
    "rejected",
    "waived",
    "needs_human_review",
    "unknown",
)

RECURRENCES = (
    "one_time",
    "monthly",
    "quarterly",
    "semi_annual",
    "annual",
    "on_request",
    "unknown",
)

# Gate 103's status vocabulary, reused: a fact somebody guessed and one somebody
# confirmed are different objects.
FACT_STATUSES = (
    "verified",
    "tenant_supplied",
    "demo_fixture",
    "unknown",
    "needs_human_review",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        # The RLS anchor. Everything else is a relationship, a fact or an audit
        # trail.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # A row relationship, never an authority. A requirement without an award
        # is a requirement of nothing, so this is NOT NULL - but it does not
        # scope the row and no policy reads it.
        sa.Column(
            "awarded_grant_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_awarded_grants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # -- what is required -------------------------------------------------
        sa.Column("requirement_type", sa.String(length=48), nullable=False),
        sa.Column("requirement_title", sa.Text(), nullable=False),
        sa.Column("requirement_description", sa.Text(), nullable=True),
        sa.Column("requirement_status", sa.String(length=32), nullable=False),
        # -- where it came from, which decides whether it obliges anybody -----
        sa.Column("requirement_source", sa.String(length=32), nullable=False),
        sa.Column("requirement_source_ref", sa.Text(), nullable=True),
        # -- when ------------------------------------------------------------
        sa.Column("requirement_due_date", sa.Date(), nullable=True),
        sa.Column("due_date_status", sa.String(length=32), nullable=False),
        sa.Column("recurrence_rule", sa.String(length=32), nullable=False),
        # -- who -------------------------------------------------------------
        sa.Column(
            "owner_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # -- what proves it was done ------------------------------------------
        sa.Column(
            "proof_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("proof_status", sa.String(length=32), nullable=False),
        # A reference, not a document. There is no document store; the flag that
        # says so lives in readiness, not in the presence of this column.
        sa.Column("proof_document_ref", sa.Text(), nullable=True),
        sa.Column("submission_status", sa.String(length=32), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        # -- the derivation, persisted so a query can filter on it ------------
        sa.Column(
            "active_obligation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "projected_burden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "unsupported_requirement",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # -- lifecycle and audit ----------------------------------------------
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Set once, never cleared. Archiving is one-way.
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Matches the 0003/0027/0031/0032 policy shape, which scopes on org AND
        # demo.
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocked_reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            _in_list("requirement_type", REQUIREMENT_TYPES),
            name="ck_nf_award_requirements_type",
        ),
        sa.CheckConstraint(
            _in_list("requirement_status", REQUIREMENT_STATUSES),
            name="ck_nf_award_requirements_status",
        ),
        sa.CheckConstraint(
            _in_list("requirement_source", REQUIREMENT_SOURCES),
            name="ck_nf_award_requirements_source",
        ),
        sa.CheckConstraint(
            _in_list("due_date_status", DUE_DATE_STATUSES),
            name="ck_nf_award_requirements_due_date_status",
        ),
        sa.CheckConstraint(
            _in_list("recurrence_rule", RECURRENCES),
            name="ck_nf_award_requirements_recurrence",
        ),
        sa.CheckConstraint(
            _in_list("proof_status", PROOF_STATUSES),
            name="ck_nf_award_requirements_proof_status",
        ),
        sa.CheckConstraint(
            _in_list("submission_status", SUBMISSION_STATUSES),
            name="ck_nf_award_requirements_submission_status",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_award_requirements_fact_status",
        ),
        # A requirement nobody can name is a requirement nobody can act on.
        sa.CheckConstraint(
            "length(trim(requirement_title)) > 0",
            name="ck_nf_award_requirements_title_not_blank",
        ),
        # The contradiction two booleans would otherwise permit. Gate 108 models
        # this as one derivation off provenance; the columns exist so a query
        # can filter, and this refuses them disagreeing.
        sa.CheckConstraint(
            "NOT (active_obligation AND projected_burden)",
            name="ck_nf_award_requirements_not_both_obligation_and_projection",
        ),
        # The rule the whole gate turns on, enforced at the row: only a human
        # entry or an evidence extraction can oblige anybody.
        sa.CheckConstraint(
            "NOT active_obligation OR "
            + _in_list("requirement_source", ACTIVE_CAPABLE_SOURCES),
            name="ck_nf_award_requirements_obligation_needs_capable_source",
        ),
        # And a projection is exactly the one provenance that produces one.
        sa.CheckConstraint(
            "projected_burden = (requirement_source = 'projected_from_nofo')",
            name="ck_nf_award_requirements_projection_matches_source",
        ),
        # An unreadable document cannot oblige anybody either, and says so in
        # its own column rather than only by absence.
        sa.CheckConstraint(
            "unsupported_requirement = "
            "(requirement_source = 'unsupported_document_type')",
            name="ck_nf_award_requirements_unsupported_matches_source",
        ),
        sa.CheckConstraint(
            "NOT (unsupported_requirement AND active_obligation)",
            name="ck_nf_award_requirements_unsupported_is_not_an_obligation",
        ),
        # A date you cannot count down to must not be stored as one you can.
        sa.CheckConstraint(
            "requirement_due_date IS NOT NULL OR NOT "
            + _in_list("due_date_status", DATE_CALCULABLE_STATUSES),
            name="ck_nf_award_requirements_calculable_status_needs_a_date",
        ),
        # A date without an account of where it came from is a guess wearing a
        # deadline's clothes.
        sa.CheckConstraint(
            "requirement_due_date IS NULL OR due_date_status <> 'unknown'",
            name="ck_nf_award_requirements_date_needs_a_status",
        ),
        # Acceptance is a separate event from submission, and cannot precede it.
        sa.CheckConstraint(
            "accepted_at IS NULL OR submitted_at IS NOT NULL",
            name="ck_nf_award_requirements_accepted_needs_submitted",
        ),
        # An accepted proof is one somebody filed. Nothing derives acceptance
        # from a document reference, and nothing derives it from submission.
        sa.CheckConstraint(
            "proof_status <> 'proof_accepted' OR proof_document_ref IS NOT NULL",
            name="ck_nf_award_requirements_accepted_proof_needs_a_reference",
        ),
        # An unestablished requirement cannot carry an established fact status.
        sa.CheckConstraint(
            "NOT active_obligation OR "
            "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
            name="ck_nf_award_requirements_obligation_needs_established_facts",
        ),
    )

    op.create_index("ix_nf_award_requirements_organization", TABLE, ["organization_id"])
    op.create_index("ix_nf_award_requirements_award", TABLE, ["awarded_grant_id"])
    # The calendar's query: what is due, for this organization, soonest first.
    op.create_index(
        "ix_nf_award_requirements_due_date",
        TABLE,
        ["organization_id", "requirement_due_date"],
    )

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002, 0027, 0029, 0031
        # and 0032 behave.
        return
    conn.execute(text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;"))
    conn.execute(text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;"))
    conn.execute(
        text(
            f"""
CREATE POLICY {TABLE}_org_demo_scope ON {TABLE}
  USING (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  )
  WITH CHECK (
    organization_id = current_setting('app.current_org_id', true)::uuid
    AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
  );
"""
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"DROP POLICY IF EXISTS {TABLE}_org_demo_scope ON {TABLE};"))
    op.drop_index("ix_nf_award_requirements_due_date", table_name=TABLE)
    op.drop_index("ix_nf_award_requirements_award", table_name=TABLE)
    op.drop_index("ix_nf_award_requirements_organization", table_name=TABLE)
    op.drop_table(TABLE)
