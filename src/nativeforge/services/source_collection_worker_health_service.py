"""Gate 157G: worker health — ready, and still polling nothing.

```text
worker_runtime_ready     a worker claims jobs, records outcomes, and recovers
source_monitoring_live   something is polling a source
```

The first may become true. The second is a constant `False` with no branch that
computes it, exactly as in Gate 156's scheduler health, and an invariant refuses
any report where it is true.

## Ready means it did the four things, not that the modules import

```text
cycle_completed          a cycle ran and its invariants were clean
claim_is_atomic          a duplicate claim was refused
expired_lease_reclaimed  a lease past its expiry was taken by another worker
retries_are_bounded      a retry decision respected the attempt budget
only_transient_retries   no activation, terms or human-review refusal retried
no_collector_invoked     zero, and no path reaches one
```

Gate 98E already detects importability. An import proves a file parses.

## Zero completed jobs is the expected answer

No handler exists that can run a job, so `jobs_completed` is 0 and an invariant
fails if it is ever anything else. A completed job in Gate 157 would mean
something ran, and nothing can.

`jobs_refused` carrying the whole count is the worker working: it claimed each
job, asked whether it may run it, was told no, and recorded why.

## Stale leases are reported, not swept

A lease past its expiry with an owner still on it means a worker died holding a
claim. It is counted here and reclaimable by the next worker. Nothing sweeps
them on a timer, because a sweeper is a scheduled job and Gate 159 owns
triggers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_retry_policy_service import (
    TRANSIENT_WORKER_FAILURE,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    worker_cycle_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_worker_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

CONDITIONS: tuple[str, ...] = (
    "cycle_completed",
    "claim_is_atomic",
    "expired_lease_reclaimed",
    "retries_are_bounded",
    "only_transient_retries",
    "no_collector_invoked",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "cycle_completed": "a worker cycle ran and its own invariants were clean",
    "claim_is_atomic": (
        "a second worker's claim on a held job was refused, by a unique index "
        "rather than by a check with a race window in front of it"
    ),
    "expired_lease_reclaimed": (
        "a lease past its expiry was taken by another worker, so a worker that "
        "dies holding a claim does not block a job forever"
    ),
    "retries_are_bounded": (
        "a retry decision at the attempt budget returned should_retry false"
    ),
    "only_transient_retries": (
        "activation, terms and human-review refusals are not retried. Retrying "
        "them would burn the budget on jobs no worker can ever run."
    ),
    "no_collector_invoked": "zero, and no code path in this gate reaches one",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_worker_health(
    *,
    cycle: dict[str, Any] | None = None,
    duplicate_claim_refused: Any = None,
    expired_lease_reclaimed: Any = None,
    retry_bounded: Any = None,
    worker_process_active: Any = None,
    jobs_available: Any = None,
    jobs_claimable: Any = None,
    stale_leases: Any = None,
    activation_allowlist_count: Any = None,
) -> dict[str, Any]:
    """Report the lane from a cycle that ran. Measures nothing itself."""
    result = cycle or {}
    cycle_failures = (
        worker_cycle_invariant_failures(result) if cycle else ["no_cycle_supplied"]
    )

    results = result.get("results") or []
    non_transient_retried = [
        r.get("job_id")
        for r in results
        if r.get("should_retry") and r.get("failure_class") != TRANSIENT_WORKER_FAILURE
    ]

    measured = {
        "cycle_completed": bool(cycle) and not cycle_failures,
        "claim_is_atomic": bool(duplicate_claim_refused),
        "expired_lease_reclaimed": bool(expired_lease_reclaimed),
        "retries_are_bounded": bool(retry_bounded),
        "only_transient_retries": not non_transient_retried,
        "no_collector_invoked": int(result.get("collectors_invoked") or 0) == 0,
    }

    missing = [name for name in CONDITIONS if not measured[name]]
    blockers = sorted(
        {
            *(f"condition_not_met:{name}" for name in missing),
            *(f"cycle_invariant:{name}" for name in cycle_failures),
        }
    )

    ready = not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # Derived from the cycle. Never supplied.
            "worker_runtime_ready": ready,
            "conditions": list(CONDITIONS),
            "conditions_met": measured,
            "conditions_missing": missing,
            "condition_evidence": dict(CONDITION_EVIDENCE),
            "blockers": blockers,
            # `None` means nobody measured it. A long-running process is a
            # deployment fact, and a request cannot know it without a shell.
            "worker_process_active": (
                None if worker_process_active is None else bool(worker_process_active)
            ),
            "worker_process_note": (
                "scripts/run_source_collection_worker.py runs one cycle and "
                "exits. No unit is installed or enabled."
            ),
            "worker_id": result.get("worker_id"),
            "jobs_available": int(jobs_available or 0),
            "jobs_claimable": int(jobs_claimable or 0),
            "jobs_claimed": int(result.get("jobs_claimed") or 0),
            "jobs_claim_denied": int(result.get("jobs_claim_denied") or 0),
            "jobs_completed": int(result.get("jobs_completed") or 0),
            "jobs_refused": int(result.get("jobs_refused") or 0),
            "jobs_retryable": int(result.get("jobs_retryable") or 0),
            "jobs_failed": int(result.get("jobs_failed") or 0),
            "stale_leases": int(stale_leases or 0),
            "activation_allowlist_count": int(activation_allowlist_count or 0),
            "non_transient_jobs_marked_retryable": sorted(
                x for x in non_transient_retried if x
            ),
            "live_source_calls": int(result.get("live_source_calls") or 0),
            "collectors_invoked": int(result.get("collectors_invoked") or 0),
            "network_calls": int(result.get("network_calls") or 0),
            # The constant the whole block is built around.
            "source_monitoring_live": False,
            "worker_ready_is_not_monitoring_live": (
                "worker_runtime_ready says a worker claims jobs and records "
                "outcomes. source_monitoring_live says something is polling a "
                "source. Nothing is: every job refuses, because none is "
                "approved."
            ),
            "api_key_required": False,
        }
    )


def worker_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that confused a worker with live monitoring."""
    fails: list[str] = []

    if health.get("worker_runtime_ready"):
        if health.get("blockers"):
            fails.append("ready_alongside_blockers")
        for name in CONDITIONS:
            if not (health.get("conditions_met") or {}).get(name):
                fails.append(f"ready_without:{name}")

    if health.get("source_monitoring_live"):
        fails.append("source_monitoring_live_became_true")

    # No handler exists, so nothing can complete.
    if int(health.get("jobs_completed") or 0):
        fails.append("a_job_completed_but_no_handler_exists")

    if health.get("non_transient_jobs_marked_retryable"):
        fails.append("a_non_transient_refusal_was_marked_retryable")

    # A retryable job while nothing is approved would mean a refusal was
    # misclassified as a hiccup.
    if int(health.get("jobs_retryable") or 0) and not int(
        health.get("activation_allowlist_count") or 0
    ):
        fails.append("retryable_jobs_with_an_empty_allowlist")

    for counter in ("live_source_calls", "collectors_invoked", "network_calls"):
        if health.get(counter):
            fails.append(f"health_counted:{counter}")

    if health.get("api_key_required"):
        fails.append("health_claimed:api_key_required")

    return sorted(set(fails))
