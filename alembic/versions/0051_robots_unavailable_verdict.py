"""Alembic 0051: `unavailable` is a robots verdict (Gate 163F, RFC 9309).

## The distinction migration 0049 was missing

0049's vocabulary had `absent` and `unreachable` and nothing between them. RFC
9309 section 2.3.1 separates three cases that 0049 collapsed into two:

```text
2xx  Successful      parse the rules
4xx  UNAVAILABLE     "crawlers MAY access any resources"
5xx  Unreachable     "crawlers MUST assume complete disallow"
```

`absent` is a fine word for a 404 — the file definitively is not there. It is
the wrong word for a 403, where the file could not be retrieved and we cannot
say whether it exists. Both permit under the RFC, and they are different
evidence, so they get different words.

The first live fetch of this campaign returned exactly the case that had no
word: `api.grants.gov/robots.txt` answered 403 `Missing Authentication Token`
— an AWS API Gateway refusing an unrouted path. The parser mapped every status
>= 400 to `unreachable` and blocked, which was conservative and wrong.

## Why the correction is recorded rather than quietly applied

The fix moves in the PERMITTING direction: a verdict that blocked now does not.
That is the direction to be most careful in, so the raw 403 evidence is
preserved exactly as received — same bytes, same hash, same status — and only
the DERIVED verdict changes. Nothing here rewrites history to pretend robots.txt
returned 200.

## And it still authorizes nothing

RFC 9309 section 2: robots.txt rules are not a form of access authorization.
`unavailable` means the robots protocol adds no restriction for this authority.
Permission to call the source comes from the recorded terms decision, the
recorded human review, the recorded activation, and a source-specific
live-fetch opt-in — none of which this migration touches.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0051"
down_revision: str | Sequence[str] | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROBOTS = "nf_source_robots_evidence"

#: `unavailable` joins the vocabulary. See the docstring: it is the 4xx case,
#: distinct from `absent` (a definite 404) and from `unreachable` (5xx or a
#: network failure, which disallows).
ROBOTS_DECISIONS = (
    "allowed",
    "disallowed",
    "absent",
    "unavailable",
    "unreachable",
    "unparseable",
    "unknown",
)

PREVIOUS_DECISIONS = (
    "allowed",
    "disallowed",
    "absent",
    "unreachable",
    "unparseable",
    "unknown",
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    with op.batch_alter_table(ROBOTS) as batch:
        batch.drop_constraint(
            "ck_nf_source_robots_evidence_decision", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_robots_evidence_decision",
            _in_list("decision", ROBOTS_DECISIONS),
        )
        # `unavailable` permits, so like `allowed` it must rest on an actual
        # fetch. A verdict nobody fetched is not evidence about anything.
        batch.drop_constraint(
            "ck_nf_source_robots_evidence_verdict_needs_a_fetch", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_robots_evidence_verdict_needs_a_fetch",
            "decision NOT IN ('allowed', 'disallowed', 'absent', 'unavailable') "
            "OR fetched_at IS NOT NULL",
        )
        # And an `unavailable` verdict must name the status that produced it,
        # so "the file could not be retrieved" is never a bare assertion.
        batch.create_check_constraint(
            "ck_nf_source_robots_evidence_unavailable_needs_a_status",
            "decision <> 'unavailable' OR http_status IS NOT NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(ROBOTS) as batch:
        batch.drop_constraint(
            "ck_nf_source_robots_evidence_unavailable_needs_a_status",
            type_="check",
        )
        batch.drop_constraint(
            "ck_nf_source_robots_evidence_verdict_needs_a_fetch", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_robots_evidence_verdict_needs_a_fetch",
            "decision NOT IN ('allowed', 'disallowed', 'absent') "
            "OR fetched_at IS NOT NULL",
        )
        batch.drop_constraint(
            "ck_nf_source_robots_evidence_decision", type_="check"
        )
        batch.create_check_constraint(
            "ck_nf_source_robots_evidence_decision",
            _in_list("decision", PREVIOUS_DECISIONS),
        )
