"""Alembic 0034: nf_award_requirement_proof_events (Gate 126B).

The audit trail for what was filed, when, by whom, and what happened to it.

## Why this is not a column on the requirement

Gate 125A recorded the reason and it holds. One requirement submitted, rejected,
resubmitted and accepted is four rows with four actors and four timestamps.
Putting that on `nf_award_requirements` would mean either overwriting the
history — the one thing an audit trail may never do — or a JSON array nothing
can query by actor or date.

## Append-first, with exactly two updates

```text
superseded_at   set on the row that was replaced. Never cleared.
archived_at     set when a row leaves the active view. Never cleared.
```

Everything else is written once. There is no delete path.

Superseding touches two rows, and the two halves live on different ones:

```text
the NEW row       supersedes_event_id -> the row it replaces
the REPLACED row  superseded_at        = when it stopped being current
```

The replaced row keeps its reference, its timestamps and its actor. A chain is
ordinary: if C supersedes B which superseded A, then B carries both a
`supersedes_event_id` and a `superseded_at`, which is why no constraint couples
them on one row.

`superseded_at` exists at all so "is this event current?" is a column rather
than a not-exists subquery against the whole table.

## Three identifiers, one authority

```text
organization_id       the RLS predicate's left side. The anchor.
award_requirement_id  a row relationship. Not an authority.
awarded_grant_id      context, nullable. Not an authority either.
```

`awarded_grant_id` is denormalised on purpose: it is the award a proof belongs
to, carried so a portfolio view need not join through the requirement. Reaching
the organization through two joins would make this table's policy depend on two
other tables' policies.

## Four things a proof event is not

```text
a document reference is not a document      there is no document store
a document reference is not a submission    somebody has to file it
a submission is not an acceptance           somebody has to accept it
a rejection is not a deletion               the proof reference is retained
```

`proof_document_storage_available` is a column rather than a constant so a row
records what was true when it was written. It is false everywhere today, and
`ck_..._storage_flag_needs_a_store` refuses a row claiming a store while naming
no document.

## No rows are inserted

A production write needs `customer_auth_live` and a verified operational
binding, and Gates 115-125 measured both as false.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "nf_award_requirement_proof_events"

# What happened. Gate 108's PROOF_ACTIONS is five verbs plus `unknown`; this
# adds the four the audit trail needs and Gate 108 never had. A test asserts
# every PROOF_ACTION still maps into this set, so the extension cannot drift
# into a replacement.
EVENT_TYPES = (
    # bridged from Gate 108 PROOF_ACTIONS
    "attach_proof",
    "mark_submitted",
    "mark_accepted",
    "mark_rejected",
    "mark_waived",
    # added by Gate 126
    "proof_requested",
    "proof_needs_review",
    "proof_superseded",
    "audit_note_added",
    "unknown",
)

# What the proof IS now. Bridged unchanged from Gate 108's PROOF_STATUSES.
EVENT_STATUSES = (
    "not_submitted",
    "proof_missing",
    "proof_attached",
    "proof_accepted",
    "proof_rejected",
    "unknown",
)

# The two statuses that assert a funder acted.
FUNDER_DECIDED_STATUSES = ("proof_accepted", "proof_rejected")

# Where the event came from. Same shape as Gate 125's requirement_source.
PROOF_SOURCES = (
    "human_entered",
    "evidence_extracted",
    "system_generated",
    "unsupported_document_type",
    "needs_human_review",
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
        # The RLS anchor. Everything else is a relationship, context, a fact or
        # an audit trail.
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # A row relationship, never an authority. A proof event without a
        # requirement is evidence of nothing.
        sa.Column(
            "award_requirement_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_award_requirements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Context, denormalised so a portfolio view need not join through the
        # requirement. Nullable, and never an authority.
        sa.Column(
            "awarded_grant_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_awarded_grants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # -- what happened, and what it made true -----------------------------
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_status", sa.String(length=32), nullable=False),
        # -- what was filed ---------------------------------------------------
        # A reference, not a document. There is no store behind it.
        sa.Column("proof_document_ref", sa.Text(), nullable=True),
        # Recorded per row rather than read from a constant, so an event says
        # what was true when it was written.
        sa.Column(
            "proof_document_storage_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("proof_summary", sa.Text(), nullable=True),
        sa.Column("proof_source", sa.String(length=32), nullable=False),
        sa.Column("proof_source_ref", sa.Text(), nullable=True),
        # -- when ---------------------------------------------------------------
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by_identity_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("nf_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # -- superseding, which retains rather than replaces --------------------
        sa.Column(
            "supersedes_event_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey(f"{TABLE}.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        # -- lifecycle and audit ------------------------------------------------
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
        # Set once, never cleared. Archiving is one-way.
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # Matches the 0003/0027/0031/0032/0033 policy shape.
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
            _in_list("event_type", EVENT_TYPES),
            name="ck_nf_proof_events_event_type",
        ),
        sa.CheckConstraint(
            _in_list("event_status", EVENT_STATUSES),
            name="ck_nf_proof_events_event_status",
        ),
        sa.CheckConstraint(
            _in_list("proof_source", PROOF_SOURCES),
            name="ck_nf_proof_events_proof_source",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_proof_events_fact_status",
        ),
        # A submission is not an acceptance, and an acceptance is an event with
        # a date.
        sa.CheckConstraint(
            "event_status <> 'proof_accepted' OR accepted_at IS NOT NULL",
            name="ck_nf_proof_events_accepted_needs_a_timestamp",
        ),
        # Nothing is accepted that was never filed.
        sa.CheckConstraint(
            "accepted_at IS NULL OR submitted_at IS NOT NULL",
            name="ck_nf_proof_events_accepted_needs_submitted",
        ),
        # An acceptance names what was accepted.
        sa.CheckConstraint(
            "event_status <> 'proof_accepted' OR proof_document_ref IS NOT NULL",
            name="ck_nf_proof_events_accepted_needs_a_reference",
        ),
        sa.CheckConstraint(
            "event_status <> 'proof_rejected' OR rejected_at IS NOT NULL",
            name="ck_nf_proof_events_rejected_needs_a_timestamp",
        ),
        # A rejection never removes the proof that was filed. This is the
        # constraint that makes "rejected is not deleted" a property of the row
        # rather than a promise in a docstring.
        sa.CheckConstraint(
            "event_status <> 'proof_rejected' OR proof_document_ref IS NOT NULL",
            name="ck_nf_proof_events_rejection_retains_the_proof",
        ),
        # A funder cannot both accept and reject in one event.
        sa.CheckConstraint(
            "accepted_at IS NULL OR rejected_at IS NULL",
            name="ck_nf_proof_events_not_accepted_and_rejected",
        ),
        # A superseding event names what it replaced, and only a superseding
        # event does. `superseded_at` is deliberately not coupled here: it lives
        # on the row that was replaced, which is a different row.
        sa.CheckConstraint(
            "(event_type = 'proof_superseded') = (supersedes_event_id IS NOT NULL)",
            name="ck_nf_proof_events_supersede_names_its_predecessor",
        ),
        # Nothing supersedes itself.
        sa.CheckConstraint(
            "supersedes_event_id IS NULL OR supersedes_event_id <> id",
            name="ck_nf_proof_events_nothing_supersedes_itself",
        ),
        # A storage flag with nothing to store is a claim about a store that
        # does not exist.
        sa.CheckConstraint(
            "NOT proof_document_storage_available OR proof_document_ref IS NOT NULL",
            name="ck_nf_proof_events_storage_flag_needs_a_store",
        ),
        # A review is an event with a date, and an unreviewed row must not carry
        # a reviewer.
        sa.CheckConstraint(
            "(reviewed_at IS NULL) = (reviewed_by_identity_id IS NULL)",
            name="ck_nf_proof_events_review_pair",
        ),
        # An unestablished event cannot assert that a funder decided anything.
        sa.CheckConstraint(
            "event_status NOT IN ('proof_accepted', 'proof_rejected') OR "
            "fact_status IN ('verified', 'tenant_supplied', 'demo_fixture')",
            name="ck_nf_proof_events_funder_decision_needs_established_facts",
        ),
        # An audit note is a note. It never moves the proof.
        sa.CheckConstraint(
            "event_type <> 'audit_note_added' OR "
            "(accepted_at IS NULL AND rejected_at IS NULL AND submitted_at IS NULL)",
            name="ck_nf_proof_events_a_note_decides_nothing",
        ),
    )

    op.create_index("ix_nf_proof_events_organization", TABLE, ["organization_id"])
    op.create_index("ix_nf_proof_events_requirement", TABLE, ["award_requirement_id"])
    # The audit trail's query: this organization's events, newest last.
    op.create_index(
        "ix_nf_proof_events_org_created", TABLE, ["organization_id", "created_at"]
    )

    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        # SQLite and others: RLS is a no-op, exactly as 0002, 0027, 0029, 0031,
        # 0032 and 0033 behave.
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
    op.drop_index("ix_nf_proof_events_org_created", table_name=TABLE)
    op.drop_index("ix_nf_proof_events_requirement", table_name=TABLE)
    op.drop_index("ix_nf_proof_events_organization", table_name=TABLE)
    op.drop_table(TABLE)
