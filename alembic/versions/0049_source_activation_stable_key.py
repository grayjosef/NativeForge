"""Alembic 0049: give activation a stable source key (Gate 163A).

## The weakness this repairs

Gate 162 resolved `activation_status` by joining
`nf_active_opportunity_sources` to the file-backed registry on `source_name` —
a DISPLAY STRING. That table has no `source_id` column, and the registry has no
UUID, so there was nothing better to join on.

The resolver reported the weakness rather than relying on it quietly, and doc
847 told Gate 163 to fix it before activating anything. This is the first gate
where a wrong join would authorize a real HTTP request, so it is fixed first.

A display name can be edited for clarity, translated, or corrected for a typo,
and any of those would silently detach an activation from the source it
authorized. A seed id cannot.

## What it adds

```text
source_id TEXT   the registry's seed_id - stable, already in the CSV,
                 and the same id every other Gate 156-162 table keys on
```

Nullable, because rows may predate it. The resolver prefers `source_id` and
falls back to the name join ONLY when it is null, and reports which it used —
so a row without the key is visibly weaker rather than silently equivalent.

There is deliberately no backfill. Zero rows existed when this ran, and
inventing a mapping from display names to seed ids for hypothetical future rows
is exactly the guesswork the column exists to eliminate.

## Also: robots evidence

`nf_source_robots_evidence` records what a robots.txt fetch actually returned.
Gate 162 left `robots_status` unresolvable for every real source because
answering it requires the live request this gate is finally permitted to make.

The evidence is per HOST, not per source, because robots.txt governs a host.
Two sources on the same host share one answer, and recording it twice would let
them disagree.

```sql
CHECK (decision <> 'allowed' OR (fetched_at IS NOT NULL
                                 AND payload_sha256 IS NOT NULL))
```

An `allowed` verdict with no fetch time and no payload hash cannot be written:
robots permission must come from bytes somebody actually received.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | Sequence[str] | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_SOURCES = "nf_active_opportunity_sources"
ROBOTS = "nf_source_robots_evidence"

#: What the fetch concluded about the path we intend to request.
#:
#: `allowed` and `absent` both permit - a host with no robots.txt has published
#: no restriction - but they are recorded separately because "we read the file
#: and it permits" is different evidence from "there is no file".
ROBOTS_DECISIONS = (
    "allowed",
    "disallowed",
    "absent",
    "unreachable",
    "unparseable",
    "unknown",
)

FACT_STATUSES = ("live_fetch", "synthetic_fixture", "demo_fixture", "unknown")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    # ---- the stable key -------------------------------------------------
    op.add_column(
        ACTIVE_SOURCES,
        sa.Column("source_id", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_nf_active_opportunity_sources_source_id",
        ACTIVE_SOURCES,
        ["organization_id", "source_id"],
    )

    # ---- robots evidence, per host --------------------------------------
    op.create_table(
        ROBOTS,
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
        # robots.txt governs a HOST. Recording it per source would let two
        # sources on one host hold contradictory answers.
        sa.Column("host", sa.Text(), nullable=False),
        # Which source's activation occasioned the fetch. Provenance, not key.
        sa.Column("fetched_for_source_id", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(length=16), nullable=False),
        # The path the decision is ABOUT. A robots verdict is path-scoped, and
        # one answer must not become permission for the whole host.
        sa.Column("evaluated_path", sa.Text(), nullable=False),
        sa.Column("user_agent_scope", sa.String(length=128), nullable=True),
        # Links to the Gate 160 payload holding the exact bytes.
        sa.Column("payload_sha256", sa.String(length=64), nullable=True),
        sa.Column("attempt_id", sa.Text(), nullable=True),
        sa.Column("evidence_ref", sa.String(length=512), nullable=True),
        sa.Column("recheck_due_at", sa.DateTime(timezone=True), nullable=True),
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
            _in_list("decision", ROBOTS_DECISIONS),
            name="ck_nf_source_robots_evidence_decision",
        ),
        sa.CheckConstraint(
            _in_list("fact_status", FACT_STATUSES),
            name="ck_nf_source_robots_evidence_fact_status",
        ),
        # THE constraint. Robots permission must come from bytes somebody
        # actually received, so an `allowed` verdict needs a fetch time and a
        # payload hash. `absent` is exempt: a 404 has no body to hash, and
        # "there is no robots.txt" is a fact about the fetch, not the payload.
        sa.CheckConstraint(
            "decision <> 'allowed' OR "
            "(fetched_at IS NOT NULL AND payload_sha256 IS NOT NULL)",
            name="ck_nf_source_robots_evidence_allowed_needs_bytes",
        ),
        sa.CheckConstraint(
            "decision NOT IN ('allowed', 'disallowed', 'absent') "
            "OR fetched_at IS NOT NULL",
            name="ck_nf_source_robots_evidence_verdict_needs_a_fetch",
        ),
    )

    # One live answer per host per organization. A recheck replaces it.
    op.create_index(
        "ux_nf_source_robots_evidence_host",
        ROBOTS,
        ["organization_id", "host", "evaluated_path"],
        unique=True,
    )
    op.create_index(
        "ix_nf_source_robots_evidence_source",
        ROBOTS,
        ["organization_id", "fetched_for_source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_nf_source_robots_evidence_source", table_name=ROBOTS)
    op.drop_index("ux_nf_source_robots_evidence_host", table_name=ROBOTS)
    op.drop_table(ROBOTS)
    op.drop_index(
        "ix_nf_active_opportunity_sources_source_id", table_name=ACTIVE_SOURCES
    )
    op.drop_column(ACTIVE_SOURCES, "source_id")
