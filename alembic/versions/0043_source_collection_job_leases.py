"""Alembic 0043: a worker's claim on a collection job (Gate 157C/E).

## Why a new table, when Gate 156 needed none

Gate 156 reused `nf_opportunity_sources` because it already carried
`check_interval_days`, `next_check_due_at` and `last_checked_at` — the whole
scheduling state. There is no equivalent for a lease.

Four existing tables carry job-ish names. The closest, and the one most likely
to be misused, is `nf_source_check_runs`, whose `check_status` vocabulary is:

```text
scheduled  running  succeeded  succeeded_with_warnings  failed  canceled
```

That is the lifecycle of a check that is happening or has happened, sitting
beside `opportunities_seen_count` and `accepted_count`. Writing a lease row
there would assert that a check ran when nothing did — fabricating evidence in a
table other gates read. The semantics do not match, and the mismatch is not
cosmetic.

## What a lease is, and what it is not

A row here says **a worker claimed the right to attempt a job until a moment**.
It does not say a check happened, a source was contacted, or anything was
fetched. There is no column in which any of those could be recorded:

```text
no response body        no url         no status code
no credential           no api key     no provider subject
no customer data        no address     no payload of any kind
```

A column that does not exist cannot be filled by a later mistake. That rule
produced 0041's missing address column and 0042's missing rendered body, and it
applies here to the thing a collection worker would most plausibly want to
stash: the response.

## Attempts are bounded in the schema, not only in the code

`attempt_count` exists so a retry budget survives a restart. A worker that kept
attempts in memory would reset its own budget every time it crashed, which is
precisely when a bounded retry matters most.

## The failure class is stored, because only one of them retries

```text
refused_by_activation      no approval exists
terms_blocked              a human must read the terms
human_review_blocked       a human must look
transient_worker_failure   the only class that retries
permanent_worker_failure   the handler is wrong
none                       nothing failed
```

Storing the class rather than a boolean is what stops an activation refusal from
being retried as though it were a hiccup — a worker that did that would look
busy, burn its budget, and never surface that 171 sources need a person.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | Sequence[str] | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASES = "nf_source_collection_job_leases"

#: What a worker has done with this job. `claimed` is a right to attempt, not
#: an attempt; `refused` is the normal outcome while nothing is approved.
LEASE_STATUSES = (
    "pending",
    "claimed",
    "completed",
    "refused",
    "retryable",
    "failed",
    "expired",
    "unknown",
)

#: Only `transient_worker_failure` is worth trying again.
FAILURE_CLASSES = (
    "none",
    "refused_by_activation",
    "terms_blocked",
    "human_review_blocked",
    "transient_worker_failure",
    "permanent_worker_failure",
    "unknown",
)

FACT_STATUSES = ("demo_fixture", "tenant_supplied", "verified", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        LEASES,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        # -- what is being claimed ------------------------------------------
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        # -- who claimed it -------------------------------------------------
        #
        # A worker id, not a person and not a machine name. Nothing here
        # identifies an operator.
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        # -- how it went ----------------------------------------------------
        sa.Column("lease_status", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_outcome_at", sa.DateTime(timezone=True), nullable=True),
        # -- why it refused, in the job's own words -------------------------
        sa.Column("blocked_reasons", sa.JSON(), nullable=True),
        # -- constants, stored so a row cannot imply otherwise --------------
        #
        # A lease is a claim. These three columns exist to be checked, and a
        # constraint below refuses any row where one of them is true.
        sa.Column(
            "collector_invoked", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "url_fetched", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "raw_payload_written",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
            _in_list("lease_status", LEASE_STATUSES),
            name="ck_nf_source_collection_job_leases_status",
        ),
        sa.CheckConstraint(
            _in_list("failure_class", FAILURE_CLASSES),
            name="ck_nf_source_collection_job_leases_failure_class",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_collection_job_leases_fact_status",
        ),
        # A budget that can be exceeded is not a budget.
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="ck_nf_source_collection_job_leases_attempts_bounded",
        ),
        sa.CheckConstraint(
            "max_attempts >= 1",
            name="ck_nf_source_collection_job_leases_max_attempts_positive",
        ),
        # A claim without an owner or an expiry is not a claim. Either all
        # three lease fields are set, or none is.
        sa.CheckConstraint(
            "(lease_owner IS NULL AND lease_acquired_at IS NULL "
            "AND lease_expires_at IS NULL) "
            "OR (lease_owner IS NOT NULL AND lease_acquired_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="ck_nf_source_collection_job_leases_lease_fields_together",
        ),
        sa.CheckConstraint(
            "lease_expires_at IS NULL OR lease_acquired_at IS NULL "
            "OR lease_expires_at > lease_acquired_at",
            name="ck_nf_source_collection_job_leases_expiry_after_acquisition",
        ),
        # The three that make this a lease table and not a check-run table.
        # Gate 157 cannot write a row saying it fetched something, because the
        # database refuses it.
        sa.CheckConstraint(
            "collector_invoked = false",
            name="ck_nf_source_collection_job_leases_no_collector",
        ),
        sa.CheckConstraint(
            "url_fetched = false",
            name="ck_nf_source_collection_job_leases_no_fetch",
        ),
        sa.CheckConstraint(
            "raw_payload_written = false",
            name="ck_nf_source_collection_job_leases_no_payload",
        ),
    )

    # One live lease per job. The uniqueness is what makes a duplicate claim
    # refusable rather than merely discouraged.
    op.create_index(
        "ux_nf_source_collection_job_leases_job",
        LEASES,
        ["organization_id", "job_id"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_collection_job_leases_source",
        LEASES,
        ["organization_id", "source_id"],
    )
    op.create_index(
        "ix_nf_source_collection_job_leases_expiry",
        LEASES,
        ["lease_expires_at"],
    )
    op.create_index(
        "ix_nf_source_collection_job_leases_retry",
        LEASES,
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_nf_source_collection_job_leases_retry", table_name=LEASES)
    op.drop_index("ix_nf_source_collection_job_leases_expiry", table_name=LEASES)
    op.drop_index("ix_nf_source_collection_job_leases_source", table_name=LEASES)
    op.drop_index("ux_nf_source_collection_job_leases_job", table_name=LEASES)
    op.drop_table(LEASES)
