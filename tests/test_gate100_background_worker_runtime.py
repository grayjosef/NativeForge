"""Gate 100 - background worker runtime decision and dry-run worker.

Hermetic. Nothing here starts a worker, calls a collector, fetches a URL, or
writes a payload, and a number of these tests exist specifically to prove that.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
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
    build_phase1_schedule_decisions,
)
from nativeforge.services.source_scheduler_dry_run_worker_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    FALSE_DECLARATION_KEYS,
    DryRunWorkerArtifactError,
    artifact_claim_failures,
    build_worker_bundle,
    render_worker_summary,
    write_worker_artifacts,
)
from nativeforge.services.source_scheduler_dry_run_worker_service import (
    PROCESSED_OUTCOMES,
    REFUSED_OUTCOMES,
    WORKER_OUTCOMES,
    build_worker_run_id,
    run_dry_run_worker,
    summarise_worker_run,
    worker_invariant_failures,
)
from nativeforge.services.source_scheduler_queue_service import build_dry_run_queue
from nativeforge.services.source_scheduler_readiness_service import (
    DRY_RUN_COMPONENT_KEYS,
    RUNTIME_COMPONENT_KEYS,
    build_scheduler_readiness,
    detect_dry_run_worker,
    scheduler_readiness_invariant_failures,
)
from nativeforge.services.source_scheduler_readiness_service import (
    RUNTIME_MODES as DETECTED_RUNTIME_MODES,
)
from nativeforge.services.source_worker_runtime_decision_service import (
    BACKGROUND_WORKER_MODES,
    BROKER_CANDIDATES,
    DECISION_ONLY_RUNTIME_MODES,
    NEXT_ACTION_SEQUENCE,
    PRODUCTION_WORKER_MODES,
    RUNTIME_MODES,
    build_worker_runtime_decision,
    worker_runtime_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = (
    REPO_ROOT / "scripts" / "run_nativeforge_source_scheduler_dry_run_worker.py"
)

NOW = "2026-09-01T12:00:00+00:00"
PAST = "2026-09-01T06:00:00+00:00"

GATE100_SERVICES = (
    "source_worker_runtime_decision_service",
    "source_scheduler_dry_run_worker_service",
    "source_scheduler_dry_run_worker_artifact_service",
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


def _decision(source_id="s1", **overrides):
    return evaluate_schedule(
        source_id=source_id, now=NOW, **{**CLEARED_DECISION, **overrides}
    )


def _mixed_queue():
    return build_dry_run_queue(
        decisions=[
            _decision("clear_a"),
            _decision("clear_b"),
            _decision("circuit_open", circuit_status="open"),
            _decision("terms_review", terms_status="TERMS_REVIEW_REQUIRED"),
            _decision("no_store", production_raw_payload_store_available=False),
        ],
        scheduled_for=PAST,
    )


# --------------------------------------------------------------------------
# 100B - runtime decision
# --------------------------------------------------------------------------


def test_the_runtime_decision_defaults_safe() -> None:
    decision = build_worker_runtime_decision()
    assert decision["production_worker_live"] is False
    assert decision["background_worker_available"] is False
    assert decision["worker_started"] is False
    assert decision["source_monitoring_live"] is False
    assert not worker_runtime_invariant_failures(decision)


def test_dry_run_in_process_does_not_mean_a_production_worker_is_live() -> None:
    decision = build_worker_runtime_decision()
    assert decision["runtime_mode"] == "dry_run_in_process"
    assert decision["worker_runtime_available"] is True
    assert decision["production_worker_live"] is False
    assert decision["background_worker_available"] is False


def test_background_worker_available_remains_false() -> None:
    assert build_worker_runtime_decision()["background_worker_available"] is False
    assert build_scheduler_readiness()["background_worker_available"] is False


def test_production_worker_live_remains_false() -> None:
    assert build_worker_runtime_decision()["production_worker_live"] is False


def test_an_external_worker_is_still_required() -> None:
    """Having a dry-run runtime is not having a worker."""
    decision = build_worker_runtime_decision()
    assert decision["external_worker_required"] is True
    assert decision["dry_run_worker_available"] is True
    assert "background_worker_not_detected" in decision["blocked_reasons"]


def test_the_decision_only_mode_is_not_in_the_detected_vocabulary() -> None:
    """Detection cannot produce a conclusion a person reached."""
    assert DECISION_ONLY_RUNTIME_MODES == frozenset({"external_worker_required"})
    assert not DECISION_ONLY_RUNTIME_MODES & DETECTED_RUNTIME_MODES
    assert DECISION_ONLY_RUNTIME_MODES < RUNTIME_MODES


def test_no_dependency_is_required_for_the_dry_run_worker() -> None:
    decision = build_worker_runtime_decision()
    assert decision["dry_run_worker_requires_dependency"] is False
    assert decision["dependency_required"] is False
    assert decision["dependency_selected"] is None


def test_no_broker_is_selected() -> None:
    decision = build_worker_runtime_decision()
    assert decision["broker_selected"] is None
    assert "broker_not_selected" in decision["blocked_reasons"]
    assert set(decision["broker_candidates"]) == set(BROKER_CANDIDATES)


def test_selecting_a_broker_makes_a_dependency_required() -> None:
    decision = build_worker_runtime_decision(selected_broker="redis")
    assert decision["broker_selected"] == "redis"
    assert decision["broker_required"] is True
    assert decision["dependency_required"] is True
    assert not worker_runtime_invariant_failures(decision)


def test_a_systemd_timer_worker_needs_no_broker() -> None:
    decision = build_worker_runtime_decision(selected_broker="none_systemd_timer")
    assert decision["broker_required"] is False
    assert decision["dependency_required"] is False


def test_an_unrecognised_broker_is_not_selected() -> None:
    decision = build_worker_runtime_decision(selected_broker="not_a_broker")
    assert decision["broker_selected"] is None
    assert decision["dependency_required"] is False


def test_the_prerequisite_order_puts_deployment_first() -> None:
    """Choosing a broker before a deploy buys infrastructure for nothing."""
    decision = build_worker_runtime_decision()
    actions = [a["action"] for a in decision["next_required_actions"]]
    assert actions == [a for a, _ in NEXT_ACTION_SEQUENCE]
    assert actions[0] == "deploy_backend_process"
    assert actions.index("choose_worker_topology") < actions.index(
        "select_broker_if_external"
    )


def test_the_decision_reports_no_live_work() -> None:
    decision = build_worker_runtime_decision()
    for key in (
        "source_monitoring_live",
        "collectors_executed",
        "urls_fetched",
        "raw_payloads_written",
        "live_source_coverage",
        "worker_started",
    ):
        assert decision[key] is False, key


def test_the_decision_follows_a_real_worker_when_one_appears(monkeypatch) -> None:
    """Not a hardcoded false: give it a worker and the answer changes."""
    import nativeforge.services.source_worker_runtime_decision_service as mod

    real = mod.build_scheduler_readiness
    monkeypatch.setattr(
        mod,
        "build_scheduler_readiness",
        lambda *, repo_root=None: dict(
            real(repo_root=repo_root),
            background_worker_available=True,
            runtime_mode="external_worker_configured",
        ),
    )
    decision = mod.build_worker_runtime_decision()
    assert decision["background_worker_available"] is True
    assert decision["runtime_mode"] == "external_worker_configured"
    assert decision["external_worker_required"] is False
    # Still not live: a configured worker is not a running one.
    assert decision["production_worker_live"] is False
    assert not worker_runtime_invariant_failures(decision)


def test_decision_invariants_reject_a_forged_production_claim() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, production_worker_live=True)
    )
    assert "production_worker_live_disagrees_with_the_mode" in fails


def test_decision_invariants_reject_a_forged_worker_claim() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, background_worker_available=True)
    )
    assert "dry_run_runtime_read_as_a_background_worker" in fails


def test_decision_invariants_reject_reordered_prerequisites() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(
            decision,
            next_required_actions=list(reversed(decision["next_required_actions"])),
        )
    )
    assert "next_required_actions_reordered_or_dropped" in fails


def test_decision_invariants_reject_a_dependency_without_a_broker() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(dict(decision, dependency_required=True))
    assert "dependency_required_without_a_selected_broker" in fails


def test_decision_invariants_reject_a_dry_run_dependency_claim() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, dry_run_worker_requires_dependency=True)
    )
    assert "dry_run_worker_claimed_a_dependency" in fails


def test_worker_modes_exclude_the_decision_only_mode() -> None:
    assert "external_worker_required" not in BACKGROUND_WORKER_MODES
    assert "external_worker_required" not in PRODUCTION_WORKER_MODES


# --------------------------------------------------------------------------
# 100C - dry-run worker
# --------------------------------------------------------------------------


def test_the_worker_accepts_dry_run_queued_jobs() -> None:
    queue = build_dry_run_queue(
        decisions=[_decision("clear_a"), _decision("clear_b")], scheduled_for=PAST
    )
    result = run_dry_run_worker(queue=queue)
    assert result["jobs_seen"] == 2
    assert result["jobs_completed_dry_run"] == 2
    assert result["jobs_blocked_dry_run"] == 0
    assert not worker_invariant_failures(result)


def test_the_completed_case_is_not_vacuous() -> None:
    """If nothing could ever complete, every refusal test proves nothing."""
    queue = build_dry_run_queue(decisions=[_decision("clear_a")], scheduled_for=PAST)
    assert run_dry_run_worker(queue=queue)["jobs_completed_dry_run"] == 1


def test_the_worker_refuses_live_collection_jobs() -> None:
    queue = _mixed_queue()
    job = dict(queue["jobs"][0], execution_mode="live_collection")
    result = run_dry_run_worker(jobs=[job], queue_id="q")
    assert result["results"][0]["outcome"] == "refused_live"
    assert result["live_jobs_refused"] == 1
    assert result["jobs_processed"] == 0
    assert not worker_invariant_failures(result)


@pytest.mark.parametrize("status", ["running", "completed", "failed"])
def test_the_worker_refuses_jobs_that_claim_execution(status: str) -> None:
    """Such a job did not come from Gate 99's queue, which rejects them."""
    queue = _mixed_queue()
    job = dict(queue["jobs"][0], job_status=status)
    result = run_dry_run_worker(jobs=[job], queue_id="q")
    assert result["results"][0]["outcome"] == "refused_invalid_status"
    assert result["jobs_processed"] == 0


def test_the_worker_refuses_an_unrecognised_execution_mode() -> None:
    queue = _mixed_queue()
    job = dict(queue["jobs"][0], execution_mode="turbo")
    result = run_dry_run_worker(jobs=[job], queue_id="q")
    assert result["results"][0]["outcome"] == "refused_unknown_mode"


@pytest.mark.parametrize("mode", ["replay_fixture", "manual_review"])
def test_the_worker_leaves_modes_it_does_not_handle_alone(mode: str) -> None:
    queue = _mixed_queue()
    job = dict(queue["jobs"][0], execution_mode=mode)
    result = run_dry_run_worker(jobs=[job], queue_id="q")
    assert result["results"][0]["outcome"] == "skipped_not_processable"
    assert result["jobs_processed"] == 0


def test_the_worker_marks_blocked_jobs_and_preserves_their_reasons() -> None:
    queue = _mixed_queue()
    blocked = [j for j in queue["jobs"] if j["job_status"] == "blocked"]
    assert blocked, "fixture must contain a blocked job"
    result = run_dry_run_worker(jobs=blocked, queue_id="q")
    assert result["jobs_blocked_dry_run"] == len(blocked)
    for job, row in zip(
        sorted(blocked, key=lambda j: j["job_id"]),
        sorted(result["results"], key=lambda r: r["job_id"]),
        strict=True,
    ):
        assert row["outcome"] == "blocked_dry_run"
        assert row["blocked_reasons"] == sorted(set(job["blocked_reasons"]))


def test_the_worker_keeps_every_job_it_saw() -> None:
    """Dropping refused jobs would report a clean sweep over the liked ones."""
    queue = _mixed_queue()
    jobs = list(queue["jobs"]) + [
        dict(queue["jobs"][0], execution_mode="live_collection")
    ]
    result = run_dry_run_worker(jobs=jobs, queue_id="q")
    assert result["jobs_seen"] == len(jobs)
    assert len(result["results"]) == len(jobs)


def test_the_worker_executes_nothing() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    assert result["collectors_executed"] is False
    assert result["urls_fetched"] is False
    assert result["raw_payloads_written"] is False
    assert result["source_monitoring_live"] is False
    for row in result["results"]:
        assert row["collector_invoked"] is False
        assert row["url_fetched"] is False
        assert row["raw_payload_written"] is False


def test_the_worker_output_is_deterministic() -> None:
    queue = _mixed_queue()
    first = run_dry_run_worker(queue=queue)
    second = run_dry_run_worker(queue=queue)
    assert first["worker_run_id"] == second["worker_run_id"]
    assert first == second


def test_the_worker_is_order_independent() -> None:
    queue = _mixed_queue()
    reversed_queue = dict(queue, jobs=list(reversed(queue["jobs"])))
    assert (
        run_dry_run_worker(queue=queue)["worker_run_id"]
        == run_dry_run_worker(queue=reversed_queue)["worker_run_id"]
    )


def test_the_run_id_has_no_clock_in_it() -> None:
    queue = _mixed_queue()
    result = run_dry_run_worker(queue=queue)
    assert result["worker_run_id"] == build_worker_run_id(
        queue_id=queue["queue_id"],
        job_ids=[str(r["job_id"]) for r in result["results"]],
    )
    assert len(result["worker_run_id"]) == 64


def test_an_empty_queue_is_valid() -> None:
    result = run_dry_run_worker(jobs=[], queue_id="q")
    assert result["jobs_seen"] == 0
    assert not worker_invariant_failures(result)


def test_the_worker_summary_carries_no_job_bodies() -> None:
    summary = summarise_worker_run(run_dry_run_worker(queue=_mixed_queue()))
    assert "results" not in summary
    assert summary["collectors_executed"] is False


def test_outcome_vocabulary_is_closed() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    for row in result["results"]:
        assert row["outcome"] in WORKER_OUTCOMES
    assert PROCESSED_OUTCOMES & REFUSED_OUTCOMES == frozenset()


@pytest.mark.parametrize(
    "key",
    [
        "collectors_executed",
        "urls_fetched",
        "raw_payloads_written",
        "source_monitoring_live",
    ],
)
def test_worker_invariants_reject_a_side_effect_claim(key: str) -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    assert f"worker_claimed:{key}" in worker_invariant_failures(
        dict(result, **{key: True})
    )


def test_worker_invariants_reject_a_live_job_marked_processed() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    forged = dict(
        result["results"][0],
        input_execution_mode="live_collection",
        outcome="completed_dry_run",
        blocked_reasons=[],
    )
    fails = worker_invariant_failures(
        dict(result, results=[forged] + result["results"][1:])
    )
    assert any("live_job_not_refused" in f for f in fails)


def test_worker_invariants_reject_an_executed_job_marked_processed() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    forged = dict(
        result["results"][0],
        input_job_status="running",
        outcome="completed_dry_run",
        blocked_reasons=[],
    )
    fails = worker_invariant_failures(
        dict(result, results=[forged] + result["results"][1:])
    )
    assert any("executed_job_processed" in f for f in fails)


def test_worker_invariants_reject_stripped_reasons() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    fails = worker_invariant_failures(dict(result, blocked_reasons=[]))
    assert "blocked_reasons_dropped_from_the_summary" in fails


def test_worker_invariants_reject_a_forged_count() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    fails = worker_invariant_failures(dict(result, jobs_completed_dry_run=99))
    assert "jobs_completed_dry_run_disagrees_with_the_results" in fails


def test_worker_invariants_reject_a_tampered_run_id() -> None:
    result = run_dry_run_worker(queue=_mixed_queue())
    fails = worker_invariant_failures(dict(result, worker_run_id="0" * 64))
    assert "worker_run_id_not_derivable_from_its_results" in fails


# --------------------------------------------------------------------------
# 100C - the worker cannot fetch or collect
# --------------------------------------------------------------------------


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE100_SERVICES)
def test_no_gate100_service_imports_an_http_client(name: str) -> None:
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


@pytest.mark.parametrize("name", GATE100_SERVICES)
def test_no_gate100_service_imports_a_collector_or_fetcher(name: str) -> None:
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


@pytest.mark.parametrize("name", GATE100_SERVICES)
def test_no_gate100_service_writes_to_the_database(name: str) -> None:
    banned = {"sqlalchemy", "psycopg", "psycopg2", "asyncpg"}
    tree = ast.parse(_service_source(name))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not roots & banned, f"{name} imports {roots & banned}"


@pytest.mark.parametrize("name", GATE100_SERVICES)
def test_every_gate100_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


# --------------------------------------------------------------------------
# 100D - readiness integration
# --------------------------------------------------------------------------


def test_the_dry_run_worker_is_detected_and_is_not_a_background_worker() -> None:
    detected = detect_dry_run_worker()
    assert detected["available"] is True
    assert detected["is_a_background_worker"] is False
    assert detected["executes_jobs"] is False
    assert detected["fetches"] is False


def test_readiness_reports_the_dry_run_worker_separately() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["dry_run_worker_available"] is True
    assert readiness["dry_run_runtime_available"] is True
    assert readiness["background_worker_available"] is False
    assert not scheduler_readiness_invariant_failures(readiness)


def test_readiness_still_says_not_ready_to_start_monitoring() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["ready_to_start_monitoring"] is False
    assert readiness["source_monitoring_live"] is False
    assert "background_worker" in readiness["components_missing"]


def test_dry_run_components_are_not_remaining_work() -> None:
    """Having them does not move the system closer to monitoring."""
    readiness = build_scheduler_readiness()
    assert not set(readiness["remaining_work"]) & DRY_RUN_COMPONENT_KEYS
    assert set(readiness["remaining_work"]) <= RUNTIME_COMPONENT_KEYS


def test_readiness_invariants_reject_a_dry_run_worker_read_as_a_real_one() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, background_worker_available=True)
    )
    assert "dry_run_worker_read_as_a_background_worker" in fails


def test_readiness_invariants_reject_a_dry_run_worker_claiming_execution() -> None:
    readiness = build_scheduler_readiness()
    components = dict(readiness["components"])
    components["dry_run_worker"] = dict(
        components["dry_run_worker"], executes_jobs=True
    )
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, components=components)
    )
    assert "dry_run_worker_claimed_execution_or_fetching" in fails


def test_may_fetch_live_now_remains_false() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["sources_may_fetch_live_now"] == 0
    for source in matrix["sources"]:
        assert source["may_fetch_live_now"] is False


def test_may_schedule_monitor_remains_false() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["sources_may_schedule_monitor"] == 0
    assert matrix["monitors_active"] == 0
    assert matrix["dry_run_worker_available"] is True
    for source in matrix["sources"]:
        assert source["may_schedule_monitor"] is False
    assert not pol.policy_invariant_failures(matrix)


def test_collectors_remain_not_active() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["collectors_active"] == 0
    for source in matrix["sources"]:
        assert source["collector_status"] == "not_active"


def test_policy_invariants_reject_a_dry_run_worker_permitting_live_work() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    forged_sources = [
        dict(matrix["sources"][0], may_schedule_monitor=True)
    ] + matrix["sources"][1:]
    fails = pol.policy_invariant_failures(dict(matrix, sources=forged_sources))
    assert any("dry_run_worker_permitted_live_work" in f for f in fails)


def test_the_preflight_reports_the_dry_run_worker_and_still_refuses() -> None:
    import nativeforge.services.source_activation_preflight_service as pre

    result = pre.build_activation_preflight(
        source_id="grants_gov_daily_extract",
        collector_type="bulk_extract",
        terms_status="NO_REVIEW_REQUIRED",
        legal_review_status="not_required",
        credential_status="not_required",
        attribution_status="present_and_verbatim",
        user_agent_status="policy_declared",
        rate_limit_status="policy_declared",
        storage_status="contract_satisfied",
        scheduler_status="policy_declared",
        monitoring_status="not_started",
        collection_intent="dry_run",
    )
    assert result["dry_run_worker_available"] is True
    assert result["activation_allowed"] is True
    assert result["safe_to_schedule"] is False
    assert result["safe_to_fetch_now"] is False
    assert "scheduler_runtime_unavailable" in result["scheduling_blocked_reasons"]
    assert not pre.preflight_invariant_failures(result)


def test_preflight_invariants_reject_scheduling_on_a_dry_run_worker() -> None:
    import nativeforge.services.source_activation_preflight_service as pre

    result = pre.build_activation_preflight(
        source_id="grants_gov_daily_extract",
        collector_type="bulk_extract",
        terms_status="NO_REVIEW_REQUIRED",
        legal_review_status="not_required",
        credential_status="not_required",
        attribution_status="present_and_verbatim",
        user_agent_status="policy_declared",
        rate_limit_status="policy_declared",
        storage_status="contract_satisfied",
        scheduler_status="policy_declared",
        monitoring_status="not_started",
        collection_intent="dry_run",
    )
    fails = pre.preflight_invariant_failures(dict(result, safe_to_schedule=True))
    assert "safe_to_schedule_on_a_dry_run_worker" in fails


# --------------------------------------------------------------------------
# 100E - CLI
# --------------------------------------------------------------------------


def _load_cli(name: str):
    spec = importlib.util.spec_from_file_location(name, CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_cli_exists_and_is_executable() -> None:
    assert CLI_PATH.exists()
    assert CLI_PATH.stat().st_mode & stat.S_IXUSR, "CLI lost its executable bit"


def test_the_cli_exits_zero_for_a_dry_run() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    assert "live_jobs_refused   0" in proc.stdout
    assert "dry_run_in_process" in proc.stdout


def test_the_cli_json_mode_reports_no_side_effects() -> None:
    proc = subprocess.run(
        [sys.executable, str(CLI_PATH), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["collectors_executed"] is False
    assert payload["urls_fetched"] is False
    assert payload["raw_payloads_written"] is False
    assert payload["source_monitoring_live"] is False


def test_the_cli_exits_nonzero_for_a_live_job() -> None:
    cli = _load_cli("gate100_cli_live")
    real = cli.build_worker_bundle

    def with_live(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        job = dict(bundle["queue"]["jobs"][0], execution_mode="live_collection")
        bundle["queue"] = dict(
            bundle["queue"], jobs=[job] + bundle["queue"]["jobs"][1:]
        )
        return bundle

    cli.build_worker_bundle = with_live
    try:
        assert cli.main([]) == cli.EXIT_LIVE_WORK
    finally:
        cli.build_worker_bundle = real


@pytest.mark.parametrize(
    "key", ["collector_invoked", "url_fetched", "raw_payload_written"]
)
def test_the_cli_exits_nonzero_when_a_result_claims_a_side_effect(key: str) -> None:
    cli = _load_cli(f"gate100_cli_{key}")
    real = cli.build_worker_bundle

    def with_side_effect(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        row = dict(bundle["result"]["results"][0], **{key: True})
        bundle["result"] = dict(
            bundle["result"], results=[row] + bundle["result"]["results"][1:]
        )
        return bundle

    cli.build_worker_bundle = with_side_effect
    try:
        assert cli.main([]) == cli.EXIT_SIDE_EFFECT
    finally:
        cli.build_worker_bundle = real


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
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("the dry-run worker attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    cli = _load_cli("gate100_cli_net")
    assert cli.main([]) == 0


# --------------------------------------------------------------------------
# 100F - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_worker_artifacts(repo_root=first)
    write_worker_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    write_worker_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_four_artifacts_are_written(tmp_path: Path) -> None:
    result = write_worker_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 4
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_eight_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_runtime_mode(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    assert "dry_run_in_process" in path.read_text(encoding="utf-8"), name


def test_the_csv_stamps_declarations_on_every_row() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_dry_run_worker_result.csv"
    if not path.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(PHASE1_SOURCE_IDS) + 1
    for line in lines[1:]:
        # dry_run_worker_available True, then seven falses.
        assert line.endswith("True,False,False,False,False,False,False,False"), line


def test_the_result_json_declares_no_live_work() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_dry_run_worker_result.json"
    if not path.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["dry_run_worker_available"] is True
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False, key


def test_the_worker_readiness_json_keeps_the_boundary() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "source_scheduler_worker_readiness.json"
    if not path.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["runtime_mode"] == "dry_run_in_process"
    assert payload["readiness"]["background_worker_available"] is False
    assert payload["readiness"]["ready_to_start_monitoring"] is False
    assert payload["decision"]["production_worker_live"] is False
    assert payload["decision"]["external_worker_required"] is True


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_worker_bundle(repo_root=REPO_ROOT)
    assert artifact_claim_failures(bundle, render_worker_summary(bundle)) == []


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.source_scheduler_dry_run_worker_artifact_service as mod

    real = mod.build_worker_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["background_worker_available"] = True
        return bundle

    monkeypatch.setattr(mod, "build_worker_bundle", lying)
    with pytest.raises(DryRunWorkerArtifactError):
        mod.write_worker_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_side_effect(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.source_scheduler_dry_run_worker_artifact_service as mod

    real = mod.build_worker_bundle

    def with_collector(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        row = dict(bundle["result"]["results"][0], collector_invoked=True)
        bundle["result"] = dict(
            bundle["result"], results=[row] + bundle["result"]["results"][1:]
        )
        return bundle

    monkeypatch.setattr(mod, "build_worker_bundle", with_collector)
    with pytest.raises(DryRunWorkerArtifactError):
        mod.write_worker_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_artifacts_cover_the_real_phase1_sources() -> None:
    decisions = build_phase1_schedule_decisions()
    assert [d["source_id"] for d in decisions] == list(PHASE1_SOURCE_IDS)


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("dry-run worker artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key="):
            assert marker not in text, f"{path.name} contains {marker!r}"


def test_the_artifact_dir_is_not_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", f"{ARTIFACT_DIR}/{ARTIFACT_NAMES[0]}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert proc.returncode != 0, "dry-run worker artifacts are gitignored"


# --------------------------------------------------------------------------
# 100 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_starts_no_worker_and_does_no_live_work() -> None:
    decision = build_worker_runtime_decision()
    readiness = build_scheduler_readiness()
    result = run_dry_run_worker(queue=_mixed_queue())

    assert decision["worker_started"] is False
    assert decision["production_worker_live"] is False
    assert readiness["scheduled_jobs_started"] == 0
    assert readiness["checks_executed"] == 0
    assert readiness["live_fetch_performed"] is False
    assert readiness["collectors_active"] is False
    assert readiness["live_source_coverage"] is False
    assert result["collectors_executed"] is False
    assert result["urls_fetched"] is False


def test_no_environment_variable_can_start_a_worker(monkeypatch) -> None:
    for name in (
        "NF_WORKER_ENABLED",
        "NF_BACKGROUND_WORKER",
        "NF_PRODUCTION_WORKER_LIVE",
        "NF_ALLOW_LIVE_COLLECTION",
    ):
        monkeypatch.setenv(name, "true")
    decision = build_worker_runtime_decision()
    assert decision["background_worker_available"] is False
    assert decision["production_worker_live"] is False
    assert decision["worker_started"] is False
