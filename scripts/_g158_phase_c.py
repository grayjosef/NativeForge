"""Gate 158I phase C: does the worker preserve what the scheduler recorded?

This exists because it did not. Measured during Gate 158:

    as enqueued by the scheduler:
      blocked_reasons=["no_collector_is_registered_for_this_source",
                       "source_activation_not_approved",
                       "source_requires_human_review",
                       "source_terms_not_approved"]

    after the worker recorded its outcome:
      terminal_reason=unknown
      blocked_reasons=["executable_is_not_a_persisted_fact_in_gate_158"]

Four real reasons replaced by one runtime note, and a classifiable class
downgraded to `unknown`, on the FIRST worker pass. The whole argument for
durable refused rows was that somebody could later ask how long 171 sources
have been terms-blocked - and that question had become unanswerable.

So this phase asserts the union, not just the presence of a row.
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
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_runtime_service import (  # noqa: E402
    run_worker_cycle,
    worker_cycle_invariant_failures,
)

TAG = os.environ["NF_G158_TAG"] + "-w"
ORG = os.environ["NF_G158_ORG"]

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}

SOURCES = [
    {
        "source_id": f"{TAG}-0",
        "check_interval_days": 7,
        "last_checked_at": "2026-09-01T00:00:00Z",
        "is_enabled": True,
        "activation_state": "activation_blocked",
        "terms_state": "terms_unknown",
        "human_review_state": "human_review_required",
        "collector_registered": False,
    }
]


def recorded_reasons() -> list[str]:
    with engine.connect() as connection:
        raw = connection.execute(
            sa.text(
                "SELECT blocked_reasons FROM nf_source_collection_jobs "
                "WHERE source_id LIKE :pattern"
            ),
            {"pattern": f"{TAG}%"},
        ).scalar()
    return sorted(json.loads(raw or "[]"))


with engine.begin() as connection:
    run_scheduler_cycle(
        now="2026-09-16T12:00:00Z",
        sources=SOURCES,
        organization_id=ORG,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )

before = recorded_reasons()
out["scheduler_recorded"] = before

with engine.begin() as connection:
    worker = run_worker_cycle(
        connection=connection,
        organization_id=ORG,
        worker_id="nf-verify-158-worker",
        now="2026-09-16T12:05:00Z",
        load_jobs_from_store=True,
    )
out["worker_invariants"] = worker_cycle_invariant_failures(worker)
out["job_rows_transitioned"] = worker["job_rows_transitioned"]

# This phase's OWN row, isolated from whatever else was in the backlog. The
# worker drains the whole organization, which is correct, so the total is not
# a fact about this fixture.
own = [
    result
    for result in worker["results"]
    if str(result.get("source_id") or "").startswith(TAG)
]
out["own_row_results"] = len(own)
out["own_row_transitions"] = sum(
    2 if result.get("job_row_status") else 0 for result in own
)
out["own_row_final_status"] = own[0]["job_row_status"] if own else None
out["jobs_loaded_from_store"] = worker["jobs_loaded_from_store"]
out["jobs_completed"] = worker["jobs_completed"]
out["collectors_invoked"] = worker["collectors_invoked"]
out["live_source_calls"] = worker["live_source_calls"]
out["claimed_means_contacted"] = worker["claimed_job_means_source_contacted"]

with engine.connect() as connection:
    row = (
        connection.execute(
            sa.text(
                "SELECT status, terminal_reason FROM nf_source_collection_jobs "
                "WHERE source_id LIKE :pattern"
            ),
            {"pattern": f"{TAG}%"},
        )
        .mappings()
        .first()
    )
after = recorded_reasons()
out["status_after"] = (row or {}).get("status")
out["terminal_reason_after"] = (row or {}).get("terminal_reason")
out["worker_recorded"] = after

# The union, both directions: nothing the scheduler recorded was dropped, and
# the worker did add its own reason rather than staying silent.
out["worker_kept_them_all"] = set(before).issubset(set(after))
out["worker_added_its_own"] = bool(set(after) - set(before))

print(json.dumps(out))
