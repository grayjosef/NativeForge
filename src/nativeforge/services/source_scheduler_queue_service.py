"""Dry-run source scheduler queue (Gate 99C).

Turns Gate 98B schedule decisions into a queue of jobs. It builds records. It
does not dispatch them, does not fetch, does not call a collector, and does not
write a raw payload.

## A queue is not monitoring

This is the distinction the whole gate rests on. After this service exists, the
repository can produce a list of work that *would* be done. Nothing consumes the
list. `source_monitoring_live` is False on every queue, and
`live_jobs_created` is zero - both derived rather than asserted, so they stop
being zero on their own if a worker ever appears rather than needing somebody to
remember to change them.

## Blocked sources stay in the queue

A source that cannot be checked is queued as a `blocked` job carrying its
reasons, not dropped. Dropping it would make the queue look healthy by omission -
the same shape as a check-run count with no payload behind it, which Gate 98D
exists to prevent. An operator reading this queue needs to see the twenty sources
that are stuck, not the two that are fine.

## Deduplication by idempotency key

Two decisions describing the same work - the same source, collector, job type and
scheduled time - produce one job. The first occurrence in sorted order wins, so
the result does not depend on input order, and the duplicates are counted rather
than silently discarded.

Sorting is by idempotency key, which is a hash: stable across runs, and
independent of whatever order the decisions arrived in. That is what makes the
artifacts regenerate byte-identically.

## live_collection is refused, and the refusal is derived

`allow_live_collection` exists as a parameter and defaults to False. Even set
True it changes nothing today: the job model requires a background worker, Gate
98E detects none, and `live_jobs_created` is counted from the jobs actually
built rather than from what was requested. An invariant fails any queue whose
live count disagrees with its own jobs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.source_scheduler_job_model_service import (
    EXECUTION_MODES,
    JOB_STATUSES,
    LIVE_EXECUTION_MODES,
    NON_EXECUTED_STATUSES,
    build_source_job,
    job_invariant_failures,
)

SCHEMA_VERSION = "nf_source_scheduler_queue_v1"

QUEUE_EXECUTION_MODES = frozenset({"dry_run", "live_collection"})
DEFAULT_QUEUE_EXECUTION_MODE = "dry_run"

# Schedule statuses that produce a job at all. `not_due` and `disabled` sources
# are not queued: there is nothing to do for them, and a job saying so would be
# noise rather than evidence.
QUEUEABLE_SCHEDULE_STATUSES = frozenset(
    {"due_and_safe_to_enqueue", "due_but_blocked", "unknown"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _digest(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join(str(p if p is not None else "") for p in parts).encode("utf-8")
    ).hexdigest()


def build_queue_id(*, scheduled_for: Any, execution_mode: Any, keys: list[str]) -> str:
    """Deterministic from the queue's contents, not from a clock."""
    return _digest(scheduled_for, execution_mode, ",".join(sorted(keys)))


def build_dry_run_queue(
    *,
    decisions: list[dict[str, Any]] | None = None,
    scheduled_for: Any = None,
    created_at: Any = None,
    collector_by_source: dict[str, Any] | None = None,
    job_type: Any = None,
    raw_payload_store_status: Any = None,
    allow_live_collection: bool = False,
) -> dict[str, Any]:
    """Build a queue from schedule decisions. Nothing is dispatched."""
    decisions = list(decisions or [])
    collector_by_source = collector_by_source or {}

    # The mode the queue was asked for. What the jobs actually get is decided by
    # the job model, which requires every live precondition including a worker.
    requested_mode = (
        "live_collection" if allow_live_collection else DEFAULT_QUEUE_EXECUTION_MODE
    )

    considered = 0
    skipped_not_queueable = 0
    built: list[dict[str, Any]] = []

    for decision in decisions:
        considered += 1
        status = decision.get("schedule_status")
        if status not in QUEUEABLE_SCHEDULE_STATUSES:
            skipped_not_queueable += 1
            continue

        source_id = decision.get("source_id")
        resolved = decision.get("resolved_inputs") or {}

        built.append(
            build_source_job(
                source_id=source_id,
                collector_id=collector_by_source.get(source_id),
                job_type=job_type,
                scheduled_for=scheduled_for
                if scheduled_for is not None
                else decision.get("next_check_due_at"),
                created_at=created_at,
                execution_mode=requested_mode,
                activation_status=resolved.get("activation_status"),
                schedule_decision_status=status,
                circuit_status=resolved.get("circuit_status"),
                raw_payload_store_status=_store_status(
                    raw_payload_store_status, resolved
                ),
            )
        )

    # Deduplicate by idempotency key, in a stable order so the result does not
    # depend on how the decisions arrived.
    built.sort(key=lambda j: (j["idempotency_key"], str(j["source_id"])))
    seen: set[str] = set()
    jobs: list[dict[str, Any]] = []
    duplicates = 0
    for job in built:
        key = job["idempotency_key"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        jobs.append(job)

    queued = [j for j in jobs if j["job_status"] == "queued"]
    blocked = [j for j in jobs if j["job_status"] == "blocked"]

    # Counted from the jobs themselves, never from what was requested.
    live_jobs = [j for j in jobs if j["execution_mode"] in LIVE_EXECUTION_MODES]

    blocked_reasons = sorted(
        {reason for job in jobs for reason in job.get("blocked_reasons") or []}
    )

    resolved_mode = (
        "live_collection" if live_jobs else DEFAULT_QUEUE_EXECUTION_MODE
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "queue_id": build_queue_id(
                scheduled_for=scheduled_for,
                execution_mode=resolved_mode,
                keys=sorted(seen),
            ),
            "scheduled_for": scheduled_for,
            "created_at": created_at,
            "execution_mode": resolved_mode,
            "requested_execution_mode": requested_mode,
            "decisions_considered": considered,
            "decisions_not_queueable": skipped_not_queueable,
            "jobs_total": len(jobs),
            "jobs_queued": len(queued),
            "jobs_blocked": len(blocked),
            "jobs_deduplicated": duplicates,
            "live_jobs_created": len(live_jobs),
            "blocked_reasons": blocked_reasons,
            "jobs": jobs,
            # Constants: a queue is a plan, not an activity.
            "dry_run_only": not live_jobs,
            "jobs_dispatched": 0,
            "collectors_executed": False,
            "live_fetch_performed": False,
            "raw_payloads_written": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def _store_status(explicit: Any, resolved: dict[str, Any]) -> Any:
    """Prefer an explicit status; otherwise derive from the decision's inputs."""
    if explicit is not None:
        return explicit
    available = resolved.get("production_raw_payload_store_available")
    if available is True:
        return "production_available"
    if available is False:
        return "unavailable"
    return "unknown"


def summarise_queue(queue: dict[str, Any]) -> dict[str, Any]:
    """A flat summary for artifacts and CLI output. Carries no job bodies."""
    by_status = {status: 0 for status in sorted(JOB_STATUSES)}
    by_mode = {mode: 0 for mode in sorted(EXECUTION_MODES)}
    for job in queue.get("jobs") or []:
        status = job.get("job_status")
        mode = job.get("execution_mode")
        if status in by_status:
            by_status[status] += 1
        if mode in by_mode:
            by_mode[mode] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "queue_id": queue.get("queue_id"),
            "jobs_total": queue.get("jobs_total"),
            "jobs_queued": queue.get("jobs_queued"),
            "jobs_blocked": queue.get("jobs_blocked"),
            "jobs_deduplicated": queue.get("jobs_deduplicated"),
            "live_jobs_created": queue.get("live_jobs_created"),
            "by_job_status": by_status,
            "by_execution_mode": by_mode,
            "blocked_reasons": queue.get("blocked_reasons"),
            "dry_run_only": queue.get("dry_run_only"),
            "jobs_dispatched": 0,
            "collectors_executed": False,
            "live_fetch_performed": False,
            "raw_payloads_written": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def queue_invariant_failures(queue: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if queue.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if queue.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "collectors_executed",
        "live_fetch_performed",
        "raw_payloads_written",
        "source_monitoring_live",
        "live_source_coverage",
    ):
        if queue.get(constant) is not False:
            fails.append(f"queue_claimed:{constant}")
    if queue.get("jobs_dispatched") != 0:
        fails.append("queue_dispatched_jobs")

    jobs = queue.get("jobs")
    if not isinstance(jobs, list):
        fails.append("jobs_not_a_list")
        return fails

    # Every job must satisfy its own invariants. A queue cannot be more honest
    # than the records it contains.
    for job in jobs:
        for failure in job_invariant_failures(job):
            fails.append(f"job_invariant:{failure}")

    # Counts derived from the jobs, never asserted beside them.
    if queue.get("jobs_total") != len(jobs):
        fails.append("jobs_total_disagrees_with_the_jobs")
    if queue.get("jobs_queued") != sum(
        1 for j in jobs if j.get("job_status") == "queued"
    ):
        fails.append("jobs_queued_disagrees_with_the_jobs")
    if queue.get("jobs_blocked") != sum(
        1 for j in jobs if j.get("job_status") == "blocked"
    ):
        fails.append("jobs_blocked_disagrees_with_the_jobs")

    live = sum(1 for j in jobs if j.get("execution_mode") in LIVE_EXECUTION_MODES)
    if queue.get("live_jobs_created") != live:
        fails.append("live_job_count_disagrees_with_the_jobs")
    if queue.get("dry_run_only") != (live == 0):
        fails.append("dry_run_flag_disagrees_with_the_jobs")

    # No job may hold an execution status, and none may be a live job while the
    # queue reports itself dry-run only.
    for job in jobs:
        if job.get("job_status") not in NON_EXECUTED_STATUSES:
            fails.append(f"queue_holds_an_executing_job:{job.get('job_id')}")
        if queue.get("dry_run_only") and job.get("execution_mode") in (
            LIVE_EXECUTION_MODES
        ):
            fails.append(f"live_job_in_a_dry_run_queue:{job.get('job_id')}")

    # Deduplication must have actually happened.
    keys = [j.get("idempotency_key") for j in jobs]
    if len(keys) != len(set(keys)):
        fails.append("duplicate_idempotency_key_in_the_queue")

    duplicates = queue.get("jobs_deduplicated")
    if not isinstance(duplicates, int) or duplicates < 0:
        fails.append("deduplicated_count_not_a_non_negative_int")

    # A blocked job must be represented, not summarised away.
    if queue.get("jobs_blocked") and not queue.get("blocked_reasons"):
        fails.append("blocked_jobs_without_reasons")

    # The queue id must be reproducible from the queue's own contents.
    expected = build_queue_id(
        scheduled_for=queue.get("scheduled_for"),
        execution_mode=queue.get("execution_mode"),
        keys=[k for k in keys if k is not None],
    )
    if queue.get("queue_id") != expected:
        fails.append("queue_id_not_derivable_from_its_contents")

    return fails
