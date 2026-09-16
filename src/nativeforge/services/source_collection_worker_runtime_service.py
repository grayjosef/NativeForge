"""Gate 157B: a worker that claims jobs, records outcomes, and runs nothing.

## What this adds to Gate 100C

`run_dry_run_worker` classifies a list of jobs and returns outcomes. It is a
pure function: no worker identity, no claim, no retry accounting, no
persistence, and nothing that survives a restart. Its own docstring says so — "a
dry-run worker is not a worker".

This adds the four things that make a worker a worker:

```text
identity     an explicit worker_id on every claim and every outcome
claiming     an atomic lease, refused when another worker holds one
retries      bounded, classified, and persisted so a crash cannot reset them
recovery     the lease table is the state; a restarted worker reads it
```

## It does not re-derive permission

Gate 156's scheduler already decided whether a job is `executable`, from
activation, terms, human review, a collector and the clock. This worker reads
that decision and refuses accordingly. It does not recompute it.

A worker that recomputed permission would be a second place for the answer to
live, and two places is how they come to disagree — this campaign's most
frequent defect, found in a delivery guard at Gate 152 and in a next-action
constant at Gate 154.

## A refusal is not a failure

With zero approved sources, every job is refused. That is the worker working:
it claimed the job, asked whether it may run it, was told no, recorded the
reason and released the claim. Nothing failed, nothing retried, and the reason
is on the row.

```text
jobs_claimed    the worker took responsibility for deciding
jobs_refused    it decided no, and said which blocker
jobs_retryable  a transient failure, bounded - zero today
jobs_completed  work finished - zero, because no work can start
```

## No threads, no sockets, no collector

One cycle, one pass, an injectable clock, and a `worker_id` the caller supplies.
Nothing here opens a socket, spawns a thread or imports a collector, and a test
parses this module's AST to prove it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.source_collection_job_lease_service import (
    CLAIMED,
    COMPLETED,
    EXPIRED,
    FAILED,
    PENDING,
    REFUSED,
    RETRYABLE,
    UNKNOWN,
    claim_job,
    lease_invariant_failures,
    record_outcome,
)
from nativeforge.services.source_collection_retry_policy_service import (
    NONE,
    TRANSIENT_WORKER_FAILURE,
    classify_blockers,
    evaluate_retry,
    retry_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_worker_runtime_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

WORKER_STATUSES: tuple[str, ...] = (
    PENDING,
    CLAIMED,
    COMPLETED,
    REFUSED,
    RETRYABLE,
    FAILED,
    EXPIRED,
    UNKNOWN,
)

#: What a Gate 157 worker is allowed to do with a claimed job.
HANDLER_EVALUATE_ONLY = "evaluate_only"

#: There is no live handler, and naming its absence is the point.
HANDLERS_NOT_IMPLEMENTED: tuple[str, ...] = (
    "fetch: needs a collector, which is Gate 161",
    "persist_payload: needs a raw payload store, which is Gate 160",
    "activate: needs an approved source, which is Gate 162 and a human first",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def run_worker_cycle(
    *,
    connection: Any = None,
    organization_id: Any = None,
    worker_id: Any = None,
    jobs: list[dict[str, Any]] | None = None,
    now: Any = None,
    handler: str = HANDLER_EVALUATE_ONLY,
    max_jobs: int = 100,
) -> dict[str, Any]:
    """One worker pass: claim, decide, record, release. Executes nothing.

    `jobs` are the scheduler's output. Their `executable` flag is read, never
    recomputed.
    """
    moment = _as_datetime(now)
    blocked: list[str] = []
    if connection is None:
        blocked.append("no_connection_supplied")
    if not str(worker_id or "").strip():
        blocked.append("no_worker_id_supplied")
    if moment is None:
        blocked.append("no_clock_supplied")
    if handler != HANDLER_EVALUATE_ONLY:
        blocked.append(f"handler_not_implemented:{handler}")

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "worker_id": str(worker_id or "") or None,
                "ran": False,
                "results": [],
                "jobs_seen": 0,
                "jobs_claimed": 0,
                "jobs_completed": 0,
                "jobs_refused": 0,
                "jobs_retryable": 0,
                "jobs_failed": 0,
                "jobs_claim_denied": 0,
                "blocked_reasons": sorted(set(blocked)),
                "invariant_failures": [],
                "collectors_invoked": 0,
                "live_source_calls": 0,
                "network_calls": 0,
                "threads_started": 0,
                "source_monitoring_live": False,
                "api_key_required": False,
            }
        )

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    claim_denied = 0

    offered = list(jobs or [])
    batch = offered[: int(max_jobs)]
    # A batch limit is reasonable. A batch limit nobody can see is how a
    # backlog goes unnoticed, so the truncation is reported rather than
    # inferred from a count that happens to equal the cap.
    truncated = len(offered) - len(batch)

    for job in batch:
        job_id = str(job.get("job_id") or "")
        source_id = str(job.get("source_id") or job_id)

        claim = claim_job(
            connection=connection,
            organization_id=organization_id,
            job_id=job_id,
            source_id=source_id,
            worker_id=worker_id,
            now=now,
        )
        failures.extend(lease_invariant_failures(claim))

        if not claim["claimed"]:
            claim_denied += 1
            results.append(
                {
                    "job_id": job_id,
                    "source_id": source_id,
                    "claimed": False,
                    "status": PENDING,
                    "failure_class": NONE,
                    "blocked_reasons": claim["blocked_reasons"],
                    "should_retry": False,
                    "collector_invoked": False,
                }
            )
            continue

        # Claimed. Now ask the scheduler's verdict - never recompute it.
        executable = bool(job.get("executable"))
        blockers = list(job.get("blockers") or [])

        if executable:
            # There is no handler that can run a job. With zero approved
            # sources this branch is unreachable today, and it is written as a
            # refusal rather than an execution so that it stays safe if a
            # source is ever approved before Gate 161 exists.
            failure_class = NONE
            status = REFUSED
            reasons = ["no_handler_implemented_in_gate_157"]
        else:
            failure_class = classify_blockers(blockers)
            status = REFUSED
            reasons = blockers

        retry = evaluate_retry(
            failure_class=failure_class,
            attempt_count=int((claim.get("lease") or {}).get("attempt_count") or 0),
            max_attempts=int((claim.get("lease") or {}).get("max_attempts") or 3),
            now=now,
        )
        failures.extend(retry_invariant_failures(retry))

        if retry["should_retry"]:
            status = RETRYABLE

        outcome = record_outcome(
            connection=connection,
            organization_id=organization_id,
            job_id=job_id,
            worker_id=worker_id,
            lease_status=status,
            failure_class=failure_class,
            blocked_reasons=reasons,
            now=now,
            next_retry_at=retry["next_retry_at"],
            # An attempt is spent only when something was actually attempted.
            # A refusal costs no attempt, or a job nobody can run would exhaust
            # its budget and then look permanently failed.
            increment_attempt=bool(failure_class == TRANSIENT_WORKER_FAILURE),
        )
        failures.extend(lease_invariant_failures(outcome))

        results.append(
            {
                "job_id": job_id,
                "source_id": source_id,
                "claimed": True,
                "status": status,
                "failure_class": failure_class,
                "blocked_reasons": sorted(set(reasons)),
                "should_retry": retry["should_retry"],
                "why_not_retried": retry["why_not_retried"],
                "next_retry_at": retry["next_retry_at"],
                "collector_invoked": False,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "worker_id": str(worker_id),
            "ran": True,
            "handler": handler,
            "handlers_not_implemented": list(HANDLERS_NOT_IMPLEMENTED),
            "evaluated_at": str(now),
            "results": results,
            "jobs_offered": len(offered),
            "jobs_seen": len(results),
            "jobs_not_reached_this_cycle": truncated,
            "batch_was_truncated": bool(truncated),
            "max_jobs_per_cycle": int(max_jobs),
            "jobs_claimed": sum(1 for r in results if r["claimed"]),
            "jobs_claim_denied": claim_denied,
            "jobs_completed": sum(1 for r in results if r["status"] == COMPLETED),
            "jobs_refused": sum(1 for r in results if r["status"] == REFUSED),
            "jobs_retryable": sum(1 for r in results if r["status"] == RETRYABLE),
            "jobs_failed": sum(1 for r in results if r["status"] == FAILED),
            "blocked_reasons": [],
            "invariant_failures": sorted(set(failures)),
            # Constants. A cycle decides and records.
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            "raw_payloads_written": 0,
            "threads_started": 0,
            "source_monitoring_live": False,
            "api_key_required": False,
            "permission_is_read_not_recomputed": (
                "the scheduler decided `executable`; this worker reads it. Two "
                "places for one answer is how they come to disagree."
            ),
        }
    )


def worker_cycle_invariant_failures(cycle: dict[str, Any]) -> list[str]:
    """Refuse a cycle that ran something, or retried a human blocker."""
    fails: list[str] = list(cycle.get("invariant_failures") or [])

    results = cycle.get("results") or []
    if cycle.get("jobs_seen") != len(results):
        fails.append("jobs_seen_disagrees")

    offered = cycle.get("jobs_offered")
    if offered is not None:
        if len(results) + int(cycle.get("jobs_not_reached_this_cycle") or 0) != int(
            offered
        ):
            fails.append("jobs_offered_does_not_account_for_every_job")
        if bool(cycle.get("batch_was_truncated")) != bool(
            cycle.get("jobs_not_reached_this_cycle")
        ):
            fails.append("truncation_flag_disagrees_with_the_count")

    for name, status in (
        ("jobs_completed", COMPLETED),
        ("jobs_refused", REFUSED),
        ("jobs_retryable", RETRYABLE),
        ("jobs_failed", FAILED),
    ):
        counted = sum(1 for r in results if r.get("status") == status)
        if counted != cycle.get(name):
            fails.append(f"{name}_disagrees")

    for result in results:
        if result.get("status") not in WORKER_STATUSES:
            fails.append(f"status_outside_vocabulary:{result.get('job_id')}")
        # The one that matters: only a transient failure may be retryable.
        if result.get("should_retry") and result.get("failure_class") != (
            TRANSIENT_WORKER_FAILURE
        ):
            fails.append(
                f"retried_a_non_transient_failure:{result.get('failure_class')}"
            )
        if result.get("collector_invoked"):
            fails.append(f"result_claimed_a_collector:{result.get('job_id')}")
        if result.get("status") == COMPLETED:
            fails.append(
                f"a_job_completed_but_no_handler_exists:{result.get('job_id')}"
            )

    if cycle.get("handler") not in (None, HANDLER_EVALUATE_ONLY):
        fails.append(f"cycle_ran_an_unimplemented_handler:{cycle.get('handler')}")

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

    for flag in ("source_monitoring_live", "api_key_required"):
        if cycle.get(flag):
            fails.append(f"cycle_claimed:{flag}")

    return sorted(set(fails))
