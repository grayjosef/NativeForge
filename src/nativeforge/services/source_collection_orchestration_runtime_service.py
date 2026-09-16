"""The orchestration runtime (Gate 159B).

## What it composes, and what it adds

```text
Gate 156   evaluates every source against an injected clock
Gate 158   persists the durable job lifecycle, idempotently
Gate 157   claims jobs, refuses them, records why
```

All three already worked. What did not exist was anything that ran them in
order, on a cadence, exactly once per slot, surviving a restart. That is the
whole of this module's contribution: ordering, exclusivity and recovery.

It adds no capability to the three gates it calls. After a cycle, the same
sources are blocked for the same reasons, no collector exists, and
`source_monitoring_live` is still false.

## Exactly once per slot

```text
1  evaluate the trigger against the last served slot
2  if it permits, acquire the cycle for this slot   (atomic, unique index)
3  run Gate 156 -> Gate 158 in evaluate_and_enqueue mode
4  run Gate 157 over the persisted backlog
5  release the cycle, recording what it did
```

Step 2 is what makes repeated polling safe. A second process inside the same
slot finds the row present and is told `this_slot_has_already_been_served`; it
reports a suppressed duplicate and does no work. Doc 829 has the measurements.

## A cycle that fires is not a source that was checked

`jobs_completed`, `collectors_invoked` and `live_source_calls` are reported as
zero AND stored as zero in columns the database refuses to let grow
(migration 0045). The orchestrator does not advance `last_checked_at`, because
writing it would assert that a check occurred - the `persisted job !=
execution` rule applied to schedule advancement.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_job_repository import (
    count_backlog,
    job_store_invariant_failures,
)
from nativeforge.repositories.source_collection_orchestration_lock_repository import (
    OUTCOME_COMPLETED,
    acquire_cycle,
    orchestration_lock_invariant_failures,
    read_last_served_slot,
    release_cycle,
)
from nativeforge.services.source_collection_missed_window_service import (
    missed_window_invariant_failures,
    recover_missed_windows,
)
from nativeforge.services.source_collection_orchestration_identity_service import (
    DEFAULT_CADENCE,
    build_orchestration_identity,
    normalize_cadence,
    orchestration_identity_invariant_failures,
)
from nativeforge.services.source_collection_periodic_trigger_service import (
    ALREADY_TRIGGERED,
    DEFAULT_MAX_CATCHUP_SLOTS,
    MISSED_WINDOW,
    evaluate_trigger,
    trigger_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    run_worker_cycle,
    worker_cycle_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_orchestration_cycle_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: What an orchestration cycle is allowed to do. There is one mode, and adding
#: one that dispatched would need a collector, which is Gate 161.
CYCLE_MODE_EVALUATE_AND_PERSIST = "evaluate_and_persist"

MODES_NOT_IMPLEMENTED = (
    "dispatch: needs a collector, which is Gate 161",
    "advance_schedule: needs a real source check, which no gate has built",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _empty_report(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "mode": CYCLE_MODE_EVALUATE_AND_PERSIST,
        "modes_not_implemented": list(MODES_NOT_IMPLEMENTED),
        "ran": False,
        "orchestration_cycle_id": None,
        "owner_id": None,
        "cadence": DEFAULT_CADENCE,
        "slot_index": None,
        "slot_key": None,
        "started_at": None,
        "completed_at": None,
        "trigger_state": None,
        "next_trigger_at": None,
        "sources_seen": 0,
        "schedule_slots_due": 0,
        "jobs_created": 0,
        "jobs_reused": 0,
        "jobs_blocked": 0,
        "jobs_claimed": 0,
        "jobs_refused": 0,
        "jobs_retry_wait": 0,
        "jobs_completed": 0,
        "duplicate_triggers_suppressed": 0,
        "missed_windows_detected": 0,
        "missed_windows_recovered": 0,
        "slots_dropped_by_the_bound": 0,
        "blocked_reasons": [],
        "invariant_failures": [],
        # Constants. A cycle orders existing work; it contacts nothing.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "raw_payloads_written": 0,
        "emails_sent": 0,
        "object_store_calls": 0,
        "threads_started": 0,
        "approved_source_count": 0,
        "last_checked_at_advanced": False,
        "clock_is_injected": True,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    base["invariant_failures"] = sorted(set(base["invariant_failures"] or []))
    return _json_safe(base)


def run_orchestration_cycle(
    *,
    connection: Any = None,
    organization_id: Any = None,
    owner_id: Any = None,
    sources: list[dict[str, Any]] | None = None,
    now: Any = None,
    cadence: Any = DEFAULT_CADENCE,
    trigger_enabled: bool = True,
    max_catchup_slots: int = DEFAULT_MAX_CATCHUP_SLOTS,
    recover_missed: bool = True,
    run_worker: bool = True,
    lease_seconds: int | None = None,
    max_jobs: int = 200,
) -> dict[str, Any]:
    """One orchestration pass. Wakes the scheduler; contacts nothing.

    `sources` is supplied by the caller, as Gate 156 requires - this module
    does not decide where the registry comes from.
    """
    resolved_cadence = normalize_cadence(cadence)
    failures: list[str] = []
    blocked: list[str] = []

    if connection is None:
        blocked.append("no_connection_supplied")
    if not str(owner_id or "").strip():
        blocked.append("no_owner_id_supplied")
    if not str(organization_id or "").strip():
        blocked.append("no_organization_id_supplied")
    if now is None:
        blocked.append("no_clock_supplied")

    identity = build_orchestration_identity(now=now, cadence=resolved_cadence)
    failures.extend(orchestration_identity_invariant_failures(identity))

    if blocked or not identity.get("usable"):
        return _empty_report(
            blocked_reasons=blocked + list(identity.get("blocked_reasons") or []),
            invariant_failures=failures,
            cadence=resolved_cadence,
        )

    # ---- what has already been served -------------------------------------
    history = read_last_served_slot(
        connection=connection,
        organization_id=organization_id,
        cadence=resolved_cadence,
        # Required, or a slot whose owner crashed counts as served and its
        # expired ownership can never be reclaimed.
        now=now,
    )
    failures.extend(orchestration_lock_invariant_failures(history))
    last_served = history.get("last_served_slot_index")

    # ---- should this cycle run at all? ------------------------------------
    trigger = evaluate_trigger(
        now=now,
        last_served_slot_index=last_served,
        cadence=resolved_cadence,
        trigger_enabled=trigger_enabled,
        max_catchup_slots=max_catchup_slots,
    )
    failures.extend(trigger_invariant_failures(trigger))

    common = {
        "cadence": resolved_cadence,
        "owner_id": str(owner_id),
        "orchestration_cycle_id": identity["cycle_id"],
        "slot_index": identity["slot_index"],
        "slot_key": identity["slot_key"],
        "trigger_state": trigger["state"],
        "next_trigger_at": trigger["next_wake_at"],
        "missed_windows_detected": trigger["missed_slot_count"],
        "slots_dropped_by_the_bound": trigger["slots_dropped_by_the_bound"],
        "last_served_slot_index": last_served,
        # A slot whose owner died. Reported so a reclaim is explicable rather
        # than looking like a slot that ran twice.
        "unfinished_slots": history.get("unfinished_slot_count") or 0,
        "served_definition": history.get("served_definition"),
        # The current slot is served by THIS cycle, so recovery excludes it.
        # That is why `missed_windows_recovered` is one less than the bound
        # when the bound is what limited the catch-up.
        "recovery_excludes_the_current_slot": True,
    }

    if not trigger["should_run_a_cycle"]:
        # Not due, already served, or blocked. Reported, and nothing written -
        # the row for an already-served slot is already there.
        return _empty_report(
            **common,
            ran=False,
            duplicate_triggers_suppressed=(
                1 if trigger["state"] == ALREADY_TRIGGERED else 0
            ),
            blocked_reasons=trigger["blocked_reasons"]
            or ([f"trigger_state:{trigger['state']}"]),
            invariant_failures=failures,
        )

    # ---- take the slot, atomically ----------------------------------------
    acquire_kwargs: dict[str, Any] = {
        "connection": connection,
        "organization_id": organization_id,
        "cycle_id": identity["cycle_id"],
        "owner_id": owner_id,
        "cadence": resolved_cadence,
        "slot_index": identity["slot_index"],
        "slot_key": identity["slot_key"],
        "orchestration_version": identity["orchestration_version"],
        "now": now,
    }
    if lease_seconds is not None:
        acquire_kwargs["lease_seconds"] = int(lease_seconds)

    claim = acquire_cycle(**acquire_kwargs)
    failures.extend(orchestration_lock_invariant_failures(claim))

    if not claim["acquired"]:
        # Another process holds or has served this slot. This is the
        # concurrency refusal, and it is named rather than silent.
        return _empty_report(
            **common,
            ran=False,
            duplicate_triggers_suppressed=1 if claim["duplicate_suppressed"] else 0,
            blocked_reasons=claim["blocked_reasons"],
            invariant_failures=failures,
        )

    # ---- owned. Gate 156 -> Gate 158 --------------------------------------
    scheduler = run_scheduler_cycle(
        now=now,
        sources=list(sources or []),
        organization_id=organization_id,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    failures.extend(cycle_invariant_failures(scheduler))

    jobs_created = int(scheduler["jobs_enqueued"])
    jobs_reused = int(scheduler["jobs_deduplicated"])

    # ---- Gate 157 over the persisted backlog ------------------------------
    worker: dict[str, Any] = {}
    if run_worker:
        worker = run_worker_cycle(
            connection=connection,
            organization_id=organization_id,
            worker_id=f"{owner_id}:worker",
            now=now,
            load_jobs_from_store=True,
            max_jobs=int(max_jobs),
        )
        failures.extend(worker_cycle_invariant_failures(worker))

    # ---- missed windows, bounded ------------------------------------------
    recovery: dict[str, Any] = {}
    if recover_missed and trigger["state"] == MISSED_WINDOW:
        # The CURRENT slot is being served by this cycle, so it is excluded
        # from recovery - recovering it would mean acquiring a row this cycle
        # already owns, which the lock would refuse and which would be counted
        # as a suppressed duplicate against ourselves.
        older = [
            index
            for index in trigger["recoverable_slot_indexes"]
            if index != identity["slot_index"]
        ]
        recovery = recover_missed_windows(
            connection=connection,
            organization_id=organization_id,
            owner_id=owner_id,
            recoverable_slot_indexes=older,
            cadence=resolved_cadence,
            now=now,
            slots_dropped_by_the_bound=trigger["slots_dropped_by_the_bound"],
            orchestration_version=identity["orchestration_version"],
            lease_seconds=lease_seconds,
        )
        failures.extend(missed_window_invariant_failures(recovery))

    # ---- the durable backlog, measured ------------------------------------
    backlog = count_backlog(
        connection=connection, organization_id=organization_id
    )
    failures.extend(job_store_invariant_failures(backlog))

    by_status = backlog.get("by_status") or {}

    counters = {
        "sources_seen": int(scheduler["jobs_known"]),
        "jobs_created": jobs_created,
        "jobs_reused": jobs_reused,
        "jobs_blocked": int(scheduler["jobs_refused"]),
        "jobs_claimed": int(worker.get("jobs_claimed") or 0),
        "jobs_refused": int(worker.get("jobs_refused") or 0),
        "missed_windows_recovered": int(recovery.get("slots_recovered") or 0),
        "duplicate_triggers_suppressed": int(
            recovery.get("slots_already_served") or 0
        ),
    }

    done = release_cycle(
        connection=connection,
        organization_id=organization_id,
        cycle_id=identity["cycle_id"],
        owner_id=owner_id,
        now=now,
        outcome=OUTCOME_COMPLETED,
        counters=counters,
    )
    failures.extend(orchestration_lock_invariant_failures(done))

    return _empty_report(
        **common,
        ran=True,
        started_at=(claim["cycle"] or {}).get("started_at"),
        completed_at=(done["cycle"] or {}).get("completed_at"),
        reclaimed_an_expired_owner=bool(claim["reclaimed"]),
        sources_seen=counters["sources_seen"],
        schedule_slots_due=int(scheduler["jobs_due"]),
        jobs_created=jobs_created,
        jobs_reused=jobs_reused,
        jobs_blocked=counters["jobs_blocked"],
        jobs_claimed=counters["jobs_claimed"],
        jobs_refused=counters["jobs_refused"],
        jobs_retry_wait=int(by_status.get("retry_wait") or 0),
        # Read from the store, not declared. If a completed row ever existed
        # this would be nonzero and the invariant checker would fail the cycle.
        jobs_completed=int(backlog.get("completed_total") or 0),
        rows_with_execution_proof=int(
            backlog.get("rows_with_execution_proof") or 0
        ),
        duplicate_triggers_suppressed=counters["duplicate_triggers_suppressed"],
        missed_windows_recovered=counters["missed_windows_recovered"],
        backlog_by_status=by_status,
        scheduler_refusal_reasons=scheduler["refusal_reasons"],
        jobs_executable=int(scheduler["jobs_executable"]),
        invariant_failures=failures,
    )


def orchestration_cycle_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Refuse a cycle that ran something, or counted itself wrong."""
    fails: list[str] = list(report.get("invariant_failures") or [])

    if report.get("mode") != CYCLE_MODE_EVALUATE_AND_PERSIST:
        fails.append(f"cycle_ran_in_an_unimplemented_mode:{report.get('mode')}")

    # A cycle that ran owns a slot and says which.
    if report.get("ran"):
        for field in ("orchestration_cycle_id", "slot_index", "owner_id"):
            if report.get(field) in (None, ""):
                fails.append(f"a_running_cycle_without:{field}")
        if report.get("blocked_reasons"):
            fails.append("ran_alongside_blocked_reasons")
    else:
        # A cycle that did not run says why.
        if not report.get("blocked_reasons"):
            fails.append("did_not_run_without_naming_a_reason")

    # Created and reused are different things, and neither may exceed what was
    # seen. A cycle reporting more created jobs than sources evaluated has
    # invented work.
    seen = int(report.get("sources_seen") or 0)
    created = int(report.get("jobs_created") or 0)
    reused = int(report.get("jobs_reused") or 0)
    if report.get("ran") and created + reused > seen:
        fails.append("created_plus_reused_exceeds_the_sources_evaluated")

    # Recovery cannot recover more than were detected.
    detected = int(report.get("missed_windows_detected") or 0)
    recovered = int(report.get("missed_windows_recovered") or 0)
    if recovered > detected:
        fails.append("recovered_more_windows_than_were_detected")

    # The standing boundary, as constants.
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
        "emails_sent",
        "object_store_calls",
        "threads_started",
        "approved_source_count",
    ):
        if int(report.get(counter) or 0) != 0:
            fails.append(f"cycle_counted:{counter}={report.get(counter)}")

    # And these two, derived from the store rather than declared.
    if int(report.get("jobs_completed") or 0) != 0:
        fails.append(f"cycle_reported_a_completed_job:{report.get('jobs_completed')}")
    if int(report.get("rows_with_execution_proof") or 0) != 0:
        fails.append("cycle_reported_a_row_with_an_execution_proof")

    if report.get("source_monitoring_live"):
        fails.append("cycle_claimed:source_monitoring_live")
    if report.get("last_checked_at_advanced"):
        fails.append("cycle_advanced_last_checked_at")
    if not report.get("clock_is_injected"):
        fails.append("cycle_read_the_wall_clock")

    # An executable job with an empty allowlist would mean a source became
    # runnable without an approval.
    if int(report.get("jobs_executable") or 0) != 0:
        fails.append(
            f"cycle_found_an_executable_job:{report.get('jobs_executable')}"
        )

    return sorted(set(fails))


#: Named so a caller can report the composition rather than infer it.
COMPOSES = (
    "source_collection_periodic_trigger_service.evaluate_trigger",
    "source_collection_orchestration_lock_repository.acquire_cycle",
    "source_collection_scheduler_loop_service.run_scheduler_cycle",
    "source_collection_job_repository.enqueue_job (via the scheduler)",
    "source_collection_worker_runtime_service.run_worker_cycle",
    "source_collection_missed_window_service.recover_missed_windows",
    "source_collection_orchestration_lock_repository.release_cycle",
)
