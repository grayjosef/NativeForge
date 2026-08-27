"""Gate 99 - dry-run scheduler runtime and job queue.

Hermetic. Nothing here fetches, dispatches, executes a collector, or writes a
payload, and a number of these tests exist specifically to prove that.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from nativeforge.services.phase1_collector_activation_policy_service import (
    PHASE1_SOURCE_IDS,
)
from nativeforge.services.source_schedule_decision_service import evaluate_schedule
from nativeforge.services.source_scheduler_dry_run_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    REFERENCE_NOW,
    REFERENCE_SCHEDULED_FOR,
    DryRunArtifactError,
    artifact_claim_failures,
    build_dry_run_bundle,
    build_phase1_schedule_decisions,
    render_dry_run_summary,
    write_dry_run_artifacts,
)
from nativeforge.services.source_scheduler_job_model_service import (
    DEFAULT_EXECUTION_MODE,
    EXECUTION_MODES,
    JOB_STATUSES,
    JOB_TYPES,
    LIVE_PRECONDITION_KEYS,
    NON_EXECUTED_STATUSES,
    build_idempotency_key,
    build_job_id,
    build_source_job,
    job_invariant_failures,
)
from nativeforge.services.source_scheduler_queue_service import (
    QUEUEABLE_SCHEDULE_STATUSES,
    build_dry_run_queue,
    queue_invariant_failures,
    summarise_queue,
)
from nativeforge.services.source_scheduler_readiness_service import (
    LIVE_RUNTIME_MODES,
    RUNTIME_AVAILABLE_MODES,
    RUNTIME_MODES,
    build_scheduler_readiness,
    detect_dry_run_runtime,
    scheduler_readiness_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts" / "run_nativeforge_source_scheduler_dry_run.py"

NOW = "2026-09-01T12:00:00+00:00"
PAST = "2026-09-01T06:00:00+00:00"
FUTURE = "2026-12-01T06:00:00+00:00"

GATE99_SERVICES = (
    "source_scheduler_job_model_service",
    "source_scheduler_queue_service",
    "source_scheduler_dry_run_artifact_service",
)

CLEARED_JOB = dict(
    collector_id="collector-1",
    job_type="source_check",
    scheduled_for=PAST,
    activation_status="activation_allowed",
    schedule_decision_status="due_and_safe_to_enqueue",
    circuit_status="closed",
    raw_payload_store_status="production_available",
)

CLEARED_DECISION = dict(
    next_check_due_at=PAST,
    collector_status="active",
    activation_status="activation_allowed",
    monitoring_status="enabled",
    terms_status="NO_REVIEW_REQUIRED",
    human_review_status="not_required",
    circuit_status="closed",
    production_raw_payload_store_available=True,
)


def _job(**overrides):
    return build_source_job(source_id="s1", **{**CLEARED_JOB, **overrides})


def _decision(source_id="s1", **overrides):
    return evaluate_schedule(
        source_id=source_id, now=NOW, **{**CLEARED_DECISION, **overrides}
    )


# --------------------------------------------------------------------------
# 99B - job model
# --------------------------------------------------------------------------


def test_job_id_is_deterministic() -> None:
    a = _job(created_at="2026-01-01T00:00:00Z")
    b = _job(created_at="2027-12-31T23:59:59Z")
    assert a["job_id"] == b["job_id"]
    assert len(a["job_id"]) == 64


def test_job_id_is_derivable_from_the_named_fields() -> None:
    job = _job()
    assert job["job_id"] == build_job_id(
        source_id="s1",
        collector_id="collector-1",
        job_type="source_check",
        scheduled_for=PAST,
        execution_mode=job["execution_mode"],
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collector_id", "collector-2"),
        ("job_type", "amendment_check"),
        ("scheduled_for", FUTURE),
    ],
)
def test_job_id_changes_when_its_inputs_change(field: str, value: str) -> None:
    assert _job()["job_id"] != _job(**{field: value})["job_id"]


def test_idempotency_key_is_deterministic() -> None:
    a = _job(created_at="2026-01-01T00:00:00Z", attempt_number=1)
    b = _job(created_at="2030-01-01T00:00:00Z", attempt_number=9)
    assert a["idempotency_key"] == b["idempotency_key"]


def test_idempotency_key_ignores_attempt_and_execution_mode() -> None:
    """A retry, and a dry rehearsal of a live job, are the same work."""
    base = build_idempotency_key(
        source_id="s1",
        collector_id="collector-1",
        job_type="source_check",
        scheduled_for=PAST,
    )
    assert _job(attempt_number=1)["idempotency_key"] == base
    assert _job(attempt_number=42)["idempotency_key"] == base
    assert _job(execution_mode="manual_review")["idempotency_key"] == base


def test_creating_a_job_executes_nothing() -> None:
    job = _job()
    assert job["executed"] is False
    assert job["fetch_performed"] is False
    assert job["collector_invoked"] is False
    assert job["raw_payload_written"] is False
    assert job["source_monitoring_live"] is False


def test_default_execution_mode_is_dry_run() -> None:
    assert DEFAULT_EXECUTION_MODE == "dry_run"
    assert build_source_job(source_id="s1")["execution_mode"] == "dry_run"
    assert _job()["execution_mode"] == "dry_run"


def test_live_collection_is_blocked_by_default() -> None:
    """Every precondition satisfied, and it still will not go live today."""
    job = _job(execution_mode="live_collection")
    assert job["requested_execution_mode"] == "live_collection"
    assert job["execution_mode"] == "dry_run"
    assert job["live_collection_granted"] is False
    assert "live_collection_downgraded" in job["blocked_reasons"]
    assert "background_worker_available" in job["live_preconditions_missing"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("activation_status", "activation_blocked"),
        ("activation_status", "activation_unknown"),
        ("schedule_decision_status", "due_but_blocked"),
        ("schedule_decision_status", "not_due"),
        ("circuit_status", "open"),
        ("circuit_status", "manual_hold"),
        ("raw_payload_store_status", "local_only"),
        ("raw_payload_store_status", "unavailable"),
    ],
)
def test_each_missing_precondition_prevents_a_live_job(
    field: str, value: str
) -> None:
    job = _job(**{field: value}, execution_mode="live_collection")
    assert job["execution_mode"] == "dry_run"
    assert job["live_collection_granted"] is False
    assert job["live_preconditions_missing"]


@pytest.mark.parametrize(
    "field",
    [
        "activation_status",
        "schedule_decision_status",
        "circuit_status",
        "raw_payload_store_status",
    ],
)
def test_an_unrecognised_status_blocks_rather_than_permits(field: str) -> None:
    job = _job(**{field: "something_nobody_defined"})
    assert job["job_status"] == "blocked"
    assert job["blocked_reasons"]


def test_an_unrecognised_execution_mode_falls_back_to_dry_run() -> None:
    assert _job(execution_mode="turbo")["execution_mode"] == "dry_run"


def test_an_unrecognised_job_type_falls_back_to_source_check() -> None:
    assert _job(job_type="whatever")["job_type"] == "source_check"


def test_a_blocked_job_states_why() -> None:
    job = _job(circuit_status="open")
    assert job["job_status"] == "blocked"
    assert job["blocked_reasons"]
    assert not job_invariant_failures(job)


def test_the_cleared_job_is_not_vacuous() -> None:
    """If nothing could ever be queued, every blocking test proves nothing."""
    assert _job()["job_status"] == "queued"


def test_job_vocabularies_are_the_declared_ones() -> None:
    assert JOB_TYPES == frozenset(
        {
            "source_check",
            "forecast_lapse_check",
            "amendment_check",
            "raw_payload_reconciliation",
            "terms_review_recheck",
        }
    )
    assert EXECUTION_MODES == frozenset(
        {"dry_run", "live_collection", "replay_fixture", "manual_review"}
    )
    assert JOB_STATUSES == frozenset(
        {
            "queued",
            "blocked",
            "skipped",
            "running",
            "completed",
            "failed",
            "cancelled",
        }
    )


def test_no_job_holds_an_execution_status() -> None:
    for job in (_job(), _job(circuit_status="open"), build_source_job(source_id="x")):
        assert job["job_status"] in NON_EXECUTED_STATUSES


def test_every_live_precondition_is_accounted_for_exactly_once() -> None:
    job = _job()
    satisfied = set(job["live_preconditions_satisfied"])
    missing = set(job["live_preconditions_missing"])
    assert not satisfied & missing
    assert satisfied | missing == set(LIVE_PRECONDITION_KEYS)


def test_job_invariants_reject_a_forged_live_job() -> None:
    forged = dict(
        _job(activation_status="activation_blocked"),
        execution_mode="live_collection",
    )
    fails = job_invariant_failures(forged)
    assert "live_collection_with_missing_preconditions" in fails
    assert "live_collection_without_activation" in fails


def test_job_invariants_reject_a_claim_of_execution() -> None:
    assert "job_claimed:executed" in job_invariant_failures(dict(_job(), executed=True))
    assert "job_claimed:fetch_performed" in job_invariant_failures(
        dict(_job(), fetch_performed=True)
    )


@pytest.mark.parametrize("status", ["running", "completed", "failed"])
def test_job_invariants_reject_an_execution_status(status: str) -> None:
    fails = job_invariant_failures(dict(_job(), job_status=status))
    assert f"job_status_implies_execution:{status}" in fails


def test_job_invariants_reject_a_tampered_identity() -> None:
    assert "job_id_not_derivable_from_its_fields" in job_invariant_failures(
        dict(_job(), job_id="0" * 64)
    )
    assert "idempotency_key_not_derivable_from_its_fields" in job_invariant_failures(
        dict(_job(), idempotency_key="0" * 64)
    )


def test_job_invariants_reject_a_blocked_job_marked_queued() -> None:
    blocked = _job(circuit_status="open")
    fails = job_invariant_failures(dict(blocked, job_status="queued"))
    assert "queued_despite_blocking_reasons" in fails


# --------------------------------------------------------------------------
# 99C - dry-run queue
# --------------------------------------------------------------------------


def _mixed_decisions() -> list[dict]:
    return [
        _decision("clear_a"),
        _decision("clear_b"),
        _decision("circuit_open", circuit_status="open"),
        _decision("terms_review", terms_status="TERMS_REVIEW_REQUIRED"),
        _decision("no_store", production_raw_payload_store_available=False),
        _decision("not_due", next_check_due_at=FUTURE),
        _decision("disabled", monitoring_status="disabled"),
        _decision("no_schedule", next_check_due_at=None),
    ]


def test_queue_creates_dry_run_jobs_only() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    assert queue["execution_mode"] == "dry_run"
    assert queue["dry_run_only"] is True
    assert all(j["execution_mode"] == "dry_run" for j in queue["jobs"])
    assert not queue_invariant_failures(queue)


def test_live_jobs_created_is_zero() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    assert queue["live_jobs_created"] == 0


def test_allow_live_collection_still_produces_no_live_jobs() -> None:
    """The flag exists; today it changes nothing, and the count proves it."""
    queue = build_dry_run_queue(
        decisions=_mixed_decisions(), scheduled_for=PAST, allow_live_collection=True
    )
    assert queue["requested_execution_mode"] == "live_collection"
    assert queue["execution_mode"] == "dry_run"
    assert queue["live_jobs_created"] == 0
    assert queue["dry_run_only"] is True
    assert not queue_invariant_failures(queue)


def test_the_live_count_is_derived_from_the_jobs_not_the_request(monkeypatch) -> None:
    """Nothing can produce a live job today, so force one and check the count.

    Without this the live-job counter is untestable: it reads zero whether it
    counts the jobs or returns a constant, because zero is the only answer the
    system can currently produce. A mutation replacing the count with `[]`
    survived the rest of this file.
    """
    import nativeforge.services.source_scheduler_queue_service as mod

    real = mod.build_source_job

    def forced_live(**kwargs):
        job = real(**kwargs)
        return dict(
            job,
            execution_mode="live_collection",
            live_collection_granted=True,
            live_preconditions_missing=[],
            live_preconditions_satisfied=sorted(LIVE_PRECONDITION_KEYS),
        )

    monkeypatch.setattr(mod, "build_source_job", forced_live)
    queue = mod.build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)

    assert queue["live_jobs_created"] == queue["jobs_total"] > 0
    assert queue["dry_run_only"] is False
    assert queue["execution_mode"] == "live_collection"


def test_queue_source_monitoring_live_remains_false() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    assert queue["source_monitoring_live"] is False
    assert queue["live_source_coverage"] is False


def test_queue_deduplicates_by_idempotency_key() -> None:
    decisions = [_decision("clear_a")] * 3 + [_decision("clear_b")]
    queue = build_dry_run_queue(decisions=decisions, scheduled_for=PAST)
    assert queue["jobs_total"] == 2
    assert queue["jobs_deduplicated"] == 2
    keys = [j["idempotency_key"] for j in queue["jobs"]]
    assert len(keys) == len(set(keys))


def test_blocked_sources_remain_represented() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    present = {j["source_id"] for j in queue["jobs"]}
    for source_id in ("circuit_open", "terms_review", "no_store", "no_schedule"):
        assert source_id in present, source_id
    assert queue["jobs_blocked"] >= 4
    assert queue["blocked_reasons"]


def test_not_due_and_disabled_sources_are_not_queued() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    present = {j["source_id"] for j in queue["jobs"]}
    assert "not_due" not in present
    assert "disabled" not in present
    assert queue["decisions_not_queueable"] == 2


def test_queueable_statuses_exclude_the_ones_with_nothing_to_do() -> None:
    assert "not_due" not in QUEUEABLE_SCHEDULE_STATUSES
    assert "disabled" not in QUEUEABLE_SCHEDULE_STATUSES


def test_queue_is_order_independent() -> None:
    decisions = _mixed_decisions()
    forward = build_dry_run_queue(decisions=decisions, scheduled_for=PAST)
    backward = build_dry_run_queue(
        decisions=list(reversed(decisions)), scheduled_for=PAST
    )
    assert forward["queue_id"] == backward["queue_id"]
    assert [j["job_id"] for j in forward["jobs"]] == [
        j["job_id"] for j in backward["jobs"]
    ]


def test_an_empty_queue_is_valid() -> None:
    queue = build_dry_run_queue(decisions=[], scheduled_for=PAST)
    assert queue["jobs_total"] == 0
    assert queue["live_jobs_created"] == 0
    assert not queue_invariant_failures(queue)


def test_queue_reports_no_dispatch_or_collector_activity() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    assert queue["jobs_dispatched"] == 0
    assert queue["collectors_executed"] is False
    assert queue["live_fetch_performed"] is False
    assert queue["raw_payloads_written"] is False


def test_queue_summary_carries_no_job_bodies() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    summary = summarise_queue(queue)
    assert "jobs" not in summary
    assert summary["jobs_dispatched"] == 0
    assert summary["by_execution_mode"]["live_collection"] == 0


def test_queue_invariants_reject_a_forged_live_count() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    fails = queue_invariant_failures(dict(queue, live_jobs_created=3))
    assert "live_job_count_disagrees_with_the_jobs" in fails


def test_queue_invariants_reject_dropped_blocked_jobs() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    trimmed = [j for j in queue["jobs"] if j["job_status"] != "blocked"]
    fails = queue_invariant_failures(dict(queue, jobs=trimmed))
    assert "jobs_total_disagrees_with_the_jobs" in fails


def test_queue_invariants_reject_a_smuggled_live_job() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    smuggled = dict(queue["jobs"][0], execution_mode="live_collection")
    fails = queue_invariant_failures(
        dict(queue, jobs=[smuggled] + queue["jobs"][1:])
    )
    assert any("live" in f for f in fails)


def test_queue_invariants_reject_a_monitoring_claim() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    fails = queue_invariant_failures(dict(queue, source_monitoring_live=True))
    assert "queue_claimed:source_monitoring_live" in fails


def test_queue_invariants_reject_a_tampered_queue_id() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    fails = queue_invariant_failures(dict(queue, queue_id="0" * 64))
    assert "queue_id_not_derivable_from_its_contents" in fails


def test_queue_invariants_reject_duplicate_keys() -> None:
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    doubled = queue["jobs"] + [queue["jobs"][0]]
    fails = queue_invariant_failures(dict(queue, jobs=doubled))
    assert "duplicate_idempotency_key_in_the_queue" in fails


# --------------------------------------------------------------------------
# 99C - the queue cannot fetch or collect
# --------------------------------------------------------------------------


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE99_SERVICES)
def test_no_gate99_service_imports_an_http_client(name: str) -> None:
    """Planning a fetch must not be able to perform one."""
    banned = {
        "requests",
        "httpx",
        "aiohttp",
        "urllib.request",
        "urllib3",
        "http.client",
        "socket",
    }
    tree = ast.parse(_service_source(name))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not imported & banned, f"{name} imports {imported & banned}"


@pytest.mark.parametrize("name", GATE99_SERVICES)
def test_no_gate99_service_imports_a_collector_or_fetcher(name: str) -> None:
    """The queue may name a collector. It may not be able to call one."""
    tree = ast.parse(_service_source(name))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    offending = {
        m
        for m in modules
        if any(
            token in m
            for token in (
                "polite_http",
                "live_network_guard",
                "real_url_resolver",
                "live_fetch",
                "source_connectors",
                "source_check_bridge",
                "body_store",
            )
        )
    }
    assert not offending, f"{name} imports {offending}"


@pytest.mark.parametrize("name", GATE99_SERVICES)
def test_no_gate99_service_writes_to_the_database(name: str) -> None:
    banned = {"sqlalchemy", "psycopg", "psycopg2", "asyncpg"}
    tree = ast.parse(_service_source(name))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not roots & banned, f"{name} imports {roots & banned}"


@pytest.mark.parametrize("name", GATE99_SERVICES)
def test_every_gate99_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


# --------------------------------------------------------------------------
# 99D - runtime readiness
# --------------------------------------------------------------------------


def test_runtime_mode_is_dry_run_in_process() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["runtime_mode"] == "dry_run_in_process"
    assert not scheduler_readiness_invariant_failures(readiness)


def test_scheduler_runtime_available_is_true_in_dry_run_mode() -> None:
    """Gate 99 may make this true. `runtime_mode` says what kind of true."""
    readiness = build_scheduler_readiness()
    assert readiness["scheduler_runtime_available"] is True
    assert readiness["runtime_mode"] in RUNTIME_AVAILABLE_MODES


def test_the_three_facts_gate_99_may_not_change_remain_false() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["background_worker_available"] is False
    assert readiness["source_monitoring_live"] is False
    assert readiness["ready_to_start_monitoring"] is False


def test_a_dry_run_runtime_executes_nothing() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["runtime_executes_jobs"] is False
    assert readiness["runtime_mode"] not in LIVE_RUNTIME_MODES
    assert detect_dry_run_runtime()["executes_jobs"] is False
    assert detect_dry_run_runtime()["fetches"] is False


def test_no_scheduler_package_is_installed() -> None:
    """Distinct from the runtime question, and still the Gate 98 answer."""
    assert build_scheduler_readiness()["scheduler_package_installed"] is False


def test_the_dry_run_runtime_requires_both_modules() -> None:
    detected = detect_dry_run_runtime()
    assert detected["available"] is True
    assert set(detected["modules_found"]) == set(detected["modules_required"])


def test_runtime_mode_detection_is_live_not_hardcoded(monkeypatch) -> None:
    """Each rung of the ladder is reachable from its own evidence."""
    import nativeforge.services.source_scheduler_readiness_service as mod

    def _worker(available: bool):
        return {
            "available": available,
            "detection_method": "test",
            "worker_modules": [],
            "worker_entry_points": [],
            "modules_considered": [],
        }

    def _trigger(available: bool):
        return lambda *, repo_root=None: {
            "available": available,
            "detection_method": "test",
            "trigger_files": [],
            "searched_directories": [],
            "searched_suffixes": [],
            "host_schedulers_inspected": False,
        }

    def _dry(available: bool):
        return {
            "available": available,
            "detection_method": "test",
            "modules_found": [],
            "modules_required": [],
            "executes_jobs": False,
            "fetches": False,
        }

    cases = [
        (False, False, False, "none"),
        (False, False, True, "dry_run_in_process"),
        (True, False, True, "external_worker_configured"),
        (True, True, True, "production_worker_live"),
    ]
    for worker, trigger, dry, expected in cases:
        monkeypatch.setattr(
            mod, "detect_background_worker", lambda w=worker: _worker(w)
        )
        monkeypatch.setattr(mod, "detect_periodic_trigger", _trigger(trigger))
        monkeypatch.setattr(mod, "detect_dry_run_runtime", lambda d=dry: _dry(d))
        assert mod.detect_runtime_mode()["runtime_mode"] == expected


def test_a_dry_run_mode_cannot_be_read_as_monitoring_even_with_worker_and_trigger(
    monkeypatch,
) -> None:
    """The guard on `source_monitoring_live` tests the mode, not the boolean.

    Today it is belt-and-braces: the mode is derived from the worker and the
    trigger, so a dry-run mode alongside both of them cannot arise naturally,
    and a mutation loosening the test to `RUNTIME_AVAILABLE_MODES` survived
    every other test in this file. This forces the inconsistent state directly,
    which is the one the guard exists for - a future change to the mode ladder
    that makes it reachable should fail here rather than start monitoring.
    """
    import nativeforge.services.source_scheduler_readiness_service as mod

    monkeypatch.setattr(
        mod,
        "detect_background_worker",
        lambda: {
            "available": True,
            "detection_method": "test",
            "worker_modules": [],
            "worker_entry_points": [],
            "modules_considered": [],
        },
    )
    monkeypatch.setattr(
        mod,
        "detect_periodic_trigger",
        lambda *, repo_root=None: {
            "available": True,
            "detection_method": "test",
            "trigger_files": [],
            "searched_directories": [],
            "searched_suffixes": [],
            "host_schedulers_inspected": False,
        },
    )
    monkeypatch.setattr(
        mod,
        "detect_runtime_mode",
        lambda *, repo_root=None: {
            "runtime_mode": "dry_run_in_process",
            "evidence": "test",
            "detection_method": "test",
            "dry_run_runtime_available": True,
            "background_worker_available": True,
            "periodic_trigger_available": True,
            "executes_jobs": False,
        },
    )

    readiness = mod.build_scheduler_readiness()
    assert readiness["background_worker_available"] is True
    assert readiness["periodic_trigger_available"] is True
    assert readiness["runtime_mode"] == "dry_run_in_process"
    # The whole point: both runtime components present, and still not live.
    assert readiness["source_monitoring_live"] is False


def test_readiness_invariants_reject_a_forged_live_mode() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, runtime_mode="production_worker_live")
    )
    assert "worker_mode_without_a_detected_worker" in fails
    assert "live_mode_without_a_periodic_trigger" in fails


def test_readiness_invariants_reject_a_dry_run_runtime_claiming_execution() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, runtime_executes_jobs=True)
    )
    assert "dry_run_runtime_claimed_execution" in fails


def test_readiness_invariants_reject_a_dry_run_runtime_read_as_monitoring() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, source_monitoring_live=True)
    )
    assert "dry_run_runtime_read_as_live_monitoring" in fails


def test_readiness_invariants_reject_a_boolean_that_disagrees_with_its_mode() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, scheduler_runtime_available=False)
    )
    assert "runtime_available_disagrees_with_the_runtime_mode" in fails


def test_runtime_mode_vocabulary_is_closed() -> None:
    assert build_scheduler_readiness()["runtime_mode"] in RUNTIME_MODES
    fails = scheduler_readiness_invariant_failures(
        dict(build_scheduler_readiness(), runtime_mode="turbo")
    )
    assert "runtime_mode_out_of_vocabulary" in fails


def test_a_dry_run_runtime_does_not_make_any_source_schedulable() -> None:
    """Gate 98F must be unaffected: scheduling still needs a worker."""
    import nativeforge.services.phase1_collector_activation_policy_service as pol
    import nativeforge.services.source_activation_preflight_service as pre

    assert pre._scheduler_runtime_available() is False
    assert pol._scheduler_runtime_available() is False
    assert pol._monitoring_live() is False

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["sources_may_schedule_monitor"] == 0
    assert matrix["monitors_active"] == 0
    assert not pol.policy_invariant_failures(matrix)


# --------------------------------------------------------------------------
# 99E - CLI
# --------------------------------------------------------------------------


def test_the_cli_script_exists_and_is_executable() -> None:
    assert CLI_PATH.exists()
    mode = CLI_PATH.stat().st_mode
    assert mode & stat.S_IXUSR, "CLI lost its executable bit"


def test_the_cli_exits_zero_without_doing_live_work() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert "live_jobs_created   0" in proc.stdout
    assert "dry_run_in_process" in proc.stdout


def test_the_cli_json_mode_reports_no_live_jobs() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["live_jobs_created"] == 0
    assert payload["source_monitoring_live"] is False
    assert payload["collectors_executed"] is False


def test_the_cli_refuses_when_a_live_job_appears() -> None:
    """The refusal is on the produced jobs, not on the requested mode."""
    spec = importlib.util.spec_from_file_location("gate99_cli", CLI_PATH)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    real = cli.build_dry_run_bundle

    def with_live(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        job = dict(bundle["queue"]["jobs"][0], execution_mode="live_collection")
        bundle["queue"] = dict(
            bundle["queue"],
            jobs=[job] + bundle["queue"]["jobs"][1:],
            live_jobs_created=1,
            dry_run_only=False,
        )
        return bundle

    cli.build_dry_run_bundle = with_live
    try:
        assert cli.main([]) == cli.EXIT_LIVE_WORK
    finally:
        cli.build_dry_run_bundle = real


def test_the_cli_prints_no_secrets() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    combined = proc.stdout + proc.stderr
    for marker in ("-----BEGIN", "eyJ", "Bearer ", "api_key=", "SECRET", "PASSWORD"):
        assert marker not in combined, marker


def test_the_cli_makes_no_network_call(monkeypatch) -> None:
    """Import and run it in-process with sockets poisoned."""
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("the dry-run CLI attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    spec = importlib.util.spec_from_file_location("gate99_cli_net", CLI_PATH)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main([]) == 0


# --------------------------------------------------------------------------
# 99F - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_dry_run_artifacts(repo_root=first)
    write_dry_run_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    write_dry_run_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_four_artifacts_are_written(tmp_path: Path) -> None:
    result = write_dry_run_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 4
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_seven_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_runtime_mode(name: str) -> None:
    """`scheduler_runtime_available: true` alone would be read as production."""
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    assert "dry_run_in_process" in path.read_text(encoding="utf-8"), name


def test_the_csv_stamps_declarations_on_every_row() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_dry_run_queue.csv"
    if not path.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(PHASE1_SOURCE_IDS) + 1
    for line in lines[1:]:
        assert line.endswith("True,0,False,False,False,False,False"), line


def test_the_queue_json_declares_no_live_work() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_dry_run_queue.json"
    if not path.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["live_jobs_created"] == 0
    assert payload["dry_run_only"] is True
    assert payload["collectors_executed"] is False
    assert payload["live_fetch_performed"] is False
    assert payload["raw_payloads_written"] is False
    assert payload["source_monitoring_live"] is False
    assert payload["live_source_coverage"] is False


def test_the_readiness_json_declares_the_runtime_mode() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_runtime_readiness.json"
    if not path.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["runtime_mode"] == "dry_run_in_process"
    assert payload["readiness"]["background_worker_available"] is False
    assert payload["readiness"]["source_monitoring_live"] is False
    assert payload["readiness"]["ready_to_start_monitoring"] is False


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_dry_run_bundle(repo_root=REPO_ROOT)
    assert artifact_claim_failures(bundle, render_dry_run_summary(bundle)) == []


def test_the_writer_refuses_a_live_job(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.source_scheduler_dry_run_artifact_service as mod

    real = mod.build_dry_run_bundle

    def with_live(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        job = dict(bundle["queue"]["jobs"][0], execution_mode="live_collection")
        bundle["queue"] = dict(
            bundle["queue"],
            jobs=[job] + bundle["queue"]["jobs"][1:],
            live_jobs_created=1,
            dry_run_only=False,
        )
        return bundle

    monkeypatch.setattr(mod, "build_dry_run_bundle", with_live)
    with pytest.raises(DryRunArtifactError):
        mod.write_dry_run_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.source_scheduler_dry_run_artifact_service as mod

    real = mod.build_dry_run_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["source_monitoring_live"] = True
        return bundle

    monkeypatch.setattr(mod, "build_dry_run_bundle", lying)
    with pytest.raises(DryRunArtifactError):
        mod.write_dry_run_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_artifact_queue_covers_the_real_phase1_sources() -> None:
    """Not a fixture. The five sources, with the state they actually have."""
    decisions = build_phase1_schedule_decisions()
    assert [d["source_id"] for d in decisions] == list(PHASE1_SOURCE_IDS)
    assert all(d["schedule_status"] == "unknown" for d in decisions)


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("dry-run artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key="):
            assert marker not in text, f"{path.name} contains {marker!r}"


def test_the_reference_clock_is_fixed_not_a_real_now() -> None:
    """A real `now` would make committed artifacts never match a fresh run."""
    assert REFERENCE_NOW == "2026-01-01T12:00:00+00:00"
    assert REFERENCE_SCHEDULED_FOR == "2026-01-01T06:00:00+00:00"


def test_the_artifact_dir_is_not_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", f"{ARTIFACT_DIR}/{ARTIFACT_NAMES[0]}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert proc.returncode != 0, "dry-run artifacts are gitignored"


# --------------------------------------------------------------------------
# 99 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_creates_no_live_work_anywhere() -> None:
    readiness = build_scheduler_readiness()
    queue = build_dry_run_queue(decisions=_mixed_decisions(), scheduled_for=PAST)
    assert readiness["scheduled_jobs_started"] == 0
    assert readiness["checks_executed"] == 0
    assert readiness["live_fetch_performed"] is False
    assert readiness["collectors_active"] is False
    assert readiness["live_source_coverage"] is False
    assert queue["live_jobs_created"] == 0
    assert queue["jobs_dispatched"] == 0


def test_no_environment_variable_can_turn_on_live_collection(monkeypatch) -> None:
    """There is no env switch. Live work needs a worker that does not exist."""
    for name in (
        "NF_ALLOW_LIVE_COLLECTION",
        "NF_SCHEDULER_LIVE",
        "NF_SOURCE_MONITORING_LIVE",
    ):
        monkeypatch.setenv(name, "true")
    os.environ.setdefault("NF_APP_ENV", "test")
    job = _job(execution_mode="live_collection")
    queue = build_dry_run_queue(
        decisions=_mixed_decisions(), scheduled_for=PAST, allow_live_collection=True
    )
    assert job["execution_mode"] == "dry_run"
    assert queue["live_jobs_created"] == 0
