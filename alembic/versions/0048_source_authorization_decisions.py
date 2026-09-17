"""Alembic 0048: where a human's answer about a source lives (Gate 162C/D).

## What was surveyed first

Four existing tables were candidates, and each records that a decision is
REQUIRED without anywhere to put the answer:

```text
nf_active_opportunity_sources
    legal_tos_review_required                 a requirement flag
    broad_eligibility_human_review_required   a requirement flag
    activation_approved_by / _at / _artifact  the ACTIVATION decision, which
                                              this gate composes and does not
                                              duplicate
nf_source_watchlist_entries
    human_review_required                     a requirement flag
    source_id (TEXT)                          the right id space, no answer
nf_discovery_review_items
    review_item_type includes source_verification
    review_status open/in_review/approved/rejected/...
    source_registry_id -> nf_opportunity_sources.id  (UUID, 0 rows)
nf_review_artifacts                            org-level, not per-source
```

`nf_discovery_review_items` was the closest fit and cannot be joined: its
`source_registry_id` is a UUID foreign key into `nf_opportunity_sources`, while
the 177-row source registry is file-backed and string-keyed
(`nf-seed-2026-fed-001`). Bridging those id spaces means creating opportunity
source rows, which is a different gate's work and would invent registry
identity as a side effect of recording a decision.

## Why ONE table and not two

Terms review and human review are different decisions by potentially different
authorities, and the first draft of this migration gave terms its own table.
Then human review turned out to need exactly the same shape: an answer, a
signer, a time, an evidence reference and an expiry.

Two near-identical tables is not the minimum persistence this gate was asked
for, so `decision_kind` discriminates and the constraints are written once.
Adding a third kind later costs a vocabulary entry rather than a table.

## The constraints that keep Gate 162 honest

```sql
CHECK (decision <> 'approved' OR (reviewed_by IS NOT NULL
                                  AND reviewed_at IS NOT NULL))
CHECK (decision <> 'approved' OR evidence_fingerprint IS NOT NULL)
CHECK (decision <> 'denied'   OR reviewed_by IS NOT NULL)
```

An approval nobody signed, or that names no evidence, cannot be written at all
— not by a service, not by a script, not by hand. The fact model refuses one
too, but a service can be bypassed and a CHECK cannot, and this is the single
row whose forgery would unlock a live source call.

There is deliberately **no** constraint forbidding `approved`. Gate 163 must be
able to write one for a source a human really reviewed. What is forbidden is an
approval without attribution and evidence.

## What it will not hold

```text
no terms text          a sha256 fingerprint of the document reviewed
no URL                 a sha256 fingerprint, as Gate 160 settled - terms
                       URLs carry query strings
no credential          no header, no token, no cookie
no customer data
```

The notes column is capped and is for a reviewer's classification, not for
quoting the document. Storing the terms text would make this table a copy of
somebody else's copyrighted page.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECISIONS = "nf_source_authorization_decisions"

#: Which question this row answers. One shape, two questions, potentially two
#: different authorities.
DECISION_KINDS = ("terms", "human_review")

#: The reviewer's answer.
#:
#: `needs_review` and `unknown` are deliberately separate: one means a reviewer
#: looked and deferred, the other means nobody has looked. Collapsing them
#: makes "we are waiting on a person" indistinguishable from "nobody has been
#: asked" - different problems with different owners and the same effect on
#: permission, which is precisely why a boolean will not do.
DECISION_VOCABULARY = (
    "approved",
    "denied",
    "needs_review",
    "unknown",
)

#: The live guard's own terms vocabulary, stored so the mapping from a
#: reviewer's answer to a guard input is a recorded fact rather than a
#: translation somebody remembers. Only meaningful for decision_kind='terms'.
GUARD_STATUSES = (
    "NO_REVIEW_REQUIRED",
    "ATTRIBUTION_REQUIRED",
    "TERMS_REVIEW_REQUIRED",
    "HUMAN_REVIEW_ONLY",
    "UNKNOWN",
    "NOT_APPLICABLE",
)

#: Guard statuses an approved TERMS decision may carry. The other members all
#: block, so an approval carrying one would be a row contradicting itself.
APPROVAL_PERMITTING = ("NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED")

FACT_STATUSES = ("synthetic_fixture", "demo_fixture", "tenant_supplied", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        DECISIONS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        # -- which source, and which question -------------------------------
        #
        # TEXT, matching the file-backed registry's id space. Not a UUID FK:
        # see the docstring on why nf_discovery_review_items cannot be joined.
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("decision_kind", sa.String(length=24), nullable=False),
        # -- the answer -----------------------------------------------------
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("guard_status", sa.String(length=32), nullable=False),
        # -- who and when ---------------------------------------------------
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=256), nullable=True),
        sa.Column("review_authority", sa.String(length=128), nullable=True),
        # -- what was reviewed ----------------------------------------------
        #
        # Fingerprints, never the document and never the URL.
        sa.Column("evidence_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("evidence_document_sha256", sa.String(length=64), nullable=True),
        sa.Column("evidence_ref", sa.String(length=512), nullable=True),
        # A reviewer's classification, capped. NOT a place to quote the terms.
        sa.Column("notes_classification", sa.String(length=256), nullable=True),
        # -- freshness ------------------------------------------------------
        #
        # A decision about a document that may have changed since is not
        # evidence about the current document.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("re_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
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
            _in_list("decision_kind", DECISION_KINDS),
            name="ck_nf_source_authorization_decisions_kind",
        ),
        sa.CheckConstraint(
            _in_list("decision", DECISION_VOCABULARY),
            name="ck_nf_source_authorization_decisions_decision",
        ),
        sa.CheckConstraint(
            _in_list("guard_status", GUARD_STATUSES),
            name="ck_nf_source_authorization_decisions_guard_status",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_authorization_decisions_fact_status",
        ),
        # THE constraints of this migration. An approval nobody signed, or that
        # names no evidence, cannot be written at all. This is the one row
        # whose forgery would unlock a live source call.
        sa.CheckConstraint(
            "decision <> 'approved' OR "
            "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_nf_source_authorization_decisions_approval_needs_signature",
        ),
        sa.CheckConstraint(
            "decision <> 'approved' OR evidence_fingerprint IS NOT NULL",
            name="ck_nf_source_authorization_decisions_approval_needs_evidence",
        ),
        # A denial needs attribution too, so "a human said no" stays
        # distinguishable from a row nobody owns.
        sa.CheckConstraint(
            "decision <> 'denied' OR reviewed_by IS NOT NULL",
            name="ck_nf_source_authorization_decisions_denial_needs_signature",
        ),
        # An approved TERMS decision carrying a blocking guard status would be
        # a row that contradicts itself. Human-review rows carry
        # NOT_APPLICABLE, so the constraint is scoped to terms.
        sa.CheckConstraint(
            "decision_kind <> 'terms' OR decision <> 'approved' OR "
            f"guard_status IN ({', '.join(repr(v) for v in APPROVAL_PERMITTING)})",
            name="ck_nf_source_authorization_decisions_terms_status_permits",
        ),
    )

    # One answer per source per question. A re-review REPLACES the answer,
    # because two live answers to the same question have no defined winner and
    # an append-only history needs a "which one counts" rule somebody will
    # eventually get wrong.
    op.create_index(
        "ux_nf_source_authorization_decisions_source_kind",
        DECISIONS,
        ["organization_id", "source_id", "decision_kind"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_authorization_decisions_decision",
        DECISIONS,
        ["organization_id", "decision_kind", "decision"],
    )
    op.create_index(
        "ix_nf_source_authorization_decisions_expiry",
        DECISIONS,
        ["organization_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nf_source_authorization_decisions_expiry", table_name=DECISIONS
    )
    op.drop_index(
        "ix_nf_source_authorization_decisions_decision", table_name=DECISIONS
    )
    op.drop_index(
        "ux_nf_source_authorization_decisions_source_kind", table_name=DECISIONS
    )
    op.drop_table(DECISIONS)
