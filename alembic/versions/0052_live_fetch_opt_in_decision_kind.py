"""Alembic 0052: `live_fetch` is a decision kind (Gate 163H).

## Why not a new table, and why not a flag

Gate 162 chose one decision table with a `decision_kind` discriminator on the
grounds that terms review and source review have identical shape: an answer, a
signer, a time, an evidence reference, an expiry. A live-fetch opt-in has the
same shape again, so it is a third kind.

The alternative was a boolean column somewhere — `live_transport_enabled`, or
`opted_in` on the activation row. Both were rejected for the same reason
Gate 162 rejected a stored allowlist flag: a boolean carries no signature, no
time and no evidence, and the one thing an opt-in must be is attributable.

As a decision kind it inherits every constraint 0048 already enforces:

```sql
CHECK (decision <> 'approved' OR (reviewed_by IS NOT NULL
                                  AND reviewed_at IS NOT NULL))
CHECK (decision <> 'approved' OR evidence_fingerprint IS NOT NULL)
```

So an opt-in nobody signed cannot be written, in the same place and by the
same rule as an approval nobody signed.

## It is per source, and that is load-bearing

The unique index is `(organization_id, source_id, decision_kind)`. Opting in a
second source means a second row and a second signature. There is no shape in
this schema that opts in "everything authorized", which matters because 177
registry rows are one terms decision away from being authorized.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0052"
down_revision: str | Sequence[str] | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DECISIONS = "nf_source_authorization_decisions"

DECISION_KINDS = ("terms", "human_review", "live_fetch")

PREVIOUS_KINDS = ("terms", "human_review")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    with op.batch_alter_table(DECISIONS) as batch:
        batch.drop_constraint(
            "ck_nf_source_authorization_decisions_kind", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_authorization_decisions_kind",
            _in_list("decision_kind", DECISION_KINDS),
        )
        # A live-fetch opt-in answers a question the live guard has no terms
        # status for, so it carries NOT_APPLICABLE like a human review does.
        # Recording a guard terms status on one would imply it said something
        # about terms, which it does not.
        batch.create_check_constraint(
            "ck_nf_source_authorization_decisions_opt_in_status",
            "decision_kind <> 'live_fetch' OR guard_status = 'NOT_APPLICABLE'",
        )


def downgrade() -> None:
    with op.batch_alter_table(DECISIONS) as batch:
        batch.drop_constraint(
            "ck_nf_source_authorization_decisions_opt_in_status", type_="check"
        )
        batch.drop_constraint(
            "ck_nf_source_authorization_decisions_kind", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_authorization_decisions_kind",
            _in_list("decision_kind", PREVIOUS_KINDS),
        )
