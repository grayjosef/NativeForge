"""Gate 159K phase B: the restart, the missed window, and the bound.

A SEPARATE process from phase A. Nothing phase A held is in memory here, so the
rows this reads were committed by a process that has since exited - which is
what makes "survives a restart" a measurement rather than a session remembering
its own writes.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_orchestration_lock_repository import (  # noqa: E402
    count_cycles,
    orchestration_lock_invariant_failures,
    read_last_served_slot,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (  # noqa: E402
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)

TAG = os.environ["NF_G159_TAG"]
ORG = os.environ["NF_G159_ORG"]

engine = sa.create_engine(get_settings().database_url)
out: dict[str, object] = {}


def sources(count: int = 3) -> list[dict[str, object]]:
    return [
        {
            "source_id": f"{TAG}-{index}",
            "check_interval_days": 7,
            "last_checked_at": "2026-09-01T00:00:00Z",
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for index in range(count)
    ]


def cycle(now: str, owner: str, **kwargs) -> dict:
    with engine.begin() as connection:
        return run_orchestration_cycle(
            connection=connection,
            organization_id=ORG,
            owner_id=owner,
            sources=sources(),
            now=now,
            **kwargs,
        )


def tagged_jobs() -> int:
    with engine.connect() as connection:
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


def cycle_rows() -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                sa.text("SELECT COUNT(*) FROM nf_source_orchestration_cycles")
            ).scalar()
            or 0
        )


# ---- what a new process finds ---------------------------------------------
with engine.connect() as connection:
    history = read_last_served_slot(
        connection=connection, organization_id=ORG, cadence="hourly",
        now="2026-09-16T13:30:00Z",
    )
out["rows_found_after_restart"] = history["cycles_recorded"]
out["last_served_slot_index"] = history["last_served_slot_index"]
out["served_definition"] = history["served_definition"]
out["unfinished_slots"] = history["unfinished_slot_count"]
out["history_invariants"] = orchestration_lock_invariant_failures(history)
out["jobs_found_after_restart"] = tagged_jobs()

# ---- RESTART IDEMPOTENCY: re-run an already-served slot -------------------
before_rows = cycle_rows()
replay = cycle("2026-09-16T13:00:00Z", "nf-verify-159-restarted")
out["restart_ran"] = replay["ran"]
out["restart_state"] = replay["trigger_state"]
out["restart_suppressed"] = replay["duplicate_triggers_suppressed"]
out["restart_created"] = replay["jobs_created"]
out["cycle_rows_before_restart"] = before_rows
out["cycle_rows_after_restart"] = cycle_rows()
out["restart_wrote_nothing"] = cycle_rows() == before_rows

# ---- MISSED WINDOW: five hours later --------------------------------------
jobs_before_recovery = tagged_jobs()
missed = cycle("2026-09-16T18:00:00Z", "nf-verify-159-owner-a")
out["missed_ran"] = missed["ran"]
out["missed_state"] = missed["trigger_state"]
out["missed_detected"] = missed["missed_windows_detected"]
out["missed_recovered"] = missed["missed_windows_recovered"]
out["missed_dropped"] = missed["slots_dropped_by_the_bound"]
out["missed_created"] = missed["jobs_created"]
out["missed_reused"] = missed["jobs_reused"]
out["jobs_before_recovery"] = jobs_before_recovery
out["jobs_after_recovery"] = tagged_jobs()
# Recovery must not invent work: the source slot has not moved, so every
# recovered orchestration slot computes the same Gate 158 job ids.
out["recovery_invented_no_jobs"] = tagged_jobs() == jobs_before_recovery
out["missed_invariants"] = orchestration_cycle_invariant_failures(missed)

# ---- recovering the SAME outage twice must recover nothing ---------------
rows_after_recovery = cycle_rows()
again = cycle("2026-09-16T18:00:00Z", "nf-verify-159-owner-a")
out["second_recovery_ran"] = again["ran"]
out["second_recovery_recovered"] = again["missed_windows_recovered"]
out["cycle_rows_after_second_recovery"] = cycle_rows()
out["second_recovery_wrote_nothing"] = cycle_rows() == rows_after_recovery

# ---- BOUNDED CATCH-UP: a thirty-hour outage, bound of four ---------------
bounded = cycle(
    "2026-09-18T00:00:00Z", "nf-verify-159-owner-a", max_catchup_slots=4
)
out["bounded_state"] = bounded["trigger_state"]
out["bounded_detected"] = bounded["missed_windows_detected"]
out["bounded_recovered"] = bounded["missed_windows_recovered"]
out["bounded_dropped"] = bounded["slots_dropped_by_the_bound"]
out["bound_held"] = int(bounded["missed_windows_recovered"] or 0) <= 4
out["bounded_invariants"] = orchestration_cycle_invariant_failures(bounded)

# ---- blocked sources stayed blocked, all the way through ----------------
with engine.connect() as connection:
    rows = list(
        connection.execute(
            sa.text(
                "SELECT status, terminal_reason, blocked_reasons "
                "FROM nf_source_collection_jobs WHERE source_id LIKE :pattern"
            ),
            {"pattern": f"{TAG}%"},
        ).mappings()
    )
reasons: set[str] = set()
for row in rows:
    reasons.update(json.loads(row["blocked_reasons"] or "[]"))
out["job_rows"] = len(rows)
out["job_statuses"] = sorted({row["status"] for row in rows})
out["terminal_reasons"] = sorted({row["terminal_reason"] for row in rows})
out["all_blocked_reasons"] = sorted(reasons)
out["terms_still_blocked"] = "source_terms_not_approved" in reasons
out["human_review_still_blocked"] = "source_requires_human_review" in reasons
out["activation_still_blocked"] = "source_activation_not_approved" in reasons

# ---- nothing was collected, counted -------------------------------------
with engine.connect() as connection:
    counts = count_cycles(connection=connection, organization_id=ORG)
out["cycles_total"] = counts["total"]
out["cycles_by_status"] = counts["by_status"]
out["rows_claiming_a_completion"] = counts["rows_claiming_a_completion"]
out["rows_claiming_a_collector"] = counts["rows_claiming_a_collector"]
out["rows_claiming_a_live_call"] = counts["rows_claiming_a_live_call"]
out["count_invariants"] = orchestration_lock_invariant_failures(counts)

# ---- the database refuses a cycle that claims a collector ---------------
#
# The repository never writes anything but zero, so the only way to ask
# whether the CHECK is real is to go around it.
try:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "UPDATE nf_source_orchestration_cycles SET collectors_invoked = 1"
            )
        )
    out["database_refused_a_collector_claim"] = False
except Exception as exc:  # noqa: BLE001 - the refusal is the measurement
    out["database_refused_a_collector_claim"] = True
    out["database_refusal"] = type(exc).__name__

print(json.dumps(out))
