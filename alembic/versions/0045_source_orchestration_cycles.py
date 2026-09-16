"""Alembic 0045: who is running the loop right now (Gate 159E).

## Why a new table, measured rather than assumed

Doc 827's survey:

```text
grep for pg_advisory_lock, advisory_lock, FOR UPDATE, with_for_update in src/
  0 hits
tables with an owner + acquired_at + released_at shape, excluding the job lease
  none
tables naming an orchestration cycle
  none
database backend   sqlite+pysqlite
```

There is nothing to compose. SQLite has no advisory lock, so the portable
atomic primitive is a unique index - which is what Gate 157 used for the job
lease and Gate 158 for enqueue idempotency. This is the third use of the same
primitive, not a third invention.

## This is NOT a second job lease

```text
nf_source_collection_job_leases   per JOB    who is working this one piece
nf_source_orchestration_cycles    per CYCLE  who is running the loop
```

One cycle covers every source in a pass and produces many jobs. A job lease
cannot express "one orchestrator at a time" because there is no single job to
hang it on, and hanging it on an arbitrary one would make the loop's exclusivity
depend on that job still existing.

Different question, different lifetime, different row. The job lease keeps its
own columns; this table declares none of them.

## Identity is the cycle, ownership is the contender

`cycle_id` is deterministic over `(orchestration_version, cadence, slot_index)`,
so the same slot is always the same row and the unique index over
`(organization_id, cycle_id)` is what suppresses a duplicate trigger. Two
processes racing for one slot both try to insert the same id; one insert fails.

`owner_id` carries a nonce, because two contenders must be distinguishable or
the loser would believe it had won.

## A cycle cannot record a completion

```text
CHECK (jobs_completed = 0)
CHECK (collectors_invoked = 0)
CHECK (live_source_calls = 0)
```

The columns exist so a read can assert them rather than trust a constant in
Python, and the database refuses any other value. Same shape as 0043's three
refused booleans: an orchestration cycle that claimed a collector ran would be
rejected by the store, not merely discouraged by a convention.

A cycle that fires is not a source that was checked.

## What it cannot hold

```text
no response body    no url             no status code
no credential       no api key         no token or cookie
no source payload   no customer data   no recipient
```
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | Sequence[str] | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CYCLES = "nf_source_orchestration_cycles"

#: The life of an ownership claim.
#:
#: `expired` is reachable only by a reclaim, and `released` only by the owner
#: finishing. A row that is merely old is still `acquired` until somebody
#: measures it - staleness is derived from `expires_at` against a clock, not
#: stored as a status that would need a sweeper to stay true.
CYCLE_STATUSES = (
    "acquired",
    "released",
    "expired",
    "abandoned",
    "unknown",
)

#: Why a cycle stopped. Mirrors nothing in Gate 157 on purpose: these are
#: orchestration outcomes, not job outcomes.
CYCLE_OUTCOMES = (
    "none",
    "completed_normally",
    "released_early",
    "reclaimed_from_an_expired_owner",
    "refused_duplicate_slot",
    "trigger_not_due",
    "operator_stopped",
    "unknown",
)

CADENCES = (
    "every_five_minutes",
    "every_fifteen_minutes",
    "hourly",
    "every_six_hours",
    "daily",
)

FACT_STATUSES = ("demo_fixture", "tenant_supplied", "verified", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        CYCLES,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        # -- identity: the SLOT, deterministic ------------------------------
        sa.Column("cycle_id", sa.Text(), nullable=False),
        sa.Column("orchestration_version", sa.String(length=32), nullable=False),
        sa.Column("cadence", sa.String(length=32), nullable=False),
        sa.Column("slot_index", sa.BigInteger(), nullable=False),
        sa.Column("slot_key", sa.Text(), nullable=True),
        # -- ownership: the CONTENDER, deliberately unique ------------------
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cycle_status", sa.String(length=32), nullable=False),
        sa.Column("cycle_outcome", sa.String(length=48), nullable=False),
        sa.Column("reclaim_count", sa.Integer(), nullable=False, server_default="0"),
        # -- what the cycle did ---------------------------------------------
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sources_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_reused", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_blocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_claimed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("jobs_refused", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "missed_windows_recovered",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "duplicate_triggers_suppressed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        # -- the three the database refuses to let grow ---------------------
        #
        # Declared so a read can assert them rather than trust a Python
        # constant, exactly as 0043 declared its three booleans.
        sa.Column("jobs_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "collectors_invoked", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "live_source_calls", sa.Integer(), nullable=False, server_default="0"
        ),
        # -- provenance ------------------------------------------------------
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
            _in_list("cycle_status", CYCLE_STATUSES),
            name="ck_nf_source_orchestration_cycles_status",
        ),
        sa.CheckConstraint(
            _in_list("cycle_outcome", CYCLE_OUTCOMES),
            name="ck_nf_source_orchestration_cycles_outcome",
        ),
        sa.CheckConstraint(
            _in_list("cadence", CADENCES),
            name="ck_nf_source_orchestration_cycles_cadence",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_orchestration_cycles_fact_status",
        ),
        # THE constraints of this migration. An orchestration cycle that
        # claimed a completion or a collector invocation is refused by the
        # database, so "a trigger is not a source check" is enforced.
        sa.CheckConstraint(
            "jobs_completed = 0",
            name="ck_nf_source_orchestration_cycles_no_completion",
        ),
        sa.CheckConstraint(
            "collectors_invoked = 0",
            name="ck_nf_source_orchestration_cycles_no_collector",
        ),
        sa.CheckConstraint(
            "live_source_calls = 0",
            name="ck_nf_source_orchestration_cycles_no_live_call",
        ),
        # A released cycle carries the instant it was released.
        sa.CheckConstraint(
            "cycle_status <> 'released' OR released_at IS NOT NULL",
            name="ck_nf_source_orchestration_cycles_released_has_a_timestamp",
        ),
        # An owned cycle has an owner AND an expiry. An owner with no expiry
        # could never be reclaimed, which is how one crashed process blocks
        # the loop forever.
        sa.CheckConstraint(
            "cycle_status <> 'acquired' "
            "OR (owner_id IS NOT NULL AND expires_at IS NOT NULL)",
            name="ck_nf_source_orchestration_cycles_owner_has_an_expiry",
        ),
        # Counts do not go backwards.
        sa.CheckConstraint(
            "sources_seen >= 0 AND jobs_created >= 0 AND jobs_reused >= 0 "
            "AND jobs_blocked >= 0 AND jobs_claimed >= 0 AND jobs_refused >= 0 "
            "AND missed_windows_recovered >= 0 "
            "AND duplicate_triggers_suppressed >= 0 AND reclaim_count >= 0",
            name="ck_nf_source_orchestration_cycles_counts_are_not_negative",
        ),
    )

    # Atomic acquisition, and duplicate-slot suppression. Two processes racing
    # for one slot insert the same deterministic cycle_id; one insert fails.
    op.create_index(
        "ux_nf_source_orchestration_cycles_cycle_id",
        CYCLES,
        ["organization_id", "cycle_id"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_orchestration_cycles_slot",
        CYCLES,
        ["organization_id", "cadence", "slot_index"],
    )
    op.create_index(
        "ix_nf_source_orchestration_cycles_status",
        CYCLES,
        ["organization_id", "cycle_status"],
    )
    op.create_index(
        "ix_nf_source_orchestration_cycles_expiry",
        CYCLES,
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_nf_source_orchestration_cycles_expiry", table_name=CYCLES)
    op.drop_index("ix_nf_source_orchestration_cycles_status", table_name=CYCLES)
    op.drop_index("ix_nf_source_orchestration_cycles_slot", table_name=CYCLES)
    op.drop_index("ux_nf_source_orchestration_cycles_cycle_id", table_name=CYCLES)
    op.drop_table(CYCLES)
