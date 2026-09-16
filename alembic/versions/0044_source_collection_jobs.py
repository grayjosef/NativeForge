"""Alembic 0044: the collection job lifecycle (Gate 158B).

## The gap this closes, measured

```text
scheduler cycle produced          1 job (in memory)
rows written anywhere             0
=> scheduler output persisted     False
```

Nothing existed until a worker looked. A scheduler cycle that ran and then lost
its process left no trace, so "this work is waiting" was not a fact the system
held — only "a worker already refused it" was, and only because Gate 157's
worker wrote a lease on its way past.

## A job is not a lease

0043 gave `nf_source_collection_job_leases` a lease (owner, acquired, expires)
AND a lifecycle (`lease_status`, `attempt_count`, `next_retry_at`). The second
half was a job fact living on a lease row, because the worker had nowhere else
to write it.

They have different lifetimes, and one row cannot have two:

```text
a lease   expires in five minutes, and is meant to
a job     survives until it is done or archived
```

So this table owns the lifecycle and **has no owner or expiry column**. Gate
157 keeps the claim. A column that does not exist cannot drift from the table
that owns it.

## A job is not a source check run

`nf_source_check_runs.check_status` is
`scheduled|running|succeeded|succeeded_with_warnings|failed|canceled`, beside
`opportunities_seen_count` and `accepted_count`. That is the record of a check
that happened. A queue row written there would assert a source was contacted
when none was — the reason Gate 157 declined it for leases, and the reason this
gate declines it again.

## `completed` exists and nothing can set it

The vocabulary includes it because a job lifecycle without a terminal success
state is incomplete, and leaving it out would mean adding it later under
pressure. But:

```text
CHECK (status <> 'completed' OR execution_proof_ref IS NOT NULL)
```

`execution_proof_ref` is null on every row, no code in Gate 158 sets it, and the
gate that defines what an execution proof *is* has not been written. So a
`completed` row is refused by the database, not merely discouraged by a
convention somebody could forget.

**A persisted job is not proof a collection occurred.** This constraint is that
sentence, enforced.

## What it cannot hold

```text
no response body    no url             no status code
no credential       no api key         no token or cookie
no oauth state      no pkce verifier   no provider subject
no customer data    no address         no object bytes
```

The rule that produced 0041's missing address column, 0042's missing rendered
body and 0043's three refused booleans, applied to the thing a collection queue
would most plausibly accumulate: the results.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: str | Sequence[str] | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOBS = "nf_source_collection_jobs"

#: The lifecycle of a piece of collection work.
#:
#: `refused` is not `failed`: a source nobody approved is not a broken job, and
#: collapsing them would put 171 terms-blocked sources in a failure count.
#: `retry_wait` is reachable only from a genuine transient worker failure.
JOB_STATUSES = (
    "queued",
    "claimed",
    "refused",
    "retry_wait",
    "canceled",
    "completed",
    "failed",
    "archived",
)

#: Why a job stopped, when it stopped for good. Mirrors Gate 157's classes so
#: one vocabulary describes a refusal in both tables.
TERMINAL_REASONS = (
    "none",
    "refused_by_activation",
    "terms_blocked",
    "human_review_blocked",
    "transient_worker_failure",
    "permanent_worker_failure",
    "attempt_budget_exhausted",
    "canceled_by_operator",
    "superseded_by_a_newer_slot",
    "unknown",
)

#: Which runtime created the row. Provenance, not identity.
CREATED_BY_RUNTIMES = (
    "scheduler_cycle",
    "worker_cycle",
    "operator_enqueue",
    "verifier_fixture",
    "unknown",
)

FACT_STATUSES = ("demo_fixture", "tenant_supplied", "verified", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        JOBS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        # -- identity -------------------------------------------------------
        #
        # `job_id` is Gate 99B's sha256 over (source_id, collector_id,
        # job_type, scheduled_for, execution_mode). Deterministic, so the same
        # slot re-enqueued is the same row - which is what the unique index
        # below turns into idempotency.
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        # -- which slot of work this is -------------------------------------
        sa.Column("schedule_key", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collection_mode", sa.String(length=32), nullable=False),
        # -- lifecycle ------------------------------------------------------
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_reason", sa.String(length=48), nullable=False),
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        # -- the column that makes `completed` unreachable ------------------
        #
        # Null on every row. No Gate 158 code sets it, and the gate that
        # defines what an execution proof IS has not been written.
        sa.Column("execution_proof_ref", sa.Text(), nullable=True),
        # -- provenance -----------------------------------------------------
        sa.Column("created_by_runtime", sa.String(length=32), nullable=False),
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
            _in_list("status", JOB_STATUSES),
            name="ck_nf_source_collection_jobs_status",
        ),
        sa.CheckConstraint(
            _in_list("terminal_reason", TERMINAL_REASONS),
            name="ck_nf_source_collection_jobs_terminal_reason",
        ),
        sa.CheckConstraint(
            _in_list("created_by_runtime", CREATED_BY_RUNTIMES),
            name="ck_nf_source_collection_jobs_created_by",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_collection_jobs_fact_status",
        ),
        # A budget that can be exceeded is not a budget.
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="ck_nf_source_collection_jobs_attempts_bounded",
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name="ck_nf_source_collection_jobs_max_attempts_positive",
        ),
        # THE constraint of this migration. `completed` without an execution
        # proof is refused by the database, so "a persisted job is not proof a
        # collection occurred" is enforced rather than asserted.
        sa.CheckConstraint(
            "status <> 'completed' OR execution_proof_ref IS NOT NULL",
            name="ck_nf_source_collection_jobs_completed_needs_execution_proof",
        ),
        # `retry_wait` is for a transient failure and nothing else. An
        # activation, terms or human-review refusal parked in a retry queue
        # would burn attempts on work no worker can ever run.
        sa.CheckConstraint(
            "status <> 'retry_wait' OR terminal_reason = 'transient_worker_failure'",
            name="ck_nf_source_collection_jobs_retry_wait_is_transient_only",
        ),
        # An archived job carries its timestamp, and a live one does not.
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) "
            "OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_nf_source_collection_jobs_archived_has_a_timestamp",
        ),
    )

    # Idempotency, enforced. A repeated scheduler cycle re-enqueues the same
    # deterministic id and the insert is refused, rather than adding a row.
    op.create_index(
        "ux_nf_source_collection_jobs_job_id",
        JOBS,
        ["organization_id", "job_id"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_collection_jobs_source",
        JOBS,
        ["organization_id", "source_id"],
    )
    op.create_index(
        "ix_nf_source_collection_jobs_status",
        JOBS,
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_nf_source_collection_jobs_retry",
        JOBS,
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_nf_source_collection_jobs_retry", table_name=JOBS)
    op.drop_index("ix_nf_source_collection_jobs_status", table_name=JOBS)
    op.drop_index("ix_nf_source_collection_jobs_source", table_name=JOBS)
    op.drop_index("ux_nf_source_collection_jobs_job_id", table_name=JOBS)
    op.drop_table(JOBS)
