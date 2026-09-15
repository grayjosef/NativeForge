"""Gate 156F: scheduler health — runtime ready, monitoring still off.

## The one sentence this lane exists to keep apart

```text
scheduler_runtime_ready   the machinery to evaluate a schedule exists and a
                          cycle runs deterministically

source_monitoring_live    something is polling a source
```

The first may become true in Gate 156. The second is a constant `False` with no
branch that computes it, and an invariant fails if it is ever anything else.

A runtime that can evaluate 177 sources and refuse all 177 is exactly as far
from monitoring as a runtime that does not exist — it is just honest about
which of the two it is.

## `scheduler_runtime_ready` requires a cycle to have run

Not "the modules import". Gate 98E already detects importability, and an import
proves a file is syntactically valid, not that it evaluates anything. This lane
requires a cycle result: jobs counted, states assigned, invariants clean.

## Zero executable jobs is the expected answer, not a failure

With 171 sources terms-blocked, 6 human-review-blocked and 0 approved, every
job refuses. `jobs_executable: 0` is what a correct scheduler reports today, and
this lane is ready anyway — readiness is about the machinery, not about whether
anything is permitted to run through it.

If `jobs_executable` were ever non-zero while `source_monitoring_live` is false,
that would be a finding, and it is one an invariant catches.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_scheduler_loop_service import (
    cycle_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_scheduler_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Every condition, each established by a cycle that ran.
CONDITIONS: tuple[str, ...] = (
    "runtime_module_evaluates",
    "cycle_completed",
    "every_job_has_a_state",
    "clock_is_injected",
    "no_collector_invoked",
    "no_live_source_call",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "runtime_module_evaluates": (
        "a next run time was computed from an interval and a last check - the "
        "one thing Gates 98-100 do not do"
    ),
    "cycle_completed": "a cycle returned counts and its own invariants were clean",
    "every_job_has_a_state": (
        "jobs_by_state accounts for every job; a job with no state would mean "
        "the evaluator fell through"
    ),
    "clock_is_injected": (
        "there is no datetime.now() in the runtime or the loop, so the same "
        "inputs give the same counts"
    ),
    "no_collector_invoked": "collectors_invoked is 0 and no code path can reach one",
    "no_live_source_call": (
        "live_source_calls is 0; with zero approved sources there is no URL to "
        "fetch even if something wanted to"
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_scheduler_health(
    *,
    cycle: dict[str, Any] | None = None,
    scheduler_process_active: Any = None,
    persistent_state_available: Any = None,
    activation_allowlist_count: Any = None,
) -> dict[str, Any]:
    """Report the lane from a cycle that ran. Measures nothing itself."""
    result = cycle or {}
    cycle_failures = (
        cycle_invariant_failures(result) if cycle else ["no_cycle_supplied"]
    )

    by_state = result.get("jobs_by_state") or {}
    jobs_known = int(result.get("jobs_known") or 0)

    measured = {
        "runtime_module_evaluates": bool(cycle) and "jobs" in result,
        "cycle_completed": bool(cycle) and not cycle_failures,
        "every_job_has_a_state": bool(cycle) and sum(by_state.values()) == jobs_known,
        "clock_is_injected": bool(result.get("clock_is_injected")),
        "no_collector_invoked": int(result.get("collectors_invoked") or 0) == 0,
        "no_live_source_call": int(result.get("live_source_calls") or 0) == 0,
    }

    missing = [name for name in CONDITIONS if not measured[name]]
    blockers = sorted(
        {
            *(f"condition_not_met:{name}" for name in missing),
            *(f"cycle_invariant:{name}" for name in cycle_failures),
        }
    )

    ready = not blockers

    jobs_executable = int(result.get("jobs_executable") or 0)
    allowlist = int(activation_allowlist_count or 0)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived from the cycle. Never supplied.
            "scheduler_runtime_ready": ready,
            "conditions": list(CONDITIONS),
            "conditions_met": measured,
            "conditions_missing": missing,
            "condition_evidence": dict(CONDITION_EVIDENCE),
            "blockers": blockers,
            # `None` means nobody measured it. A scheduler process is Gate 157.
            "scheduler_process_active": (
                None
                if scheduler_process_active is None
                else bool(scheduler_process_active)
            ),
            "scheduler_process_is_gate_157": True,
            "persistent_state_available": (
                None
                if persistent_state_available is None
                else bool(persistent_state_available)
            ),
            "persistent_state_note": (
                "nf_opportunity_sources already carries check_interval_days, "
                "next_check_due_at and last_checked_at. No new table was added "
                "and alembic head is unchanged."
            ),
            "jobs_known": jobs_known,
            "jobs_due": int(result.get("jobs_due") or 0),
            "jobs_executable": jobs_executable,
            "jobs_blocked": int(result.get("jobs_refused") or 0),
            "jobs_by_state": dict(by_state),
            "refusal_reasons": dict(result.get("refusal_reasons") or {}),
            "activation_allowlist_count": allowlist,
            "live_source_calls": int(result.get("live_source_calls") or 0),
            "collectors_invoked": int(result.get("collectors_invoked") or 0),
            "network_calls": int(result.get("network_calls") or 0),
            # The constant this whole gate is built around.
            "source_monitoring_live": False,
            "runtime_ready_is_not_monitoring_live": (
                "scheduler_runtime_ready says the machinery evaluates a "
                "schedule. source_monitoring_live says something is polling a "
                "source. Nothing is. With 0 approved sources every job refuses."
            ),
            "api_key_required": False,
            "rows_written": 0,
        }
    )


def scheduler_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that confused a runtime with live monitoring."""
    fails: list[str] = []

    if health.get("scheduler_runtime_ready"):
        if health.get("blockers"):
            fails.append("ready_alongside_blockers")
        for name in CONDITIONS:
            if not (health.get("conditions_met") or {}).get(name):
                fails.append(f"ready_without:{name}")

    # The one that matters: a runtime being ready must never imply monitoring.
    if health.get("source_monitoring_live"):
        fails.append("source_monitoring_live_became_true")

    # An executable job while nothing is approved would mean the allowlist gate
    # failed open.
    if int(health.get("jobs_executable") or 0) > int(
        health.get("activation_allowlist_count") or 0
    ):
        fails.append("more_executable_jobs_than_approved_sources")

    if int(health.get("jobs_executable") or 0) and not health.get(
        "activation_allowlist_count"
    ):
        fails.append("executable_jobs_with_an_empty_allowlist")

    for counter in (
        "live_source_calls",
        "collectors_invoked",
        "network_calls",
        "rows_written",
    ):
        if health.get(counter):
            fails.append(f"health_counted:{counter}")

    if health.get("api_key_required"):
        fails.append("health_claimed:api_key_required")

    by_state = health.get("jobs_by_state") or {}
    if by_state and sum(by_state.values()) != int(health.get("jobs_known") or 0):
        fails.append("jobs_by_state_does_not_account_for_every_job")

    return sorted(set(fails))
