"""Gate 159K: the lane, with the evidence a request cannot produce.

The health route supplies no evidence for `expired_owner_reclaimable`,
`missed_window_recovered` or `restart_is_idempotent`, because a request cannot
kill a process, wait for a lease to lapse, or be two processes across a
restart. It reports those red and names this script.

This is the script. It has separate processes behind it (phases A, B and C all
ran before this one), real committed rows, and a clock it can move, so it can
hand the health service the three the route could not - and the lane goes green
HERE while staying red THERE, which is the honest arrangement.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    count_backlog,
)
from nativeforge.repositories.source_collection_orchestration_lock_repository import (  # noqa: E402
    count_cycles,
    list_stale_owners,
    read_last_served_slot,
)
from nativeforge.services.source_collection_orchestration_health_service import (  # noqa: E402
    NOT_MEASURABLE_BY_A_REQUEST,
    build_orchestration_health,
    orchestration_health_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_identity_service import (  # noqa: E402
    build_orchestration_identity,
    orchestration_identity_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (  # noqa: E402
    run_orchestration_cycle,
)
from nativeforge.services.source_collection_periodic_trigger_service import (  # noqa: E402
    evaluate_trigger,
)

TAG = os.environ["NF_G159_TAG"] + "-h"
ORG = os.environ["NF_G159_ORG"]

#: A fresh cadence window nothing else in this verifier has touched, so the
#: lane is measured on evidence this phase produced rather than on leftovers.
T_FIRST = "2026-12-08T08:00:00Z"
T_SAME_SLOT = "2026-12-08T08:30:00Z"
T_AFTER_GAP = "2026-12-08T12:00:00Z"

engine = sa.create_engine(get_settings().database_url)


def sources() -> list[dict[str, object]]:
    return [
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


def cycle_rows() -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(
                sa.text("SELECT COUNT(*) FROM nf_source_orchestration_cycles")
            ).scalar()
            or 0
        )


# ---- a cycle, and a duplicate in the same slot ---------------------------
first = cycle(T_FIRST, "nf-verify-159-health-a")
duplicate = cycle(T_SAME_SLOT, "nf-verify-159-health-b")

# ---- restart idempotency: the same instant again writes nothing ----------
rows_before_replay = cycle_rows()
cycle(T_FIRST, "nf-verify-159-health-c")
restart_wrote_nothing = cycle_rows() == rows_before_replay

# ---- a missed window, recovered ------------------------------------------
gap = cycle(T_AFTER_GAP, "nf-verify-159-health-a")

# ---- an expired owner, reclaimed -----------------------------------------
#
# A one-minute lease on a later slot, then a reclaim half an hour on.
crashed = cycle(
    "2026-12-08T15:00:00Z", "nf-verify-159-health-dies", lease_seconds=60,
    run_worker=False,
)
with engine.begin() as connection:
    # Put the row back the way a crash would leave it: owned, never released.
    connection.execute(
        sa.text(
            "UPDATE nf_source_orchestration_cycles SET cycle_status='acquired', "
            "released_at=NULL, completed_at=NULL WHERE cycle_id=:cycle_id"
        ),
        {"cycle_id": crashed["orchestration_cycle_id"]},
    )
reclaimed = cycle(
    "2026-12-08T15:30:00Z", "nf-verify-159-health-rescuer", run_worker=False
)

# ---- the lane -------------------------------------------------------------
with engine.connect() as connection:
    history = read_last_served_slot(
        connection=connection, organization_id=ORG, cadence="hourly",
        now=T_AFTER_GAP,
    )
    counts = count_cycles(connection=connection, organization_id=ORG)
    backlog = count_backlog(connection=connection, organization_id=ORG)
    stale = list_stale_owners(
        connection=connection, organization_id=ORG, now=T_AFTER_GAP
    )

trigger = evaluate_trigger(
    now=T_AFTER_GAP,
    last_served_slot_index=history["last_served_slot_index"],
    cadence="hourly",
)
identity_a = build_orchestration_identity(now=T_FIRST)
identity_b = build_orchestration_identity(now=T_FIRST)

health = build_orchestration_health(
    cycle=first,
    trigger=trigger,
    identity_is_deterministic=(
        identity_a["cycle_id"] == identity_b["cycle_id"]
        and not orchestration_identity_invariant_failures(identity_a)
    ),
    duplicate_trigger_result=duplicate,
    concurrent_owner_refused=(
        not duplicate["ran"] and int(duplicate["jobs_created"] or 0) == 0
    ),
    # The three a request cannot produce. This process can.
    expired_owner_reclaimed=bool(reclaimed.get("reclaimed_an_expired_owner")),
    missed_window_result={
        "slots_recovered": gap["missed_windows_recovered"],
        "slots_offered": gap["missed_windows_detected"],
        "slots_dropped_by_the_bound": gap["slots_dropped_by_the_bound"],
        "catchup_was_bounded": bool(gap["slots_dropped_by_the_bound"]),
    },
    restart_recovered_nothing=restart_wrote_nothing,
    cycle_counts=counts,
    backlog=backlog,
    stale_cycle_owners=stale["stale_owner_count"],
    # The verifier reads systemd for this; see the shell script.
    orchestration_process_active=bool(
        os.environ.get("NF_G159_PROCESS_ACTIVE") == "1"
    ),
)

print(
    json.dumps(
        {
            "ready": health["orchestration_runtime_ready"],
            "conditions": health["conditions"],
            "not_met": health["conditions_not_met"],
            "blockers": health["blockers"],
            "invariants": orchestration_health_invariant_failures(health),
            "not_measurable_by_a_request": list(NOT_MEASURABLE_BY_A_REQUEST),
            "jobs_completed": health["jobs_completed"],
            "collectors_invoked": health["collectors_invoked"],
            "live_source_calls": health["live_source_calls"],
            "approved_source_count": health["approved_source_count"],
            "monitoring_live": health["source_monitoring_live"],
            "process_active": health["orchestration_process_active"],
            "duplicate_triggers_suppressed": health[
                "duplicate_triggers_suppressed"
            ],
            "missed_windows_recovered": health["missed_windows_recovered"],
            "total_reclaims": health["total_reclaims"],
            "stale_cycle_owners": health["stale_cycle_owners"],
            "reclaim_happened": bool(reclaimed.get("reclaimed_an_expired_owner")),
            "restart_wrote_nothing": restart_wrote_nothing,
        }
    )
)
