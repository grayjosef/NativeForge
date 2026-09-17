"""Gate 161 verifier phase: a hermetic job through the Gate 157 worker.

`every_refusal_condition_fires_alone` is the one that matters. A refusal set
exercised only as a whole could be missing any single condition and every
refusal would still fire, so each condition is violated on its own and must
produce exactly its own reason.

Rows written here are cleaned up by `_g161_phase_cleanup.py`, the LAST phase.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from tests import session_org_helper as soh  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    enqueue_job,
)
from nativeforge.services.hermetic_source_transport_service import (  # noqa: E402
    HermeticTransportRegistry,
)
from nativeforge.services.source_collection_worker_runtime_service import (  # noqa: E402,E501
    HANDLER_EVALUATE_ONLY,
    HANDLER_HERMETIC_EXECUTION,
    HERMETIC_REFUSALS,
    hermetic_execution_refusals,
    run_worker_cycle,
    worker_cycle_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
PREFIX = "nf161-verify-"
URL = "https://fixtures.invalid/nf161/verify/worker"
BODY = b'{"opportunities":[{"number":"NF-161-W"}]}'

REG = HermeticTransportRegistry()
REG.register_ok(URL, BODY)

out: dict[str, object] = {}
detail: list[str] = []
session = SessionLocal()

try:
    soh.ensure_org(DEMO, "demo")
    stamp = uuid.uuid4().hex[:8]

    def job(tag: str, source_id: str = "nf161.fixture.verify.worker") -> dict:
        return {
            "job_id": f"{PREFIX}{stamp}-{tag}",
            "source_id": source_id,
            "executable": True,
            "blockers": [],
            "hermetic_fixture": True,
            "source_definition": {
                "source_id": source_id,
                "endpoint": URL,
                "method": "GET",
            },
        }

    # ---- each refusal condition, violated alone -------------------------
    alone: dict[str, str] = {}
    alone["handler_is_not_hermetic_execution"] = str(
        hermetic_execution_refusals(
            job("h"), handler=HANDLER_EVALUATE_ONLY, transport=REG.transport
        )
    )
    alone["no_hermetic_transport_was_injected"] = str(
        hermetic_execution_refusals(
            job("t"), handler=HANDLER_HERMETIC_EXECUTION, transport=None
        )
    )

    variants = [
        ("job_is_not_declared_a_hermetic_fixture",
         lambda j: j.update(hermetic_fixture=False)),
        ("executable_is_not_a_persisted_fact_in_gate_158",
         lambda j: j.update(loaded_from_store=True)),
        ("the_scheduler_did_not_mark_this_job_executable",
         lambda j: j.update(executable=False)),
        ("job_carries_no_source_definition",
         lambda j: j.pop("source_definition")),
        ("source_id_is_not_a_synthetic_fixture",
         lambda j: j.update(source_id="grants.gov")),
    ]
    for expected, mutate in variants:
        candidate = job("v")
        mutate(candidate)
        alone[expected] = str(
            hermetic_execution_refusals(
                candidate,
                handler=HANDLER_HERMETIC_EXECUTION,
                transport=REG.transport,
            )
        )

    each_alone = all(
        alone.get(expected) == f"['{expected}']"
        for expected in HERMETIC_REFUSALS
    )
    out["every_refusal_condition_fires_alone"] = bool(
        each_alone and set(alone) == set(HERMETIC_REFUSALS)
    )
    if not each_alone:
        for expected, got in alone.items():
            if got != f"['{expected}']":
                detail.append(f"{expected} -> {got}")

    # ---- the cycles ------------------------------------------------------
    def cycle(jobs: list[dict], **kw: object) -> dict:
        for item in jobs:
            enqueue_job(
                connection=session,
                organization_id=DEMO,
                job_id=item["job_id"],
                idempotency_key=item["job_id"],
                source_id=item["source_id"],
                schedule_key=f"{PREFIX}{stamp}",
                scheduled_for=NOW - timedelta(minutes=5),
                now=NOW,
            )
        result = run_worker_cycle(
            connection=session,
            organization_id=DEMO,
            worker_id=f"{PREFIX}{stamp}",
            jobs=jobs,
            now=NOW,
            **kw,
        )
        fails = worker_cycle_invariant_failures(result)
        if fails:
            detail.append(f"cycle:{fails}")
        return result

    ran = cycle(
        [job("run")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=REG.transport,
    )
    out["hermetic_job_flows_through"] = bool(ran["hermetic_executions"] == 1)
    out["worker_completed_nothing"] = bool(ran["jobs_completed"] == 0)
    out["worker_persisted_the_payload"] = bool(
        ran["hermetic_payloads_persisted"] == 1
        and ran["raw_payloads_written"] == 1
    )
    out["worker_produced_a_proof"] = bool(ran["hermetic_execution_proofs"] == 1)
    out["worker_live_counters_zero"] = bool(
        ran["collectors_invoked"] == 0
        and ran["live_source_calls"] == 0
        and ran["network_calls"] == 0
        and ran["urls_fetched"] == 0
        and ran["source_monitoring_live"] is False
        and ran["hermetic_execution_means_collection_occurred"] is False
    )

    default = cycle([job("default")])
    out["default_handler_executes_nothing"] = bool(
        default["hermetic_executions"] == 0
        and default["raw_payloads_written"] == 0
    )

    no_transport = cycle(
        [job("notransport")], handler=HANDLER_HERMETIC_EXECUTION
    )
    out["no_transport_executes_nothing"] = bool(
        no_transport["hermetic_executions"] == 0
        and no_transport["hermetic_transport_injected"] is False
    )

    real = cycle(
        [job("realsrc", source_id="grants.gov")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=REG.transport,
    )
    out["real_source_refused_by_the_worker"] = bool(
        real["hermetic_executions"] == 0 and real["raw_payloads_written"] == 0
    )

    from_store = run_worker_cycle(
        connection=session,
        organization_id=DEMO,
        worker_id=f"{PREFIX}{stamp}-store",
        jobs=None,
        now=NOW,
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=REG.transport,
        load_jobs_from_store=True,
        max_jobs=20,
    )
    detail.extend(worker_cycle_invariant_failures(from_store))
    out["store_loaded_job_refused"] = bool(
        from_store["hermetic_executions"] == 0
    )

    session.commit()
except Exception as exc:  # noqa: BLE001 - the phase reports rather than raises
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
    session.rollback()
finally:
    session.close()

for key in (
    "hermetic_job_flows_through", "worker_completed_nothing",
    "worker_persisted_the_payload", "worker_produced_a_proof",
    "default_handler_executes_nothing", "no_transport_executes_nothing",
    "real_source_refused_by_the_worker", "store_loaded_job_refused",
    "every_refusal_condition_fires_alone", "worker_live_counters_zero",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
