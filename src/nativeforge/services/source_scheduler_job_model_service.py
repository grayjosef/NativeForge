"""Source scheduler job model (Gate 99B).

Represents a scheduled source job. Building one performs no network I/O, runs no
collector, and writes nothing.

## A job is a description of work, not the work

`build_source_job` returns a record. Nothing in this module dispatches, and
`executed`, `fetch_performed` and `collector_invoked` are False on every job.
That is not a courtesy flag - it is the whole distinction this gate rests on. A
queue of jobs nobody has agreed to run is a plan; treating it as monitoring is
how "we have a scheduler" becomes true in a slide deck and false in production.

## dry_run is the default, and live_collection has to be earned

`execution_mode` defaults to `dry_run`. `live_collection` is not refused
outright - refusing it permanently would make this module useless the day a
worker exists - but it is granted only when *every* preflight is affirmatively
satisfied:

```text
activation_status          activation_allowed
schedule_decision_status   due_and_safe_to_enqueue
circuit_status             closed or half_open
raw_payload_store_status   production_available
```

Each is derived from the affirmative set. Absent or unrecognised values do not
pass, and a request for `live_collection` that fails any of them comes back as a
`dry_run` job with `live_collection_downgraded` in its reasons - not as an error,
and never as a live job that "probably would have been fine".

Gate 99 additionally holds the whole module to dry-run through
`LIVE_COLLECTION_REQUIRES_WORKER`: a live job also needs a background worker to
exist, and Gate 98E detects that none does. So `live_jobs_created` is zero in
this gate by *derivation* rather than by a constant that would go stale.

## Deterministic identity

`job_id` is a sha256 over source, collector, type, scheduled time and execution
mode. The same job described twice is the same id. `idempotency_key` covers the
same tuple minus the attempt number, so a retry of a job is recognisably the same
piece of work rather than a second one - which is what lets the queue deduplicate
without a database.

Neither includes `created_at`. Including a wall clock would make every
description of the same job unique, which is precisely the bug deduplication
exists to prevent.

## Blocked jobs say why

A job that cannot run is kept, with `blocked_reasons` populated. Dropping it
would make the queue look healthy by omission - the same shape as a count with no
evidence behind it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.source_circuit_breaker_service import (
    CIRCUIT_STATUSES,
    SCHEDULING_PERMITTED_STATUSES,
)
from nativeforge.services.source_schedule_decision_service import (
    ENQUEUE_PERMITTED_STATUSES,
    SCHEDULE_STATUSES,
)

SCHEMA_VERSION = "nf_source_scheduler_job_model_v1"

JOB_TYPES = frozenset(
    {
        "source_check",
        "forecast_lapse_check",
        "amendment_check",
        "raw_payload_reconciliation",
        "terms_review_recheck",
    }
)
DEFAULT_JOB_TYPE = "source_check"

EXECUTION_MODES = frozenset(
    {"dry_run", "live_collection", "replay_fixture", "manual_review"}
)
DEFAULT_EXECUTION_MODE = "dry_run"

# The only mode that would put a request on the wire.
LIVE_EXECUTION_MODES = frozenset({"live_collection"})

JOB_STATUSES = frozenset(
    {"queued", "blocked", "skipped", "running", "completed", "failed", "cancelled"}
)

# Statuses a job may hold without anything having run. `running`, `completed`
# and `failed` describe execution, and nothing in this gate executes.
NON_EXECUTED_STATUSES = frozenset({"queued", "blocked", "skipped", "cancelled"})

ACTIVATION_STATUSES = frozenset(
    {
        "activation_allowed",
        "activation_blocked",
        "activation_requires_human_review",
        "activation_unknown",
    }
)
ACTIVATION_SATISFYING = frozenset({"activation_allowed"})

RAW_PAYLOAD_STORE_STATUSES = frozenset(
    {"production_available", "local_only", "contract_only", "unavailable", "unknown"}
)
RAW_PAYLOAD_STORE_SATISFYING = frozenset({"production_available"})

# Gate 99 constant, and a deliberate one: a live job needs somewhere to run.
# Gate 98E detects that no background worker exists, so this resolves to a
# refusal by derivation rather than by a hardcoded False that would go stale.
LIVE_COLLECTION_REQUIRES_WORKER = True

# Every precondition a live_collection job must satisfy, in reporting order.
LIVE_PRECONDITION_KEYS: tuple[str, ...] = (
    "activation_allowed",
    "schedule_permits_enqueue",
    "circuit_permits",
    "production_payload_store",
    "background_worker_available",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _as_attempt(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        return 1
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 1
    return number if number >= 1 else 1


def _digest(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join(str(p if p is not None else "") for p in parts).encode("utf-8")
    ).hexdigest()


def build_job_id(
    *,
    source_id: Any,
    collector_id: Any,
    job_type: Any,
    scheduled_for: Any,
    execution_mode: Any,
) -> str:
    """Deterministic. The same job described twice is the same id."""
    return _digest(source_id, collector_id, job_type, scheduled_for, execution_mode)


def build_idempotency_key(
    *,
    source_id: Any,
    collector_id: Any,
    job_type: Any,
    scheduled_for: Any,
) -> str:
    """Deterministic, and independent of execution mode and attempt number.

    A retry of a job, and a dry-run rehearsal of a job that would later run live,
    are the same *piece of work*. The key says so, which is what lets the queue
    deduplicate without consulting a database.
    """
    return _digest(source_id, collector_id, job_type, scheduled_for)


def _background_worker_available() -> bool:
    """Detected via Gate 98E, never passed in."""
    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )
    except ImportError:
        return False
    return bool(build_scheduler_readiness()["background_worker_available"])


def build_source_job(
    *,
    source_id: Any,
    collector_id: Any = None,
    job_type: Any = None,
    scheduled_for: Any = None,
    created_at: Any = None,
    execution_mode: Any = None,
    activation_status: Any = None,
    schedule_decision_status: Any = None,
    circuit_status: Any = None,
    raw_payload_store_status: Any = None,
    attempt_number: Any = None,
) -> dict[str, Any]:
    """One job record. Nothing is dispatched, fetched, or written."""
    requested_mode = _norm(
        execution_mode, EXECUTION_MODES, fallback=DEFAULT_EXECUTION_MODE
    )
    jtype = _norm(job_type, JOB_TYPES, fallback=DEFAULT_JOB_TYPE)
    activation = _norm(
        activation_status, ACTIVATION_STATUSES, fallback="activation_unknown"
    )
    schedule_status = _norm(
        schedule_decision_status, SCHEDULE_STATUSES, fallback="unknown"
    )
    circuit = _norm(circuit_status, CIRCUIT_STATUSES, fallback="unknown")
    store = _norm(
        raw_payload_store_status, RAW_PAYLOAD_STORE_STATUSES, fallback="unknown"
    )
    attempt = _as_attempt(attempt_number)

    worker_available = _background_worker_available()

    # Derive the live preconditions affirmatively. Nothing is subtracted from a
    # permissive default; each is a membership test against a satisfying set.
    preconditions = {
        "activation_allowed": activation in ACTIVATION_SATISFYING,
        "schedule_permits_enqueue": schedule_status in ENQUEUE_PERMITTED_STATUSES,
        "circuit_permits": circuit in SCHEDULING_PERMITTED_STATUSES,
        "production_payload_store": store in RAW_PAYLOAD_STORE_SATISFYING,
        "background_worker_available": worker_available
        or not LIVE_COLLECTION_REQUIRES_WORKER,
    }
    missing = sorted(k for k, ok in preconditions.items() if not ok)

    blocked_reasons: list[str] = []
    if activation not in ACTIVATION_SATISFYING:
        blocked_reasons.append(f"activation_not_allowed:{activation}")
    if schedule_status not in ENQUEUE_PERMITTED_STATUSES:
        blocked_reasons.append(f"schedule_does_not_permit_enqueue:{schedule_status}")
    if circuit not in SCHEDULING_PERMITTED_STATUSES:
        blocked_reasons.append(f"circuit_does_not_permit:{circuit}")
    if store not in RAW_PAYLOAD_STORE_SATISFYING:
        blocked_reasons.append(f"production_payload_store_unavailable:{store}")

    # A live request that has not earned it becomes a dry run, recorded as such.
    live_requested = requested_mode in LIVE_EXECUTION_MODES
    live_granted = live_requested and not missing
    resolved_mode = requested_mode if live_granted or not live_requested else "dry_run"
    if live_requested and not live_granted:
        blocked_reasons.append("live_collection_downgraded")
        if not worker_available and LIVE_COLLECTION_REQUIRES_WORKER:
            blocked_reasons.append("background_worker_unavailable")

    # A job whose preconditions do not hold is kept, and marked. `queued` here
    # means "eligible to be picked up", not "will run" - nothing picks up.
    job_status = "queued" if not blocked_reasons else "blocked"

    job_id = build_job_id(
        source_id=source_id,
        collector_id=collector_id,
        job_type=jtype,
        scheduled_for=scheduled_for,
        execution_mode=resolved_mode,
    )
    idempotency_key = build_idempotency_key(
        source_id=source_id,
        collector_id=collector_id,
        job_type=jtype,
        scheduled_for=scheduled_for,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "job_id": job_id,
            "source_id": source_id,
            "collector_id": collector_id,
            "job_type": jtype,
            "scheduled_for": scheduled_for,
            "created_at": created_at,
            "execution_mode": resolved_mode,
            "requested_execution_mode": requested_mode,
            "activation_status": activation,
            "schedule_decision_status": schedule_status,
            "circuit_status": circuit,
            "raw_payload_store_status": store,
            "attempt_number": attempt,
            "idempotency_key": idempotency_key,
            "job_status": job_status,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "live_preconditions_satisfied": sorted(
                k for k, ok in preconditions.items() if ok
            ),
            "live_preconditions_missing": missing,
            "live_collection_granted": live_granted,
            # Constants: describing work is not doing it.
            "executed": False,
            "fetch_performed": False,
            "collector_invoked": False,
            "raw_payload_written": False,
            "source_monitoring_live": False,
            "fabricated": False,
        }
    )


def job_invariant_failures(job: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if job.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if job.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "executed",
        "fetch_performed",
        "collector_invoked",
        "raw_payload_written",
        "source_monitoring_live",
    ):
        if job.get(constant) is not False:
            fails.append(f"job_claimed:{constant}")

    if job.get("job_type") not in JOB_TYPES:
        fails.append("job_type_out_of_vocabulary")
    if job.get("execution_mode") not in EXECUTION_MODES:
        fails.append("execution_mode_out_of_vocabulary")
    if job.get("job_status") not in JOB_STATUSES:
        fails.append("job_status_out_of_vocabulary")

    # Nothing runs in this gate, so no job may hold an execution status.
    if job.get("job_status") not in NON_EXECUTED_STATUSES:
        fails.append(f"job_status_implies_execution:{job.get('job_status')}")

    if job.get("attempt_number") is not None:
        attempt = job.get("attempt_number")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            fails.append("attempt_number_not_a_positive_int")

    # Live collection must have earned every precondition.
    if job.get("execution_mode") in LIVE_EXECUTION_MODES:
        if job.get("live_preconditions_missing"):
            fails.append("live_collection_with_missing_preconditions")
        if not job.get("live_collection_granted"):
            fails.append("live_execution_mode_without_a_grant")
        if job.get("activation_status") not in ACTIVATION_SATISFYING:
            fails.append("live_collection_without_activation")
        if job.get("circuit_status") not in SCHEDULING_PERMITTED_STATUSES:
            fails.append("live_collection_with_a_blocking_circuit")
        if job.get("raw_payload_store_status") not in RAW_PAYLOAD_STORE_SATISFYING:
            fails.append("live_collection_without_a_production_payload_store")

    if job.get("live_collection_granted") and job.get("live_preconditions_missing"):
        fails.append("grant_with_missing_preconditions")

    # Every precondition accounted for exactly once.
    satisfied = set(job.get("live_preconditions_satisfied") or [])
    missing = set(job.get("live_preconditions_missing") or [])
    if satisfied & missing:
        fails.append("precondition_both_satisfied_and_missing")
    if satisfied | missing != set(LIVE_PRECONDITION_KEYS):
        fails.append("precondition_dropped_from_the_checklist")

    # A blocked job must say why, and a job with reasons must read as blocked.
    if job.get("job_status") == "blocked" and not job.get("blocked_reasons"):
        fails.append("blocked_without_a_reason")
    if job.get("blocked_reasons") and job.get("job_status") == "queued":
        fails.append("queued_despite_blocking_reasons")

    # Identity must be reproducible from the job's own fields.
    expected_id = build_job_id(
        source_id=job.get("source_id"),
        collector_id=job.get("collector_id"),
        job_type=job.get("job_type"),
        scheduled_for=job.get("scheduled_for"),
        execution_mode=job.get("execution_mode"),
    )
    if job.get("job_id") != expected_id:
        fails.append("job_id_not_derivable_from_its_fields")

    expected_key = build_idempotency_key(
        source_id=job.get("source_id"),
        collector_id=job.get("collector_id"),
        job_type=job.get("job_type"),
        scheduled_for=job.get("scheduled_for"),
    )
    if job.get("idempotency_key") != expected_key:
        fails.append("idempotency_key_not_derivable_from_its_fields")

    return fails
