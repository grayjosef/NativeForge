"""Gate 158I phase A: the process that writes, then exits.

Phase A and phase B are separate processes on purpose. A restart proof that
reads back through the connection which wrote has two possible causes - a
durable row, or a session remembering its own uncommitted write - and the
campaign's rule is that such a check has only been half-tested.

Writes only to the demo organization, and only rows tagged with this run's id.
Contacts no source, invokes no collector and opens no socket.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.services.source_collection_scheduler_loop_service import (  # noqa: E402
    CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    cycle_invariant_failures,
    run_scheduler_cycle,
)

TAG = os.environ["NF_G158_TAG"]
ORG = os.environ["NF_G158_ORG"]
T0 = "2026-09-16T12:00:00Z"

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def sources(
    count: int = 3, last_checked: str = "2026-09-01T00:00:00Z"
) -> list[dict[str, object]]:
    """Three blocked sources. Every prerequisite unsatisfied, each by name."""
    return [
        {
            "source_id": f"{TAG}-{index}",
            "check_interval_days": 7,
            "last_checked_at": last_checked,
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for index in range(count)
    ]


def tag_rows(connection) -> int:
    return int(
        connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_source_collection_jobs "
                "WHERE source_id LIKE :pattern"
            ),
            {"pattern": f"{TAG}%"},
        ).scalar()
        or 0
    )


# ---- a cycle with NO connection must write nothing ------------------------
with engine.connect() as connection:
    before = tag_rows(connection)

connectionless = run_scheduler_cycle(now=T0, sources=sources(), organization_id=ORG)

with engine.connect() as connection:
    out["no_connection_rows_written"] = tag_rows(connection) - before
out["no_connection_reported"] = connectionless["rows_written"]
out["no_connection_invariants"] = cycle_invariant_failures(connectionless)

# ---- a cycle WITH a connection, committed ---------------------------------
with engine.begin() as connection:
    first = run_scheduler_cycle(
        now=T0,
        sources=sources(),
        organization_id=ORG,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
out["created"] = first["jobs_enqueued"]
out["cycle_invariants"] = cycle_invariant_failures(first)

# ---- four more cycles must not grow it ------------------------------------
#
# This is the bound the survey argued for: a deterministic id plus a unique
# index, not a cap. If it were wrong, this would be 15 rows rather than 3.
for _ in range(4):
    with engine.begin() as connection:
        again = run_scheduler_cycle(
            now=T0,
            sources=sources(),
            organization_id=ORG,
            mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
            connection=connection,
        )
out["after_five_cycles_created"] = again["jobs_enqueued"]
out["after_five_cycles_deduplicated"] = again["jobs_deduplicated"]
with engine.connect() as connection:
    out["rows_after_five_cycles"] = tag_rows(connection)

# ---- a later slot is different work ---------------------------------------
#
# Last week's missed window and this week's pending one are not the same job,
# and a store that deduplicated them would lose the older one.
with engine.begin() as connection:
    later = run_scheduler_cycle(
        now="2026-10-30T12:00:00Z",
        sources=sources(last_checked="2026-10-20T00:00:00Z"),
        organization_id=ORG,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
out["later_slot_created"] = later["jobs_enqueued"]
with engine.connect() as connection:
    out["rows_with_later_slot"] = tag_rows(connection)

print(json.dumps(out))
