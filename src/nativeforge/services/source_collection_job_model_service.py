"""Gate 156C: the collection job record — a projection, not a second model.

## Why this does not replace `source_scheduler_job_model_service`

Gate 99B already builds a source job, and its module name is one word from this
one. Writing a second independent model would give the repository two places to
ask whether a job may run, which is how they come to disagree — and Gate 153
overwrote a 320-line module by picking a name that was already taken.

So this composes. `build_collection_job` calls Gate 99B's `build_source_job`
for the parts it already owns (job id, idempotency key, execution mode, the
`collector_invoked` / `fetch_performed` constants) and adds the scheduling
fields Gate 156 needs: the computed next run, the runtime state, and a single
`executable` flag with every prerequisite named beside it.

```text
Gate 99B  build_source_job        what kind of job this is, and its identity
Gate 156  build_collection_job    when it is due, and whether it may run
```

## `executable` is true only when every prerequisite is affirmatively true

Not "nothing objected". Activation, terms and human review must each hold the
permitting value, a collector must be registered, and the clock must have come
round. A source whose terms nobody has read is UNKNOWN, and UNKNOWN blocks.

**Expected executable count across the registry today: 0.**
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_scheduler_runtime_service import (
    RUNTIME_STATES,
    evaluate_source_schedule,
    schedule_evaluation_invariant_failures,
)
from nativeforge.services.source_scheduler_job_model_service import (
    build_source_job,
)

SCHEMA_VERSION = "nf_source_collection_job_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Fields every collection job carries, named so a test can assert the shape
#: rather than trusting whatever the builder happened to emit.
JOB_FIELDS: tuple[str, ...] = (
    "job_id",
    "source_id",
    "organization_id",
    "schedule",
    "next_run_at",
    "last_run_at",
    "runtime_state",
    "activation_state",
    "terms_state",
    "human_review_state",
    "blockers",
    "executable",
    "fact_status",
)

FACT_STATUS_DEMO = "demo_fixture"
FACT_STATUS_REGISTRY = "registry_row"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_collection_job(
    *,
    source_id: Any = None,
    organization_id: Any = None,
    now: Any = None,
    last_checked_at: Any = None,
    check_interval_days: Any = None,
    recorded_next_check_due_at: Any = None,
    activation_state: Any = None,
    terms_state: Any = None,
    human_review_state: Any = None,
    is_enabled: Any = None,
    collector_registered: Any = None,
    known_source: bool = True,
    fact_status: Any = None,
    is_demo: Any = None,
) -> dict[str, Any]:
    """One collection job. Dispatches nothing, fetches nothing, writes nothing."""
    evaluation = evaluate_source_schedule(
        source_id=source_id,
        now=now,
        last_checked_at=last_checked_at,
        check_interval_days=check_interval_days,
        recorded_next_check_due_at=recorded_next_check_due_at,
        activation_state=activation_state,
        terms_state=terms_state,
        human_review_state=human_review_state,
        is_enabled=is_enabled,
        collector_registered=collector_registered,
        known_source=known_source,
    )

    # Gate 99B owns identity and the execution-mode constants. Its default
    # execution_mode is `dry_run` and its `collector_invoked` is False; nothing
    # here overrides either.
    base = build_source_job(
        source_id=source_id,
        job_type="scheduled_check",
        scheduled_for=evaluation["next_run_at"],
        execution_mode="dry_run",
        activation_status=(
            "activation_allowed" if evaluation["executable"] else "activation_blocked"
        ),
        schedule_decision_status=(
            "due_and_safe_to_enqueue" if evaluation["executable"] else "due_but_blocked"
        ),
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "job_id": base.get("job_id"),
            "source_id": evaluation["source_id"],
            "organization_id": str(organization_id) if organization_id else None,
            "schedule": {
                "check_interval_days": evaluation["check_interval_days"],
                "source_of_truth": evaluation["source_of_truth"],
                "recorded_next_check_due_at": evaluation["recorded_next_check_due_at"],
                "computed_next_run_at": evaluation["computed_next_run_at"],
                "disagrees": evaluation["disagrees"],
            },
            "next_run_at": evaluation["next_run_at"],
            "last_run_at": evaluation["last_checked_at"],
            "runtime_state": evaluation["runtime_state"],
            "due": evaluation["due"],
            "activation_state": evaluation["activation_state"],
            "terms_state": evaluation["terms_state"],
            "human_review_state": evaluation["human_review_state"],
            "collector_registered": evaluation["collector_registered"],
            "is_enabled": evaluation["is_enabled"],
            "blockers": evaluation["blockers"],
            "blocker_count": evaluation["blocker_count"],
            "executable": evaluation["executable"],
            "fact_status": str(
                fact_status or (FACT_STATUS_DEMO if is_demo else FACT_STATUS_REGISTRY)
            ),
            "is_demo": bool(is_demo),
            # From Gate 99B, unchanged. A job is a description of work.
            "execution_mode": base.get("execution_mode"),
            "collector_invoked": False,
            "fetch_performed": False,
            "executed": False,
            "live_source_called": False,
            "network_calls": 0,
            "rows_written": 0,
            "source_monitoring_live": False,
            "built_on_gate_99b": "source_scheduler_job_model_service.build_source_job",
        }
    )


def collection_job_invariant_failures(job: dict[str, Any]) -> list[str]:
    """Refuse a job that claims execution, or permission it does not have."""
    fails: list[str] = []

    for field in JOB_FIELDS:
        if field not in job:
            fails.append(f"job_field_missing:{field}")

    if job.get("runtime_state") not in RUNTIME_STATES:
        fails.append(f"runtime_state_outside_vocabulary:{job.get('runtime_state')}")

    if job.get("executable"):
        if job.get("blockers"):
            fails.append("executable_alongside_blockers")
        if not job.get("due"):
            fails.append("executable_while_not_due")

    # Reconstructed from the same evaluator, so a job cannot carry a verdict
    # its own inputs would not produce.
    fails.extend(
        schedule_evaluation_invariant_failures(
            {
                "runtime_state": job.get("runtime_state"),
                "executable": job.get("executable"),
                "due": job.get("due"),
                "blockers": job.get("blockers"),
                "blocker_count": job.get("blocker_count"),
                "activation_state": job.get("activation_state"),
                "terms_state": job.get("terms_state"),
                "human_review_state": job.get("human_review_state"),
                "collector_registered": job.get("collector_registered"),
                "collector_invoked": job.get("collector_invoked"),
                "live_source_called": job.get("live_source_called"),
                "source_monitoring_live": job.get("source_monitoring_live"),
                "network_calls": job.get("network_calls"),
                "rows_written": job.get("rows_written"),
            }
        )
    )

    for flag in ("executed", "fetch_performed", "collector_invoked"):
        if job.get(flag):
            fails.append(f"job_claimed:{flag}")

    return sorted(set(fails))
