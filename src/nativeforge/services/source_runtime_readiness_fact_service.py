"""Whether the Gates 156-161 runtime can carry a collection (Gate 162F).

## The stale claim this repairs, stated precisely

`phase1_collector_activation_policy_service` reports
`scheduler_runtime_available: False`. Measured, the cause is not what the name
suggests:

```text
source_scheduler_readiness_service says
    scheduler_runtime_available    True
    background_worker_available    FALSE   <- this is the one
    periodic_trigger_available     False
    runtime_executes_jobs          False
    scheduler_package_installed    False

and phase1 computes
    _scheduler_runtime_available() = scheduler_runtime_available
                                     AND background_worker_available
```

Gate 98E's detector looks for a third-party scheduler package and a broker. The
runtime Gates 157-161 actually built is in-process: a worker that claims jobs
and records outcomes, a durable job store, periodic orchestration with
duplicate suppression and missed-window recovery, a payload store, and an
execution envelope. The detector was never taught that this counts, so it
answers a question about celery and phase1 reads it as a question about
whether work can run.

## What this does NOT do

It does not answer "does the module exist". A file on disk is not a runtime,
and `162F` said so explicitly. Each lane below has its own health service that
OBSERVES evidence - rows in tables, restart proofs, hashes that verify - and
this composes those observations.

Which means a lane can report `not_ready` in a bare process that has not
exercised it, and that is correct rather than a bug: the lane is reporting that
it cannot see the evidence from here. `conditions_not_met` says which evidence
is missing, so "not ready" is never a bare no.

## Necessary, and emphatically not sufficient

A ready runtime authorizes nothing. It is one of eleven facts, and every source
in the registry currently fails on terms, human review and activation
regardless of what this service answers. If this returned `ready` for every
lane tomorrow, zero sources would become approved.

That is the distinction the whole 156-165 block exists to hold, so this module
carries it in a field rather than leaving it to a reader's good sense.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_runtime_readiness_fact_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The six lanes Gates 156-161 built, each with the health service that
#: OBSERVES it and the field that lane calls its own readiness.
#:
#: Ordered as the block built them, so a reader can see the dependency chain.
LANES: tuple[tuple[str, str, str, str], ...] = (
    (
        "scheduler_runtime_ready",
        "source_scheduler_readiness_service",
        "build_scheduler_readiness",
        "scheduler_runtime_available",
    ),
    (
        "worker_runtime_ready",
        "source_collection_worker_health_service",
        "build_worker_health",
        "worker_runtime_ready",
    ),
    (
        "collection_job_store_ready",
        "source_collection_job_store_health_service",
        "build_job_store_health",
        "collection_job_store_ready",
    ),
    (
        "orchestration_runtime_ready",
        "source_collection_orchestration_health_service",
        "build_orchestration_health",
        "orchestration_runtime_ready",
    ),
    (
        "raw_payload_persistence_ready",
        "source_raw_payload_health_service",
        "build_raw_payload_health",
        "raw_payload_persistence_ready",
    ),
    (
        "collector_execution_envelope_ready",
        "source_collector_execution_health_service",
        "build_execution_health",
        "execution_envelope_ready",
    ),
)

LANE_NAMES: tuple[str, ...] = tuple(lane[0] for lane in LANES)

#: Which lanes a SOURCE COLLECTION actually needs. Named explicitly, because
#: 162F asked which of them the authorization guard requires and the honest
#: answer is "not all six".
#:
#: A collection needs somewhere to record the job, something to run it,
#: somewhere to put the bytes, and an envelope to carry the request. It does
#: NOT need periodic orchestration: a one-shot operator-triggered collection is
#: a legitimate shape, and requiring a scheduler would make the first live
#: source depend on machinery it does not use.
REQUIRED_FOR_COLLECTION: tuple[str, ...] = (
    "worker_runtime_ready",
    "collection_job_store_ready",
    "raw_payload_persistence_ready",
    "collector_execution_envelope_ready",
)

#: Needed only for MONITORING - a recurring, unattended collection.
REQUIRED_FOR_MONITORING: tuple[str, ...] = (
    *REQUIRED_FOR_COLLECTION,
    "scheduler_runtime_ready",
    "orchestration_runtime_ready",
)

READY = "ready"
NOT_READY = "not_ready"
UNKNOWN = "unknown"

NOT_IMPLIED: tuple[str, ...] = (
    "a ready runtime is not an approved source",
    "a ready runtime is not a terms decision",
    "a ready runtime is not a human review",
    "a ready runtime has contacted nothing",
    "if every lane were ready tomorrow, zero sources would become approved",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _observe_lane(
    module_name: str,
    function_name: str,
    ready_field: str,
    *,
    connection: Any,
    organization_id: Any,
) -> dict[str, Any]:
    """Ask one lane's health service. Never infer from the module existing."""
    import importlib
    import inspect

    try:
        module = importlib.import_module(f"nativeforge.services.{module_name}")
    except ImportError:
        return {
            "observed": False,
            "status": UNKNOWN,
            "why": f"{module_name} could not be imported",
            "conditions_not_met": [],
        }

    function = getattr(module, function_name, None)
    if function is None:
        return {
            "observed": False,
            "status": UNKNOWN,
            "why": f"{module_name}.{function_name} does not exist",
            "conditions_not_met": [],
        }

    # Only pass what the lane actually takes. A lane that needs no connection
    # is measuring something that does not depend on one.
    try:
        params = set(inspect.signature(function).parameters)
    except (TypeError, ValueError):
        params = set()
    kwargs: dict[str, Any] = {}
    if "connection" in params:
        kwargs["connection"] = connection
    if "organization_id" in params:
        kwargs["organization_id"] = organization_id

    try:
        health = function(**kwargs)
    except Exception as exc:  # noqa: BLE001 - a lane that raises is not ready
        return {
            "observed": False,
            "status": UNKNOWN,
            "why": f"{function_name} raised {type(exc).__name__}",
            "conditions_not_met": [],
        }

    if ready_field not in health:
        return {
            "observed": False,
            "status": UNKNOWN,
            "why": f"{module_name} does not report {ready_field}",
            "conditions_not_met": [],
        }

    unmet = list(
        health.get("conditions_not_met")
        or health.get("unmet_conditions")
        or health.get("blocked_reasons")
        or []
    )
    ready = bool(health[ready_field])
    return {
        "observed": True,
        "status": READY if ready else NOT_READY,
        "ready_field": ready_field,
        "source_of_truth": f"{module_name}.{function_name}",
        # A bare "not ready" is not actionable. Say which evidence is absent.
        "conditions_not_met": unmet,
        "why": (
            None
            if ready
            else (
                f"{len(unmet)} condition(s) unobserved from here"
                if unmet
                else "the lane reported not ready without naming a condition"
            )
        ),
    }


def build_runtime_readiness_facts(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Observe all six lanes. Composes health services; infers nothing."""
    lanes: dict[str, Any] = {}
    for name, module_name, function_name, ready_field in LANES:
        lanes[name] = _observe_lane(
            module_name,
            function_name,
            ready_field,
            connection=connection,
            organization_id=organization_id,
        )

    def _ready(names: tuple[str, ...]) -> bool:
        return all(lanes[n]["status"] == READY for n in names)

    collection_ready = _ready(REQUIRED_FOR_COLLECTION)
    monitoring_ready = _ready(REQUIRED_FOR_MONITORING)

    unmet_for_collection = sorted(
        name
        for name in REQUIRED_FOR_COLLECTION
        if lanes[name]["status"] != READY
    )
    unmet_for_monitoring = sorted(
        name
        for name in REQUIRED_FOR_MONITORING
        if lanes[name]["status"] != READY
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "lanes": lanes,
            "lane_names": list(LANE_NAMES),
            "required_for_collection": list(REQUIRED_FOR_COLLECTION),
            "required_for_monitoring": list(REQUIRED_FOR_MONITORING),
            # The fact the authorization resolver consumes. Named `runtime_status`
            # to match the fact model's vocabulary exactly.
            "runtime_status": READY if collection_ready else NOT_READY,
            "collection_runtime_ready": collection_ready,
            "monitoring_runtime_ready": monitoring_ready,
            "unmet_for_collection": unmet_for_collection,
            "unmet_for_monitoring": unmet_for_monitoring,
            "lanes_observed": sum(
                1 for lane in lanes.values() if lane["observed"]
            ),
            "lanes_ready": sum(
                1 for lane in lanes.values() if lane["status"] == READY
            ),
            # ---- what this repairs, and what it does not ------------------
            "repairs": (
                "phase1_collector_activation_policy_service read Gate 98E's "
                "`background_worker_available`, which detects a third-party "
                "scheduler package and a broker. The Gates 157-161 runtime is "
                "in-process, so that detector answers a question about celery "
                "and phase1 read it as a question about whether work can run."
            ),
            "not_derived_from_module_existence": (
                "each lane's own health service OBSERVES evidence - rows, "
                "restart proofs, hashes that verify. A file on disk is not a "
                "runtime, and a lane reporting not_ready from a process that "
                "has not exercised it is reporting that correctly."
            ),
            "not_implied": list(NOT_IMPLIED),
            "authorizes_nothing": True,
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def runtime_readiness_invariant_failures(facts: dict[str, Any]) -> list[str]:
    """Refuse a readiness report that authorizes, or that says no without why."""
    fails: list[str] = []

    lanes = facts.get("lanes") or {}
    expected = set(facts.get("lane_names") or ())
    if expected and set(lanes) != expected:
        fails.append("lanes_do_not_match_the_declared_set")

    for name, lane in lanes.items():
        if lane.get("status") not in (READY, NOT_READY, UNKNOWN):
            fails.append(f"lane_status_outside_vocabulary:{name}")
        # A lane that is not ready must say why. A bare no is not actionable,
        # and this campaign has already shipped one refusal nobody could
        # diagnose.
        if lane.get("status") != READY and not (
            lane.get("conditions_not_met") or lane.get("why")
        ):
            fails.append(f"a_not_ready_lane_that_does_not_say_why:{name}")

    # runtime_status and the composed answer must agree, both directions.
    ready = bool(facts.get("collection_runtime_ready"))
    if (facts.get("runtime_status") == READY) != ready:
        fails.append("runtime_status_disagrees_with_collection_runtime_ready")
    if ready and facts.get("unmet_for_collection"):
        fails.append("ready_alongside_unmet_lanes")
    if not ready and not facts.get("unmet_for_collection"):
        fails.append("not_ready_without_naming_an_unmet_lane")

    # Monitoring needs strictly more than collection, so it can never be the
    # readier of the two.
    if facts.get("monitoring_runtime_ready") and not ready:
        fails.append("monitoring_ready_while_collection_is_not")

    # THE invariant of this module.
    if not facts.get("authorizes_nothing"):
        fails.append("a_runtime_readiness_report_that_claims_to_authorize")
    if not facts.get("not_implied"):
        fails.append("the_report_did_not_say_what_it_does_not_imply")

    for flag in ("live_source_call", "source_monitoring_live"):
        if facts.get(flag):
            fails.append(f"runtime_readiness_claimed:{flag}")

    return sorted(set(fails))
