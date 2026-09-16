"""Gate 156E: one scheduler cycle — deterministic, clock-injected, runs nothing.

## A cycle, not a daemon

`run_scheduler_cycle` evaluates every supplied source once and returns counts.
It starts no thread, sleeps for nothing, and holds no loop. Something else
decides when to call it, and in Gate 156 that something is a test, a verifier or
a route.

A daemon would need a timer, and a timer is Gate 159. Building the loop first
and the trigger later means the loop can be proved deterministic before anything
fires it on its own.

## Why not inside the FastAPI lifespan

Gate 102 added a lifespan hook and recorded that nothing is attached to it. This
gate does not attach either, for two reasons worth naming:

```text
a request-scoped scheduler runs only while a request is in flight, which is
not a schedule

a scheduler attached to the web process makes "restart the API" and "skip a
collection window" the same action
```

So the cycle is a callable. Attaching it to a process is Gate 157's question,
and to a trigger Gate 159's.

## The clock is an argument

Every evaluation takes `now`. There is no `datetime.now()` in this module, which
is what makes a cycle reproducible: the same sources and the same instant give
the same counts, and a test can place the clock anywhere without waiting.

## An empty allowlist is not a special case

With zero approved sources, every job evaluates to `blocked` by the ordinary
path and `executable_jobs` is 0 by counting, not by a guard. There is no
`if allowlist_empty: return` branch to get wrong — which matters, because a
guard that special-cases the safe state is a guard that stops working the moment
the state changes.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_job_repository import (
    enqueue_job,
    job_store_invariant_failures,
)
from nativeforge.services.source_collection_job_identity_service import (
    build_job_identity,
    identity_invariant_failures,
)
from nativeforge.services.source_collection_job_model_service import (
    build_collection_job,
    collection_job_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_runtime_service import (
    BLOCKED,
    DISABLED,
    DUE,
    SCHEDULED,
    UNKNOWN,
    WAITING,
)

SCHEMA_VERSION = "nf_source_collection_scheduler_cycle_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: What a cycle is allowed to do in Gate 156.
CYCLE_MODE_EVALUATE_ONLY = "evaluate_only"

#: Gate 158: evaluate, and write what was evaluated to the durable job store.
#:
#: This is the mode that closes the gap Gate 158 measured - a cycle produced one
#: job in memory and wrote zero rows, so queued work did not survive its own
#: process. It needs a connection and an organization, and it still dispatches
#: nothing: a row that says "this needs doing" is not a source that was
#: contacted.
CYCLE_MODE_EVALUATE_AND_ENQUEUE = "evaluate_and_enqueue"

CYCLE_MODES = (CYCLE_MODE_EVALUATE_ONLY, CYCLE_MODE_EVALUATE_AND_ENQUEUE)

#: What it would take to add a mode that runs anything. Named so the absence is
#: a decision rather than an omission.
#:
#: `persist` left this list in Gate 158, which is the only entry that has ever
#: left it.
EXECUTION_MODES_NOT_IMPLEMENTED = (
    "dispatch: needs a collector, which is Gate 161",
    "trigger: needs a timer, which is Gate 159",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def run_scheduler_cycle(
    *,
    now: Any = None,
    sources: list[dict[str, Any]] | None = None,
    organization_id: Any = None,
    mode: str = CYCLE_MODE_EVALUATE_ONLY,
    connection: Any = None,
) -> dict[str, Any]:
    """Evaluate every source once against `now`. Dispatches nothing.

    `sources` is a list of plain dicts, so the caller decides where they came
    from - the registry, a fixture, or a test.

    In `evaluate_only` this module opens no database and the default stays
    `evaluate_only`, so nothing that called this before Gate 158 writes a row
    now. In `evaluate_and_enqueue` it writes to the job store through the
    repository and reports what it actually wrote.
    """
    rows = list(sources or [])
    wants_enqueue = mode == CYCLE_MODE_EVALUATE_AND_ENQUEUE

    jobs: list[dict[str, Any]] = []
    for row in rows:
        jobs.append(
            build_collection_job(
                source_id=row.get("source_id") or row.get("id"),
                organization_id=organization_id or row.get("organization_id"),
                now=now,
                last_checked_at=row.get("last_checked_at"),
                check_interval_days=row.get("check_interval_days"),
                recorded_next_check_due_at=row.get("next_check_due_at"),
                activation_state=row.get("activation_state"),
                terms_state=row.get("terms_state"),
                human_review_state=row.get("human_review_state"),
                is_enabled=row.get("is_enabled"),
                collector_registered=row.get("collector_registered"),
                known_source=bool(row.get("known_source", True)),
                is_demo=row.get("is_demo"),
                fact_status=row.get("fact_status"),
            )
        )

    # ---- persist, if this cycle was asked to -------------------------------
    #
    # Option A from the Gate 158 survey: every evaluated source gets a durable
    # row, including a refused one. A refusal that lives only inside one cycle
    # is a backlog nobody can measure over time, and "how long has this been
    # waiting" is the question that eventually makes someone read the terms.
    #
    # Bounded by the deterministic id plus the unique index, not by a cap: a
    # repeated cycle re-enqueues the same ids and the inserts are refused.
    # Hoisted above the enqueue pass, which contributes to it. Every invariant
    # failure from any phase of the cycle lands in one list.
    failures: list[str] = []

    enqueue_results: list[dict[str, Any]] = []
    enqueue_blocked: list[str] = []
    rows_created = 0
    rows_deduplicated = 0

    if wants_enqueue:
        if connection is None:
            enqueue_blocked.append("enqueue_requested_without_a_connection")
        if not str(organization_id or "").strip():
            enqueue_blocked.append("enqueue_requested_without_an_organization")

    if wants_enqueue and not enqueue_blocked:
        for job in jobs:
            identity = build_job_identity(
                source_id=job["source_id"],
                scheduled_for=job["next_run_at"],
                collector_id=None,
                execution_mode=job["execution_mode"],
            )
            failures.extend(identity_invariant_failures(identity))

            # The store must hold the id the scheduler reports. Gate 158
            # measured these disagreeing - an out-of-vocabulary job_type, and a
            # stray strip() - so the agreement is asserted per job rather than
            # assumed from the fact that both call the same function.
            if identity["job_id"] != job["job_id"]:
                failures.append(
                    f"identity_disagrees_with_the_job_model:{job['source_id']}"
                )

            written = enqueue_job(
                connection=connection,
                organization_id=organization_id,
                job_id=identity["job_id"],
                idempotency_key=identity["idempotency_key"],
                source_id=job["source_id"],
                schedule_key=identity["schedule_key"],
                scheduled_for=job["next_run_at"],
                collection_mode=job["execution_mode"],
                # The scheduler records WHY, and records nothing about outcome.
                # A refused source is enqueued as `queued` carrying its
                # blockers; deciding it is refused is the worker's job.
                blocked_reasons=list(job["blockers"] or []),
                created_by_runtime="scheduler_cycle",
                fact_status=(
                    job["fact_status"]
                    if job["fact_status"] in ("demo_fixture", "verified")
                    else "unknown"
                ),
                now=now,
                is_demo=bool(job["is_demo"]),
            )
            failures.extend(job_store_invariant_failures(written))
            enqueue_results.append(
                {
                    "source_id": job["source_id"],
                    "job_id": identity["job_id"],
                    "created": written["created"],
                    "deduplicated": written["deduplicated"],
                    "blocked_reasons": written["blocked_reasons"],
                }
            )
            if written["created"]:
                rows_created += 1
            if written["deduplicated"]:
                rows_deduplicated += 1
            enqueue_blocked.extend(written["blocked_reasons"])

    by_state = {
        state: sum(1 for job in jobs if job["runtime_state"] == state)
        for state in (SCHEDULED, DUE, WAITING, BLOCKED, DISABLED, UNKNOWN)
    }

    due = [job for job in jobs if job["due"]]
    executable = [job for job in jobs if job["executable"]]
    refused = [job for job in jobs if job["blockers"]]

    # Every distinct reason, counted. An operator asking why nothing ran gets
    # the shape of the answer rather than one example.
    refusal_reasons: dict[str, int] = {}
    for job in refused:
        for blocker in job["blockers"]:
            refusal_reasons[blocker] = refusal_reasons.get(blocker, 0) + 1

    for job in jobs:
        failures.extend(collection_job_invariant_failures(job))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "mode": mode,
            "evaluated_at": now if now is None else str(now),
            "jobs": jobs,
            "jobs_known": len(jobs),
            "jobs_by_state": by_state,
            "jobs_due": len(due),
            # Counted, never guarded. With an empty allowlist this is 0 because
            # every job refused on its own terms.
            "jobs_executable": len(executable),
            "jobs_refused": len(refused),
            "executable_job_ids": sorted(job["job_id"] for job in executable),
            "refusal_reasons": dict(sorted(refusal_reasons.items())),
            "distinct_refusal_reasons": len(refusal_reasons),
            "invariant_failures": sorted(set(failures)),
            "execution_modes_not_implemented": list(EXECUTION_MODES_NOT_IMPLEMENTED),
            # ---- what this cycle persisted --------------------------------
            "enqueue_requested": wants_enqueue,
            "enqueue_performed": bool(wants_enqueue and not enqueue_blocked),
            "enqueue_results": enqueue_results,
            "jobs_enqueued": rows_created,
            "jobs_deduplicated": rows_deduplicated,
            "enqueue_blocked_reasons": sorted(set(enqueue_blocked)),
            # DERIVED. This was a declared 0 through Gate 157, which was true
            # only because the cycle could not write. Counting it instead means
            # a cycle that writes cannot report that it did not.
            "rows_written": rows_created,
            # Constants, and they stay constants. A cycle that writes a row
            # still contacted nothing: persisting is not executing.
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            "raw_payloads_written": 0,
            "source_monitoring_live": False,
            "api_key_required": False,
            "threads_started": 0,
            "clock_is_injected": True,
        }
    )


def cycle_invariant_failures(cycle: dict[str, Any]) -> list[str]:
    """Refuse a cycle that ran something, or counted itself wrong."""
    fails: list[str] = list(cycle.get("invariant_failures") or [])

    jobs = cycle.get("jobs") or []
    if cycle.get("jobs_known") != len(jobs):
        fails.append("jobs_known_disagrees")

    counted_due = sum(1 for job in jobs if job.get("due"))
    if counted_due != cycle.get("jobs_due"):
        fails.append("jobs_due_disagrees")

    counted_executable = sum(1 for job in jobs if job.get("executable"))
    if counted_executable != cycle.get("jobs_executable"):
        fails.append("jobs_executable_disagrees")

    by_state = cycle.get("jobs_by_state") or {}
    if sum(by_state.values()) != len(jobs):
        fails.append("jobs_by_state_does_not_account_for_every_job")

    # An executable job must have survived every prerequisite, and in Gate 156
    # no collector exists, so this list must be empty for a different reason
    # than a guard.
    for job in jobs:
        if job.get("executable") and job.get("blockers"):
            fails.append(f"executable_job_carries_blockers:{job.get('job_id')}")

    if cycle.get("mode") not in CYCLE_MODES:
        fails.append(f"cycle_ran_in_an_unimplemented_mode:{cycle.get('mode')}")

    for flag in ("source_monitoring_live", "api_key_required"):
        if cycle.get(flag):
            fails.append(f"cycle_claimed:{flag}")

    # `rows_written` is deliberately NOT in this list any more. A cycle may
    # write rows; it may not contact anything. Removing it wholesale would have
    # dropped the check, so it is replaced below by an agreement test rather
    # than deleted.
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
        "threads_started",
    ):
        if cycle.get(counter):
            fails.append(f"cycle_counted:{counter}")

    # ---- persistence must agree with itself -------------------------------
    created = int(cycle.get("jobs_enqueued") or 0)
    if int(cycle.get("rows_written") or 0) != created:
        fails.append("rows_written_disagrees_with_jobs_enqueued")

    counted_created = sum(
        1 for r in (cycle.get("enqueue_results") or []) if r.get("created")
    )
    if counted_created != created:
        fails.append("jobs_enqueued_disagrees_with_the_per_job_results")

    counted_dedup = sum(
        1 for r in (cycle.get("enqueue_results") or []) if r.get("deduplicated")
    )
    if counted_dedup != int(cycle.get("jobs_deduplicated") or 0):
        fails.append("jobs_deduplicated_disagrees_with_the_per_job_results")

    # An evaluate_only cycle that wrote anything has done something it was not
    # asked to do.
    if cycle.get("mode") == CYCLE_MODE_EVALUATE_ONLY:
        if int(cycle.get("rows_written") or 0):
            fails.append("evaluate_only_cycle_wrote_rows")
        if cycle.get("enqueue_results"):
            fails.append("evaluate_only_cycle_reported_enqueue_results")

    # A cycle cannot both claim it enqueued and report why it could not.
    if cycle.get("enqueue_performed") and cycle.get("enqueue_blocked_reasons"):
        fails.append("enqueue_reported_success_alongside_blocked_reasons")

    # A row per evaluated job, at most. More than that means the store grew
    # faster than the work it describes.
    if created > len(jobs):
        fails.append("more_rows_written_than_jobs_evaluated")

    if not cycle.get("clock_is_injected"):
        fails.append("cycle_read_the_wall_clock")

    return sorted(set(fails))
