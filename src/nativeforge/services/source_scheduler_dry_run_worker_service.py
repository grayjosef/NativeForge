"""Dry-run scheduler worker (Gate 100C).

Consumes Gate 99 queue jobs and marks them. It calls no collector, fetches no
URL, and writes no payload.

## A dry-run worker is not a worker

It is the shape a worker would have, exercised against jobs that cannot run.
Processing a job here means reading it, checking it is the kind of job this
worker is allowed to touch, and recording an outcome. That is all a worker does
*around* the actual work; the actual work is absent, and after this gate it is
still absent.

```text
collectors_executed     false
urls_fetched            false
raw_payloads_written    false
source_monitoring_live  false
```

All four are constants on every result and all four are held by invariants. The
module imports no HTTP client, no collector, and no body store, and a test parses
its AST to prove it - a worker that cannot fetch cannot be quietly promoted into
one that does.

## What it refuses, and why refusing is not the same as skipping

```text
live_collection jobs         refused_live
running/completed/failed     refused_invalid_status
unrecognised execution mode  refused_unknown_mode
```

A refused job is kept in the result with its reason, exactly as Gate 99 keeps
blocked jobs in the queue. A worker that silently dropped the live jobs it would
not run would report a clean sweep over the jobs it liked, which is the shape of
every dishonest green dashboard.

The middle case matters more than it looks. `running`, `completed` and `failed`
describe *execution*, and Gate 99B's invariants already reject a job holding one.
A job arriving here with such a status did not come from Gate 99's queue - it
came from somewhere else, or was edited in between. Either way this worker has no
business touching it, because the one thing it can be sure of is that it does not
know what already happened to that job.

## Two outcomes for the jobs it does process

```text
completed_dry_run   a queued job. Nothing ran; it would have been eligible.
blocked_dry_run     a blocked job. Its reasons are carried through unchanged.
```

`completed_dry_run` is named carefully. It does not mean the check completed - it
means the *dry run* completed, and the distinction is the entire gate. A field
called `completed` would be read as a check having happened within a week of
somebody putting it on a dashboard.

## Deterministic

`worker_run_id` is a sha256 over the queue id and the sorted job ids. The same
queue processed twice yields the same run id, and there is no clock in it - a
timestamp would make the artifacts differ on every run, which is the check that
makes committing them worthwhile.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.source_scheduler_job_model_service import (
    EXECUTION_MODES,
    LIVE_EXECUTION_MODES,
    NON_EXECUTED_STATUSES,
)

SCHEMA_VERSION = "nf_source_scheduler_dry_run_worker_v1"

# What this worker will pick up. Deliberately narrow: `dry_run` only. A
# `replay_fixture` or `manual_review` job is somebody else's business, and
# widening this set is a decision rather than an oversight.
PROCESSABLE_EXECUTION_MODES = frozenset({"dry_run"})

# Input statuses this worker will accept. Bridged from Gate 99B rather than
# restated, so the two cannot drift.
ACCEPTABLE_INPUT_STATUSES = NON_EXECUTED_STATUSES

# Statuses that describe execution. A job carrying one did not come from Gate
# 99's queue, which rejects them by invariant.
EXECUTED_INPUT_STATUSES = frozenset({"running", "completed", "failed"})

WORKER_OUTCOMES = frozenset(
    {
        "completed_dry_run",
        "blocked_dry_run",
        "refused_live",
        "refused_invalid_status",
        "refused_unknown_mode",
        "skipped_not_processable",
    }
)

# Outcomes that mean the worker actually handled the job.
PROCESSED_OUTCOMES = frozenset({"completed_dry_run", "blocked_dry_run"})
REFUSED_OUTCOMES = frozenset(
    {"refused_live", "refused_invalid_status", "refused_unknown_mode"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _digest(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join(str(p if p is not None else "") for p in parts).encode("utf-8")
    ).hexdigest()


def build_worker_run_id(*, queue_id: Any, job_ids: list[str]) -> str:
    """Deterministic from the queue's contents. No clock."""
    return _digest(queue_id, ",".join(sorted(job_ids)))


def _classify(job: dict[str, Any]) -> tuple[str, list[str]]:
    """One job's outcome, and the reasons behind it."""
    mode = job.get("execution_mode")
    status = job.get("job_status")

    # 1. A live job is refused before anything else is considered. It is the
    #    one case where being wrong would put a request on the wire.
    if mode in LIVE_EXECUTION_MODES:
        return "refused_live", [f"live_collection_refused:{mode}"]

    # 2. A mode this worker has not been taught is refused, not assumed safe.
    if mode not in EXECUTION_MODES:
        return "refused_unknown_mode", [f"execution_mode_unrecognised:{mode}"]

    # 3. A status describing execution means this job did not come from Gate
    #    99's queue. What already happened to it is unknown, so it is not
    #    touched.
    if status in EXECUTED_INPUT_STATUSES or status not in ACCEPTABLE_INPUT_STATUSES:
        return "refused_invalid_status", [f"input_status_not_acceptable:{status}"]

    # 4. A mode this worker does not handle - replay_fixture, manual_review -
    #    is left alone rather than claimed.
    if mode not in PROCESSABLE_EXECUTION_MODES:
        return "skipped_not_processable", [f"execution_mode_not_handled:{mode}"]

    # 5. The two real outcomes. Blocked reasons carry through unchanged.
    reasons = list(job.get("blocked_reasons") or [])
    if status == "blocked" or reasons:
        return "blocked_dry_run", reasons or ["job_blocked_without_a_stated_reason"]
    if status == "queued":
        return "completed_dry_run", []
    return "skipped_not_processable", [f"job_status_not_processable:{status}"]


def run_dry_run_worker(
    *,
    queue: dict[str, Any] | None = None,
    jobs: list[dict[str, Any]] | None = None,
    queue_id: Any = None,
) -> dict[str, Any]:
    """Process a dry-run queue. Nothing is fetched, collected, or written."""
    if queue is not None:
        source_jobs = list(queue.get("jobs") or [])
        resolved_queue_id = queue.get("queue_id") if queue_id is None else queue_id
    else:
        source_jobs = list(jobs or [])
        resolved_queue_id = queue_id

    results: list[dict[str, Any]] = []
    for job in source_jobs:
        outcome, reasons = _classify(job)
        results.append(
            {
                "job_id": job.get("job_id"),
                "source_id": job.get("source_id"),
                "job_type": job.get("job_type"),
                "idempotency_key": job.get("idempotency_key"),
                "input_execution_mode": job.get("execution_mode"),
                "input_job_status": job.get("job_status"),
                "outcome": outcome,
                "blocked_reasons": sorted(set(reasons)),
                # Per-job constants. A result is not a check.
                "collector_invoked": False,
                "url_fetched": False,
                "raw_payload_written": False,
            }
        )

    # Stable order so the artifacts regenerate byte-identically.
    results.sort(key=lambda r: (str(r["job_id"]), str(r["source_id"])))

    completed = [r for r in results if r["outcome"] == "completed_dry_run"]
    blocked = [r for r in results if r["outcome"] == "blocked_dry_run"]
    refused_live = [r for r in results if r["outcome"] == "refused_live"]
    refused = [r for r in results if r["outcome"] in REFUSED_OUTCOMES]
    processed = [r for r in results if r["outcome"] in PROCESSED_OUTCOMES]

    blocked_reasons = sorted(
        {reason for r in results for reason in r.get("blocked_reasons") or []}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "worker_run_id": build_worker_run_id(
                queue_id=resolved_queue_id,
                job_ids=[str(r["job_id"]) for r in results],
            ),
            "queue_id": resolved_queue_id,
            "jobs_seen": len(results),
            "jobs_processed": len(processed),
            "jobs_completed_dry_run": len(completed),
            "jobs_blocked_dry_run": len(blocked),
            "live_jobs_refused": len(refused_live),
            "jobs_refused": len(refused),
            "jobs_skipped": len(
                [r for r in results if r["outcome"] == "skipped_not_processable"]
            ),
            "blocked_reasons": blocked_reasons,
            "results": results,
            # The four the gate requires, held by invariants.
            "collectors_executed": False,
            "urls_fetched": False,
            "raw_payloads_written": False,
            "source_monitoring_live": False,
            # And the rest of the boundary.
            "live_source_coverage": False,
            "dry_run_only": True,
            "background_worker_available": False,
            "production_worker_live": False,
            "fabricated": False,
        }
    )


def summarise_worker_run(result: dict[str, Any]) -> dict[str, Any]:
    """A flat summary for artifacts and CLI output. Carries no job bodies."""
    by_outcome = {outcome: 0 for outcome in sorted(WORKER_OUTCOMES)}
    for row in result.get("results") or []:
        outcome = row.get("outcome")
        if outcome in by_outcome:
            by_outcome[outcome] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "worker_run_id": result.get("worker_run_id"),
            "queue_id": result.get("queue_id"),
            "jobs_seen": result.get("jobs_seen"),
            "jobs_processed": result.get("jobs_processed"),
            "jobs_completed_dry_run": result.get("jobs_completed_dry_run"),
            "jobs_blocked_dry_run": result.get("jobs_blocked_dry_run"),
            "live_jobs_refused": result.get("live_jobs_refused"),
            "by_outcome": by_outcome,
            "blocked_reasons": result.get("blocked_reasons"),
            "collectors_executed": False,
            "urls_fetched": False,
            "raw_payloads_written": False,
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "dry_run_only": True,
            "fabricated": False,
        }
    )


def worker_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # The four the gate requires, plus the rest of the boundary.
    for constant in (
        "collectors_executed",
        "urls_fetched",
        "raw_payloads_written",
        "source_monitoring_live",
        "live_source_coverage",
        "background_worker_available",
        "production_worker_live",
    ):
        if result.get(constant) is not False:
            fails.append(f"worker_claimed:{constant}")
    if result.get("dry_run_only") is not True:
        fails.append("worker_not_marked_dry_run_only")

    rows = result.get("results")
    if not isinstance(rows, list):
        fails.append("results_not_a_list")
        return fails

    for row in rows:
        outcome = row.get("outcome")
        if outcome not in WORKER_OUTCOMES:
            fails.append(f"outcome_out_of_vocabulary:{outcome}")
        for constant in ("collector_invoked", "url_fetched", "raw_payload_written"):
            if row.get(constant) is not False:
                fails.append(f"result_claimed:{constant}:{row.get('job_id')}")

        # A live job may never be reported as processed.
        if row.get("input_execution_mode") in LIVE_EXECUTION_MODES:
            if outcome != "refused_live":
                fails.append(f"live_job_not_refused:{row.get('job_id')}")

        # A job that arrived mid-execution may never be processed.
        if row.get("input_job_status") in EXECUTED_INPUT_STATUSES:
            if outcome in PROCESSED_OUTCOMES:
                fails.append(f"executed_job_processed:{row.get('job_id')}")

        # A refusal or a block must say why.
        if outcome in REFUSED_OUTCOMES | {"blocked_dry_run"}:
            if not row.get("blocked_reasons"):
                fails.append(f"outcome_without_a_reason:{row.get('job_id')}")

        # A completed dry run must have had nothing wrong with it.
        if outcome == "completed_dry_run" and row.get("blocked_reasons"):
            fails.append(f"completed_with_blocking_reasons:{row.get('job_id')}")

    # Counts derived from the rows, never asserted beside them.
    if result.get("jobs_seen") != len(rows):
        fails.append("jobs_seen_disagrees_with_the_results")
    for key, outcomes in (
        ("jobs_completed_dry_run", {"completed_dry_run"}),
        ("jobs_blocked_dry_run", {"blocked_dry_run"}),
        ("live_jobs_refused", {"refused_live"}),
        ("jobs_processed", PROCESSED_OUTCOMES),
        ("jobs_refused", REFUSED_OUTCOMES),
    ):
        expected = sum(1 for r in rows if r.get("outcome") in outcomes)
        if result.get(key) != expected:
            fails.append(f"{key}_disagrees_with_the_results")

    # Blocked reasons must be carried through, not summarised away.
    row_reasons = {
        reason for r in rows for reason in r.get("blocked_reasons") or []
    }
    if row_reasons - set(result.get("blocked_reasons") or []):
        fails.append("blocked_reasons_dropped_from_the_summary")

    # The run id must be reproducible from what was processed.
    expected_id = build_worker_run_id(
        queue_id=result.get("queue_id"),
        job_ids=[str(r.get("job_id")) for r in rows],
    )
    if result.get("worker_run_id") != expected_id:
        fails.append("worker_run_id_not_derivable_from_its_results")

    return fails
