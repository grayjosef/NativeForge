"""Alembic 0047: a record that an attempt happened (Gate 161G).

## Why Gate 158 and Gate 160 cannot carry this

Measured against both tables:

```text
missing from BOTH   execution_status  transport_kind  refusal_reason
                    started_at  completed_at  http_status
                    bytes_received  live_source_call
                    execution_proof_available
```

And the decisive one: **a refused or timed-out attempt produces no payload row
at all.** Gate 160 stores a RESPONSE; an attempt the policy refused, or one that
timed out before any bytes arrived, has no response to store. Without this table
there is no record those attempts ever happened, and "we tried and were refused"
is exactly the fact an operator needs when a source stops working.

So this is not a second payload store and not a second job store. It records
**that an attempt was made, by which transport, and what came of it** - and
points at Gate 160's payload by `attempt_id` rather than duplicating a byte of
it.

## live_source_call is a column the database refuses to set true

```sql
CHECK (live_source_call = 0)
CHECK (transport_kind = 'hermetic')
```

Gate 161 has no live transport implementation, and the policy, the boundary and
`DISPATCHABLE_KINDS` each refuse one independently. This adds a fourth refusal
in the one place none of them can be bypassed: an attempt row claiming a live
call cannot be written at all.

Gate 162 is where that changes, deliberately, by a migration that relaxes these
constraints with approvals in hand. Until then a live attempt is not a thing this
database can hold - which is stronger than a flag nobody reads.

## execution_proof_available is scoped, not absolute

The column records whether THIS attempt satisfied the proof requirements. For a
hermetic attempt that means the fixture path worked end to end; it does not mean
a source was contacted, and `transport_kind` sitting beside it is what keeps the
two readable apart.

Gate 158's `completed` remains unreachable for real-source jobs. See doc 840.

## What it will not hold

```text
no response body      Gate 160 owns bytes; this points at them
no request URL        a sha256 fingerprint, as Gate 160 settled
no credential         no header, no token, no cookie
no customer data
```
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | Sequence[str] | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ATTEMPTS = "nf_source_collection_execution_attempts"

#: What happened to the attempt.
#:
#: `refused_by_policy` and `transport_failed` are deliberately separate: one
#: means we never tried, the other means we tried and could not. Collapsing them
#: would make "the policy is blocking us" indistinguishable from "the source is
#: down", which are opposite operational problems.
EXECUTION_STATUSES = (
    "refused_by_policy",
    "request_build_failed",
    "transport_refused",
    "transport_failed",
    "response_received",
    "response_persisted",
    "unknown",
)

#: Only hermetic exists. `live` is named so refusing it is expressible.
TRANSPORT_KINDS = ("hermetic", "live")

#: Why an attempt stopped. Mirrors Gate 157's failure classes where they
#: overlap, so one vocabulary describes a refusal across the block.
REFUSAL_REASONS = (
    "none",
    "refused_by_activation",
    "terms_blocked",
    "human_review_blocked",
    "not_a_synthetic_fixture",
    "live_transport_not_implemented",
    "live_transport_not_permitted",
    "scope_not_permitted",
    "request_build_refused",
    "transport_timeout",
    "transport_connection_failed",
    "response_too_large",
    "transient_worker_failure",
    "permanent_worker_failure",
    "unknown",
)

FACT_STATUSES = ("synthetic_fixture", "demo_fixture", "tenant_supplied", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        ATTEMPTS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        # -- identity: Gate 160's attempt id, shared on purpose ------------
        #
        # The same digest Gate 160 stores against the payload, so a payload and
        # its attempt join without a second identity to keep in step.
        sa.Column("attempt_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("collector_version", sa.String(length=128), nullable=False),
        # -- provenance ----------------------------------------------------
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        # -- when ----------------------------------------------------------
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # -- what happened --------------------------------------------------
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("transport_kind", sa.String(length=16), nullable=False),
        sa.Column("transport_outcome", sa.String(length=48), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("bytes_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refusal_reason", sa.String(length=48), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        sa.Column("request_url_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("request_method", sa.String(length=16), nullable=True),
        # -- the link to Gate 160's bytes -----------------------------------
        #
        # A payload hash, not a body. Null when no bytes arrived, which is the
        # normal case for a refusal or a timeout.
        sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("raw_payload_persisted", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        # -- the proof -------------------------------------------------------
        sa.Column("execution_proof_available", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        # -- declared so a read can assert it, and refused by the database ---
        sa.Column("live_source_call", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("fact_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            _in_list("execution_status", EXECUTION_STATUSES),
            name="ck_nf_source_collection_execution_attempts_status",
        ),
        sa.CheckConstraint(
            _in_list("transport_kind", TRANSPORT_KINDS),
            name="ck_nf_source_collection_execution_attempts_transport_kind",
        ),
        sa.CheckConstraint(
            _in_list("refusal_reason", REFUSAL_REASONS),
            name="ck_nf_source_collection_execution_attempts_refusal",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_collection_execution_attempts_fact_status",
        ),
        # THE two constraints of this migration. A live attempt is not a thing
        # this database can hold while Gate 161 stands.
        sa.CheckConstraint(
            "live_source_call = 0",
            name="ck_nf_source_collection_execution_attempts_no_live_call",
        ),
        sa.CheckConstraint(
            "transport_kind = 'hermetic'",
            name="ck_nf_source_collection_execution_attempts_hermetic_only",
        ),
        # A proof requires bytes that were actually persisted. Gate 160 owns
        # the hash; an attempt claiming a proof without one is refused.
        sa.CheckConstraint(
            "execution_proof_available = 0 "
            "OR (raw_payload_persisted = 1 AND raw_payload_sha256 IS NOT NULL)",
            name="ck_nf_source_collection_execution_attempts_proof_needs_payload",
        ),
        # Bytes and a persisted payload go together.
        sa.CheckConstraint(
            "raw_payload_persisted = 0 OR raw_payload_sha256 IS NOT NULL",
            name="ck_nf_source_collection_execution_attempts_persisted_has_a_hash",
        ),
        sa.CheckConstraint(
            "bytes_received >= 0",
            name="ck_nf_source_collection_execution_attempts_bytes_not_negative",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_nf_source_collection_execution_attempts_attempt_is_positive",
        ),
    )

    # One attempt, one row. A second execution of the same attempt identity is
    # refused, which is what makes a retry a NEW attempt rather than an
    # overwrite of the old one's outcome.
    op.create_index(
        "ux_nf_source_collection_execution_attempts_attempt",
        ATTEMPTS,
        ["organization_id", "attempt_id"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_collection_execution_attempts_job",
        ATTEMPTS,
        ["organization_id", "job_id"],
    )
    op.create_index(
        "ix_nf_source_collection_execution_attempts_source",
        ATTEMPTS,
        ["organization_id", "source_id", "started_at"],
    )
    op.create_index(
        "ix_nf_source_collection_execution_attempts_status",
        ATTEMPTS,
        ["organization_id", "execution_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nf_source_collection_execution_attempts_status", table_name=ATTEMPTS
    )
    op.drop_index(
        "ix_nf_source_collection_execution_attempts_source", table_name=ATTEMPTS
    )
    op.drop_index(
        "ix_nf_source_collection_execution_attempts_job", table_name=ATTEMPTS
    )
    op.drop_index(
        "ux_nf_source_collection_execution_attempts_attempt", table_name=ATTEMPTS
    )
    op.drop_table(ATTEMPTS)
