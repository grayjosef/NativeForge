"""Alembic 0050: a live attempt becomes recordable, and must name its warrant.

## What Gate 161 said would happen here

Migration 0047's docstring:

> Gate 162 is where that changes, deliberately, by a migration that relaxes
> these constraints with approvals in hand. Until then a live attempt is not a
> thing this database can hold - which is stronger than a flag nobody reads.

The approvals are now in hand. MAYHEM recorded a signed terms decision, a
signed source review and a signed activation for exactly one source
(`nf-seed-2026-api-grants-gov-search2`), and the attribution notice verified
verbatim on a customer-visible surface.

## This is a RELAXATION and a STRENGTHENING in the same migration

Four blanket refusals go:

```text
nf_source_collection_execution_attempts
    CHECK (transport_kind = 'hermetic')      dropped
    CHECK (live_source_call = 0)             dropped
nf_source_collection_raw_payloads
    CHECK (collector_invoked = 0)            dropped
    CHECK (live_fetch_performed = 0)         dropped
```

If that were all, the tables would go from refusing every live row to accepting
any live row, which trades one useless extreme for a worse one. So each is
replaced by a constraint that keeps the property that actually mattered — that
a live call is accountable:

```text
CHECK (live_source_call = 0 OR transport_kind = 'live')
CHECK (transport_kind <> 'live' OR authorized_source_id IS NOT NULL)
CHECK (live_fetch_performed = 0 OR authorized_source_id IS NOT NULL)
CHECK (collector_invoked = 0 OR authorized_source_id IS NOT NULL)
```

`authorized_source_id` is new on both tables. Every live row must name the
source whose recorded authorization permitted it. A live attempt that cannot
say which approval it was made under still cannot be written — which is the
question an auditor actually asks, and a stronger one than "did a live call
happen".

## What this does NOT do

It does not opt anything in. `DISPATCHABLE_KINDS` still contains only
`hermetic` until code changes, `allow_live_fetch` is still hardcoded False in
`authorize_source_for_live_access`, and no live transport implementation exists
yet. This migration makes a live row RECORDABLE; it does not make a live call
POSSIBLE.

The separation is the point: the database stops being the thing that refuses,
so the refusal has to live where it can be reasoned about.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: str | Sequence[str] | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ATTEMPTS = "nf_source_collection_execution_attempts"
PAYLOADS = "nf_source_collection_raw_payloads"


def upgrade() -> None:
    # ---- attempts -------------------------------------------------------
    with op.batch_alter_table(ATTEMPTS) as batch:
        batch.add_column(sa.Column("authorized_source_id", sa.Text(), nullable=True))
        batch.drop_constraint(
            "ck_nf_source_collection_execution_attempts_hermetic_only",
            type_="check",
        )
        batch.drop_constraint(
            "ck_nf_source_collection_execution_attempts_no_live_call",
            type_="check",
        )
        # A live call and a live transport are the same event described twice.
        # They may not disagree.
        batch.create_check_constraint(
            "ck_nf_source_collection_execution_attempts_live_needs_live_kind",
            "live_source_call = 0 OR transport_kind = 'live'",
        )
        # THE replacement. A live attempt must name the source whose recorded
        # authorization permitted it.
        batch.create_check_constraint(
            "ck_nf_source_collection_execution_attempts_live_needs_a_warrant",
            "transport_kind <> 'live' OR authorized_source_id IS NOT NULL",
        )

    op.create_index(
        "ix_nf_source_collection_execution_attempts_authorized_source",
        ATTEMPTS,
        ["organization_id", "authorized_source_id"],
    )

    # ---- payloads -------------------------------------------------------
    with op.batch_alter_table(PAYLOADS) as batch:
        batch.add_column(sa.Column("authorized_source_id", sa.Text(), nullable=True))
        batch.drop_constraint(
            "ck_nf_source_collection_raw_payloads_no_collector", type_="check"
        )
        batch.drop_constraint(
            "ck_nf_source_collection_raw_payloads_no_live_fetch", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_raw_payloads_live_needs_a_warrant",
            "live_fetch_performed = 0 OR authorized_source_id IS NOT NULL",
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_raw_payloads_collector_needs_a_warrant",
            "collector_invoked = 0 OR authorized_source_id IS NOT NULL",
        )

    op.create_index(
        "ix_nf_source_collection_raw_payloads_authorized_source",
        PAYLOADS,
        ["organization_id", "authorized_source_id"],
    )


def downgrade() -> None:
    # Reinstating the blanket refusals would fail against any live row already
    # recorded, which is correct: a downgrade past the first live collection
    # should not silently succeed.
    op.drop_index(
        "ix_nf_source_collection_raw_payloads_authorized_source",
        table_name=PAYLOADS,
    )
    with op.batch_alter_table(PAYLOADS) as batch:
        batch.drop_constraint(
            "ck_nf_source_collection_raw_payloads_collector_needs_a_warrant",
            type_="check",
        )
        batch.drop_constraint(
            "ck_nf_source_collection_raw_payloads_live_needs_a_warrant",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_raw_payloads_no_live_fetch",
            "live_fetch_performed = 0",
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_raw_payloads_no_collector",
            "collector_invoked = 0",
        )
        batch.drop_column("authorized_source_id")

    op.drop_index(
        "ix_nf_source_collection_execution_attempts_authorized_source",
        table_name=ATTEMPTS,
    )
    with op.batch_alter_table(ATTEMPTS) as batch:
        batch.drop_constraint(
            "ck_nf_source_collection_execution_attempts_live_needs_a_warrant",
            type_="check",
        )
        batch.drop_constraint(
            "ck_nf_source_collection_execution_attempts_live_needs_live_kind",
            type_="check",
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_execution_attempts_no_live_call",
            "live_source_call = 0",
        )
        batch.create_check_constraint(
            "ck_nf_source_collection_execution_attempts_hermetic_only",
            "transport_kind = 'hermetic'",
        )
        batch.drop_column("authorized_source_id")
