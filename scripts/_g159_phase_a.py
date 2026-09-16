"""Gate 159K phase A: a cycle runs, and a second one in the same slot does not.

Committed, so phase B is reading rows this process wrote and then exited -
which is what makes the restart claim a measurement rather than a session
remembering itself.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa  # noqa: E402

from nativeforge.lib.settings import get_settings  # noqa: E402
from nativeforge.services.source_collection_orchestration_identity_service import (  # noqa: E402
    build_orchestration_identity,
    orchestration_identity_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (  # noqa: E402
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)

TAG = os.environ["NF_G159_TAG"]
ORG = os.environ["NF_G159_ORG"]

#: Three fixed instants, all inside one hourly slot except the last.
T_SLOT_START = "2026-09-16T12:00:00Z"
T_SLOT_LATE = "2026-09-16T12:59:59Z"

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


# ---- identity determinism -------------------------------------------------
same_a = build_orchestration_identity(now=T_SLOT_START)
same_b = build_orchestration_identity(now=T_SLOT_LATE)
other = build_orchestration_identity(now="2026-09-16T13:00:00Z")
out["same_slot_same_id"] = same_a["cycle_id"] == same_b["cycle_id"]
out["different_slot_different_id"] = same_a["cycle_id"] != other["cycle_id"]
out["identity_invariants"] = orchestration_identity_invariant_failures(same_a)
out["cycle_id_is_a_job_id"] = same_a["is_a_collection_job_id"]

# ---- one cycle ------------------------------------------------------------
first = cycle(T_SLOT_START, "nf-verify-159-owner-a")
out["first_ran"] = first["ran"]
out["first_trigger_state"] = first["trigger_state"]
out["first_slot_index"] = first["slot_index"]
out["first_cycle_id"] = first["orchestration_cycle_id"]
out["sources_seen"] = first["sources_seen"]
out["jobs_created"] = first["jobs_created"]
out["jobs_blocked"] = first["jobs_blocked"]
out["jobs_claimed"] = first["jobs_claimed"]
out["jobs_refused"] = first["jobs_refused"]
out["jobs_completed"] = first["jobs_completed"]
out["jobs_executable"] = first["jobs_executable"]
out["collectors_invoked"] = first["collectors_invoked"]
out["live_source_calls"] = first["live_source_calls"]
out["source_monitoring_live"] = first["source_monitoring_live"]
out["first_invariants"] = orchestration_cycle_invariant_failures(first)
out["jobs_after_first"] = tagged_jobs()
out["cycle_rows_after_first"] = cycle_rows()
out["refusal_reasons"] = sorted(first["scheduler_refusal_reasons"])

# ---- DUPLICATE TRIGGER: same slot, same owner, later in the window --------
duplicate = cycle(T_SLOT_LATE, "nf-verify-159-owner-a")
out["duplicate_ran"] = duplicate["ran"]
out["duplicate_state"] = duplicate["trigger_state"]
out["duplicate_suppressed"] = duplicate["duplicate_triggers_suppressed"]
out["duplicate_created"] = duplicate["jobs_created"]
out["jobs_after_duplicate"] = tagged_jobs()
out["cycle_rows_after_duplicate"] = cycle_rows()

# ---- CONCURRENCY: same slot, a DIFFERENT owner ---------------------------
concurrent = cycle(T_SLOT_START, "nf-verify-159-owner-b")
out["concurrent_ran"] = concurrent["ran"]
out["concurrent_state"] = concurrent["trigger_state"]
out["concurrent_suppressed"] = concurrent["duplicate_triggers_suppressed"]
out["concurrent_created"] = concurrent["jobs_created"]
out["cycle_rows_after_concurrent"] = cycle_rows()

# ---- a LATER slot runs, and reuses the same work -------------------------
later = cycle("2026-09-16T13:00:00Z", "nf-verify-159-owner-a")
out["later_ran"] = later["ran"]
out["later_created"] = later["jobs_created"]
out["later_reused"] = later["jobs_reused"]
out["jobs_after_later"] = tagged_jobs()
out["cycle_rows_after_later"] = cycle_rows()
out["later_invariants"] = orchestration_cycle_invariant_failures(later)

print(json.dumps(out))
