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

from nativeforge.repositories.source_collection_job_repository import (
    CLAIMED as JOB_CLAIMED,
)
from nativeforge.repositories.source_collection_job_repository import (
    FAILED as JOB_FAILED,
)
from nativeforge.repositories.source_collection_job_repository import (
    QUEUED as JOB_QUEUED,
)
from nativeforge.repositories.source_collection_job_repository import (
    REFUSED as JOB_REFUSED,
)
from nativeforge.repositories.source_collection_job_repository import (
    RETRY_WAIT as JOB_RETRY_WAIT,
)
from nativeforge.repositories.source_collection_job_repository import (
    TERMINAL_REASONS as JOB_TERMINAL_REASONS,
)
from nativeforge.repositories.source_collection_job_repository import (
    get_job,
    job_store_invariant_failures,
    list_jobs,
    transition_job,
)
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
from nativeforge.services.source_collection_transport_service import (
    HERMETIC as HERMETIC_TRANSPORT_KIND,
)
from nativeforge.services.source_collector_execution_service import (
    execute_collection,
    execution_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_worker_runtime_v1"

#: Why a job read out of the durable store cannot be run by this worker.
#:
#: The store records WHY a job was blocked. It does not record that a job is
#: permitted, and an empty `blocked_reasons` is the absence of a recorded
#: objection rather than the presence of an approval. Inferring permission from
#: it would be inferring source approval, so a store-loaded job is refused by
#: name and the permitted path stays reachable only for a job a scheduler pass
#: handed over directly.
STORE_LOADED_IS_NOT_PERMITTED = "executable_is_not_a_persisted_fact_in_gate_158"

#: Lease outcome -> durable job status. `completed` appears in neither column:
#: no worker in this campaign can complete a job, and the store would refuse it.
LEASE_STATUS_TO_JOB_STATUS = {
    REFUSED: JOB_REFUSED,
    RETRYABLE: JOB_RETRY_WAIT,
    FAILED: JOB_FAILED,
}

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

#: Gate 161: run the collector execution envelope against a REGISTERED FIXTURE.
#:
#: Opt-in by name. A caller that does not ask for this handler gets exactly the
#: Gate 157 behaviour, and a caller that does still has to satisfy six further
#: conditions per job. See `hermetic_execution_refusals`.
HANDLER_HERMETIC_EXECUTION = "hermetic_execution"

HANDLERS: tuple[str, ...] = (HANDLER_EVALUATE_ONLY, HANDLER_HERMETIC_EXECUTION)

#: There is no live handler, and naming its absence is the point.
HANDLERS_NOT_IMPLEMENTED: tuple[str, ...] = (
    "fetch_a_live_source: needs an approved source, which is Gate 162",
    "activate: needs an approved source, which is Gate 162 and a human first",
)

#: The id prefix a hermetic fixture source must carry.
#:
#: Necessary, never sufficient - see `_is_synthetic_fixture_source`.
HERMETIC_FIXTURE_PREFIX = "nf161.fixture."

#: Why a claimed job may not reach the hermetic envelope. Every one of these is
#: a refusal; there is no reason in this list that grants anything.
HERMETIC_REFUSALS: tuple[str, ...] = (
    "handler_is_not_hermetic_execution",
    "no_hermetic_transport_was_injected",
    "job_is_not_declared_a_hermetic_fixture",
    STORE_LOADED_IS_NOT_PERMITTED,
    "the_scheduler_did_not_mark_this_job_executable",
    "job_carries_no_source_definition",
    "source_id_is_not_a_synthetic_fixture",
)

#: Said on the way out of a SUCCESSFUL hermetic execution.
HERMETIC_IS_NOT_A_COLLECTION = (
    "hermetic_execution_succeeded_and_a_fixture_is_not_a_collection"
)


def _is_synthetic_fixture_source(source_id: Any) -> bool:
    """Two independent facts, both required.

    The prefix alone would let a caller name a real source
    `nf161.fixture.grants.gov`. The registry absence alone would pass every
    source in the world, the approved registry being empty. So: the id declares
    itself a fixture AND the approved registry has never heard of it.
    """
    text = str(source_id or "").strip()
    if not text.startswith(HERMETIC_FIXTURE_PREFIX):
        return False
    if len(text) <= len(HERMETIC_FIXTURE_PREFIX):
        return False
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        return text not in set(load_registry_rows())
    except Exception:  # noqa: BLE001 - an unanswerable registry refuses
        return False


def hermetic_execution_refusals(
    job: dict[str, Any], *, handler: str, transport: Any
) -> list[str]:
    """Every reason this job may not reach the envelope. Empty means it may."""
    refusals: list[str] = []
    if handler != HANDLER_HERMETIC_EXECUTION:
        refusals.append("handler_is_not_hermetic_execution")
    if not callable(transport):
        refusals.append("no_hermetic_transport_was_injected")
    if job.get("hermetic_fixture") is not True:
        refusals.append("job_is_not_declared_a_hermetic_fixture")
    if job.get("loaded_from_store"):
        refusals.append(STORE_LOADED_IS_NOT_PERMITTED)
    if not job.get("executable"):
        refusals.append("the_scheduler_did_not_mark_this_job_executable")
    if not isinstance(job.get("source_definition"), dict):
        refusals.append("job_carries_no_source_definition")
    if not _is_synthetic_fixture_source(
        job.get("source_id") or (job.get("source_definition") or {}).get("source_id")
    ):
        refusals.append("source_id_is_not_a_synthetic_fixture")
    return sorted(set(refusals))


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
    transport: Any = None,
    max_jobs: int = 100,
    load_jobs_from_store: bool = False,
    record_job_transitions: bool = True,
) -> dict[str, Any]:
    """One worker pass: claim, decide, record, release. Executes nothing.

    `jobs` are the scheduler's output. Their `executable` flag is read, never
    recomputed.

    Gate 158 adds two things, and neither grants a permission:

    - `load_jobs_from_store` reads the durable backlog when no scheduler output
      was handed over. Those jobs are refused by name, because the store holds
      why a job was blocked and never holds that it is permitted.
    - `record_job_transitions` writes the outcome onto the durable job row as
      well as the lease, so a refusal outlives the pass that produced it.
    """
    moment = _as_datetime(now)
    blocked: list[str] = []
    if connection is None:
        blocked.append("no_connection_supplied")
    if not str(worker_id or "").strip():
        blocked.append("no_worker_id_supplied")
    if moment is None:
        blocked.append("no_clock_supplied")
    if handler not in HANDLERS:
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
    # Hoisted above the store read, which contributes to it.
    failures: list[str] = []
    claim_denied = 0
    job_rows_transitioned = 0
    job_rows_missing = 0
    hermetic_executions = 0
    hermetic_payloads = 0
    hermetic_proofs = 0

    offered = list(jobs or [])

    # The durable backlog, when nobody handed over a scheduler pass. Read as
    # identities and lifecycle - never as permission.
    store_loaded = 0
    if load_jobs_from_store and not offered:
        for status in (JOB_QUEUED, JOB_RETRY_WAIT):
            listed = list_jobs(
                connection=connection,
                organization_id=organization_id,
                status=status,
                limit=int(max_jobs),
            )
            failures.extend(job_store_invariant_failures(listed))
            for row in listed.get("jobs") or []:
                offered.append(
                    {
                        "job_id": row["job_id"],
                        "source_id": row["source_id"],
                        # Hardcoded False, and NOT derived from the blockers
                        # below. See STORE_LOADED_IS_NOT_PERMITTED: reading why
                        # a source is blocked is not deciding that it is
                        # permitted.
                        "executable": False,
                        # The scheduler's recorded reasons come along, with
                        # this worker's own reason APPENDED rather than
                        # substituted. Replacing them was measured erasing four
                        # real blockers - including the terms refusal this
                        # campaign counts - and downgrading a classifiable
                        # reason to `unknown` on the first worker pass.
                        "blockers": [
                            *(row.get("blocked_reasons") or []),
                            STORE_LOADED_IS_NOT_PERMITTED,
                        ],
                        "loaded_from_store": True,
                        "persisted_blocked_reasons": list(
                            row.get("blocked_reasons") or []
                        ),
                    }
                )
                store_loaded += 1

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
                    "loaded_from_store": bool(job.get("loaded_from_store")),
                    # A denied claim touches no job row. Saying so keeps every
                    # result the same shape.
                    "job_row_status": None,
                    "job_row_blocked_reasons": [],
                }
            )
            continue

        # Claimed. Now ask the scheduler's verdict - never recompute it.
        executable = bool(job.get("executable"))
        blockers = list(job.get("blockers") or [])

        hermetic_refused = hermetic_execution_refusals(
            job, handler=handler, transport=transport
        )
        execution = None

        if not hermetic_refused:
            # Gate 161. Every one of the seven conditions held, so the envelope
            # runs against a REGISTERED FIXTURE. `is_synthetic_fixture` is
            # derived above, not forwarded from the caller: a worker that
            # passed on a caller's claim would be the way to declare a real
            # source synthetic.
            execution = execute_collection(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
                source_definition=job["source_definition"],
                attempt_number=int(
                    (claim.get("lease") or {}).get("attempt_count") or 1
                ),
                transport=transport,
                now=now,
                is_synthetic_fixture=True,
                scope=CONTROLLED_SCOPE,
            )
            failures.extend(execution_invariant_failures(execution))
            hermetic_executions += 1
            if execution["raw_payload_sha256"]:
                hermetic_payloads += 1
            if execution["execution_proof_available"]:
                hermetic_proofs += 1

            # The envelope ran; the JOB is still not done. It asked for source
            # X to be collected and a fixture answered instead, so the lease
            # outcome is a refusal with nothing having failed - which is also
            # what keeps `jobs_completed = 0` true and honest.
            failure_class = NONE
            status = REFUSED
            reasons = [
                HERMETIC_IS_NOT_A_COLLECTION,
                f"execution_status:{execution['execution_status']}",
            ]
        elif executable:
            # A permitted job the hermetic handler would not take. With zero
            # approved sources this is unreachable today, and it is written as
            # a refusal rather than an execution so that it stays safe if a
            # source is ever approved before Gate 162 says it may be called.
            failure_class = NONE
            status = REFUSED
            reasons = ["no_live_handler_implemented", *hermetic_refused]
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

        # ---- and now the durable row ---------------------------------------
        #
        # The lease says who held this for five minutes. The job row is what
        # survives, so the outcome is recorded on both. A job row that does not
        # exist is COUNTED rather than created here: inventing one would make
        # the worker a second enqueue path, and the scheduler is the only thing
        # that decides what work exists.
        job_row_status = None
        job_row_blocked: list[str] = []
        if record_job_transitions:
            present = get_job(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
            )
            if present.get("job") is None:
                job_rows_missing += 1
                job_row_blocked = present["blocked_reasons"]
            else:
                current = str((present["job"] or {}).get("status") or "")
                target = LEASE_STATUS_TO_JOB_STATUS.get(status)
                reason = (
                    failure_class
                    if failure_class in JOB_TERMINAL_REASONS
                    else "unknown"
                )
                steps: list[tuple[str, str]] = []
                # A queued job must pass through `claimed` to reach an
                # outcome, which is the state machine saying that an outcome
                # without a claim never happened.
                if current == JOB_QUEUED and target is not None:
                    steps.append((JOB_CLAIMED, NONE))
                if target is not None:
                    steps.append((target, reason))

                for to_status, step_reason in steps:
                    moved = transition_job(
                        connection=connection,
                        organization_id=organization_id,
                        job_id=job_id,
                        to_status=to_status,
                        terminal_reason=step_reason,
                        # Union with what the row already held. A transition
                        # records what happened; it does not get to forget why
                        # the work was blocked in the first place.
                        blocked_reasons=sorted(
                            set(reasons)
                            | set((present["job"] or {}).get("blocked_reasons") or [])
                        ),
                        next_retry_at=(
                            retry["next_retry_at"]
                            if to_status == JOB_RETRY_WAIT
                            else None
                        ),
                        increment_attempt=(
                            to_status == JOB_RETRY_WAIT
                            and failure_class == TRANSIENT_WORKER_FAILURE
                        ),
                        now=now,
                    )
                    failures.extend(job_store_invariant_failures(moved))
                    if moved["transitioned"]:
                        job_row_status = moved["to_status"]
                        job_rows_transitioned += 1
                    else:
                        job_row_blocked.extend(moved["blocked_reasons"])

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
                # A live collector. Still none; a fixture is not one.
                "collector_invoked": False,
                "hermetic_execution_refusals": hermetic_refused,
                "hermetic_execution": execution,
                "execution_attempt_id": (
                    execution["execution_attempt_id"] if execution else None
                ),
                "loaded_from_store": bool(job.get("loaded_from_store")),
                "job_row_status": job_row_status,
                "job_row_blocked_reasons": sorted(set(job_row_blocked)),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "worker_id": str(worker_id),
            "ran": True,
            "handler": handler,
            "handlers": list(HANDLERS),
            "handlers_not_implemented": list(HANDLERS_NOT_IMPLEMENTED),
            "hermetic_transport_injected": callable(transport),
            "hermetic_executions": hermetic_executions,
            "hermetic_payloads_persisted": hermetic_payloads,
            "hermetic_execution_proofs": hermetic_proofs,
            "evaluated_at": str(now),
            "results": results,
            "jobs_offered": len(offered),
            "jobs_seen": len(results),
            "jobs_not_reached_this_cycle": truncated,
            "batch_was_truncated": bool(truncated),
            "max_jobs_per_cycle": int(max_jobs),
            "jobs_loaded_from_store": store_loaded,
            "job_rows_transitioned": job_rows_transitioned,
            "job_rows_missing": job_rows_missing,
            "job_transitions_recorded": bool(record_job_transitions),
            "jobs_claimed": sum(1 for r in results if r["claimed"]),
            "jobs_claim_denied": claim_denied,
            "jobs_completed": sum(1 for r in results if r["status"] == COMPLETED),
            "jobs_refused": sum(1 for r in results if r["status"] == REFUSED),
            "jobs_retryable": sum(1 for r in results if r["status"] == RETRYABLE),
            "jobs_failed": sum(1 for r in results if r["status"] == FAILED),
            "blocked_reasons": [],
            "invariant_failures": sorted(set(failures)),
            # Constants. A hermetic execution contacts nothing, so none of
            # these move: a registered fixture is not a collector, no host was
            # reached, and no URL was fetched.
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            # This one is NOT a constant. Gate 160 really did store bytes, and
            # reporting zero next to a row that exists is how a counter becomes
            # a claim rather than a count.
            "raw_payloads_written": hermetic_payloads,
            "threads_started": 0,
            "source_monitoring_live": False,
            "api_key_required": False,
            # Said plainly, because a row that moved to `claimed` is the most
            # plausible thing to mistake for a source having been contacted.
            "claimed_job_means_source_contacted": False,
            "persisted_job_means_collection_occurred": False,
            "hermetic_execution_means_collection_occurred": False,
            "why_a_hermetic_execution_completes_nothing": (
                "the job asked for a source to be collected and a registered "
                "fixture answered instead. The envelope ran; the work did not."
            ),
            "store_loaded_jobs_are_never_permitted": (
                "the job store records why a job was blocked, never that it is "
                "permitted. An empty blocked_reasons is the absence of a "
                "recorded objection, not an approval."
            ),
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

    if cycle.get("handler") not in (None, *HANDLERS):
        fails.append(f"cycle_ran_an_unimplemented_handler:{cycle.get('handler')}")

    # These describe LIVE activity, and a hermetic execution is none of it: a
    # registered fixture is not a collector, no host was reached, no URL was
    # fetched, and nothing was spawned. They stay hard zero under every handler.
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "threads_started",
    ):
        if cycle.get(counter):
            fails.append(f"cycle_counted:{counter}")

    # `raw_payloads_written` is no longer one of them, because Gate 160 stores
    # real bytes and forcing the count to zero would make it a claim rather
    # than a count. What replaces the zero is an AGREEMENT, which is the
    # property the zero was standing in for:
    #
    #   - it must equal what the hermetic path says it persisted;
    #   - a payload cannot outnumber the executions that produced it;
    #   - and under any handler but the hermetic one it must still be zero.
    hermetic_runs = int(cycle.get("hermetic_executions") or 0)
    hermetic_stored = int(cycle.get("hermetic_payloads_persisted") or 0)
    written = int(cycle.get("raw_payloads_written") or 0)
    proofs = int(cycle.get("hermetic_execution_proofs") or 0)

    if written != hermetic_stored:
        fails.append("raw_payloads_written_disagrees_with_the_hermetic_count")
    if hermetic_stored > hermetic_runs:
        fails.append("more_payloads_than_executions")
    if proofs > hermetic_stored:
        fails.append("more_execution_proofs_than_persisted_payloads")
    if hermetic_runs and cycle.get("handler") != HANDLER_HERMETIC_EXECUTION:
        fails.append(
            f"a_hermetic_execution_under_handler:{cycle.get('handler')}"
        )
    if hermetic_runs and not cycle.get("hermetic_transport_injected"):
        fails.append("a_hermetic_execution_without_an_injected_transport")

    # A hermetic execution must never be mistaken for a collection, and the
    # cycle says so in a field rather than leaving it to be inferred.
    if cycle.get("hermetic_execution_means_collection_occurred"):
        fails.append("cycle_claimed_a_hermetic_execution_collected_something")

    # Each result's own envelope is re-checked here rather than trusted. A
    # summary that agrees with itself has only been half-checked.
    for result in results:
        envelope = result.get("hermetic_execution")
        if not isinstance(envelope, dict):
            continue
        fails.extend(execution_invariant_failures(envelope))
        if envelope.get("transport_kind") != HERMETIC_TRANSPORT_KIND:
            fails.append(
                f"a_result_carried_a_non_hermetic_envelope:{result.get('job_id')}"
            )

    for flag in ("source_monitoring_live", "api_key_required"):
        if cycle.get(flag):
            fails.append(f"cycle_claimed:{flag}")

    return sorted(set(fails))
