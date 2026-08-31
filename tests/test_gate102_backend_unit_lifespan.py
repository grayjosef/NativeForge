"""Gate 102 - backend unit install proof and lifespan hook boundary.

Hermetic. Nothing here installs a unit, starts a process, attaches a scheduler,
fetches a URL, or claims production readiness.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app, lifespan
from nativeforge.services.backend_lifespan_hook_service import (
    ATTACH_PREREQUISITES,
    FUTURE_SCHEDULER_DEPENDENCIES,
    LIFESPAN_PHASES,
    SCHEDULER_ATTACH_POINT,
    build_lifespan_hook_contract,
    detect_lifespan_hook_wired,
    lifespan_invariant_failures,
    lifespan_transitions,
    record_shutdown,
    record_startup,
    reset_lifespan_log,
    transition_invariant_failures,
)
from nativeforge.services.backend_process_proof_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    ENABLED_BY_THIS_GATE,
    FALSE_DECLARATION_KEYS,
    INSTALL_COMMANDS,
    REFERENCE_OBSERVED_AT,
    REFERENCE_PID,
    ProcessProofArtifactError,
    artifact_claim_failures,
    build_process_proof_bundle,
    render_summary,
    write_process_proof_artifacts,
)
from nativeforge.services.backend_process_proof_service import (
    HEALTHCHECK_SATISFYING,
    PROOF_FIELDS,
    PROOF_REQUIREMENT_KEYS,
    as_runtime_contract_proof,
    build_process_proof,
    proof_invariant_failures,
)
from nativeforge.services.backend_runtime_contract_service import (
    LOOPBACK_HOSTS,
    SYSTEMD_UNIT_RELATIVE_PATH,
    backend_runtime_invariant_failures,
    build_backend_runtime_contract,
)
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
    scheduler_readiness_invariant_failures,
)
from nativeforge.services.source_worker_runtime_decision_service import (
    build_worker_runtime_decision,
    worker_runtime_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_PATH = REPO_ROOT / SYSTEMD_UNIT_RELATIVE_PATH
MAIN_PATH = REPO_ROOT / "src" / "nativeforge" / "main.py"

COMPLETE_PROOF = dict(
    observed_at="2026-01-01T12:00:00+00:00",
    unit_installed=True,
    unit_active=True,
    pid=4242,
    host="127.0.0.1",
    port=8000,
    healthcheck_status="ok",
    readiness_status="ok",
)


def _proof(**overrides):
    return build_process_proof(**{**COMPLETE_PROOF, **overrides})


# --------------------------------------------------------------------------
# 102B - process proof
# --------------------------------------------------------------------------


def test_a_complete_proof_supports_a_live_backend() -> None:
    """Not vacuous: if nothing could ever prove live, every refusal is empty."""
    proof = _proof()
    assert proof["persistent_backend_live"] is True
    assert proof["runtime_mode"] == "persistent_backend_live"
    assert proof["requirements_missing"] == []
    assert not proof_invariant_failures(proof)


def test_a_proof_requires_observed_at() -> None:
    proof = _proof(observed_at=None)
    assert proof["persistent_backend_live"] is False
    assert "no_observed_at" in proof["blocked_reasons"]


@pytest.mark.parametrize("value", [None, ""])
def test_an_empty_observed_at_is_no_observation(value: object) -> None:
    assert _proof(observed_at=value)["persistent_backend_live"] is False


def test_a_proof_requires_an_active_unit() -> None:
    proof = _proof(unit_active=False)
    assert proof["persistent_backend_live"] is False
    assert "unit_not_active" in proof["blocked_reasons"]


def test_a_proof_requires_an_installed_unit() -> None:
    """systemd cannot run a unit it does not have."""
    proof = _proof(unit_installed=False)
    assert proof["persistent_backend_live"] is False
    assert "unit_active_without_being_installed" in proof["blocked_reasons"]


@pytest.mark.parametrize("value", [None, 0, -1, "many", True])
def test_a_proof_requires_a_pid(value: object) -> None:
    proof = _proof(pid=value)
    assert proof["persistent_backend_live"] is False
    assert "no_pid_observed" in proof["blocked_reasons"]


@pytest.mark.parametrize("host", sorted(LOOPBACK_HOSTS))
def test_loopback_hosts_are_accepted(host: str) -> None:
    proof = _proof(host=host)
    assert proof["loopback_only"] is True
    assert proof["persistent_backend_live"] is True


@pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.5", "example.com"])
def test_a_proof_requires_a_loopback_host(host: str) -> None:
    proof = _proof(host=host)
    assert proof["loopback_only"] is False
    assert proof["persistent_backend_live"] is False
    assert any("host_is_not_loopback" in r for r in proof["blocked_reasons"])


@pytest.mark.parametrize("status", ["failed", "unreachable", "unknown", "nonsense"])
def test_a_proof_requires_a_passing_healthcheck(status: str) -> None:
    """A unit can be active while the app inside it fails every request."""
    proof = _proof(healthcheck_status=status)
    assert proof["persistent_backend_live"] is False
    assert any("healthcheck_not_ok" in r for r in proof["blocked_reasons"])


def test_healthcheck_satisfying_is_only_ok() -> None:
    assert HEALTHCHECK_SATISFYING == frozenset({"ok"})


def test_source_dirty_counts_tracked_changes_only(tmp_path: Path) -> None:
    """An untracked scratch file does not change the running code.

    This repository carries hundreds of untracked smoke artifacts, which made
    `source_dirty` permanently true on this host. The flag is paired with
    `git_sha` to answer "does the running code differ from that commit", and a
    flag that is always true can never answer it.
    """
    from nativeforge.services.backend_health_readiness_service import (
        detect_git_identity,
    )

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.invalid"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=tmp_path, check=True)

    assert detect_git_identity(repo_root=tmp_path)["source_dirty"] is False

    # An untracked file is not a dirty source.
    (tmp_path / "scratch.log").write_text("noise\n", encoding="utf-8")
    assert detect_git_identity(repo_root=tmp_path)["source_dirty"] is False

    # A tracked modification is.
    (tmp_path / "tracked.txt").write_text("two\n", encoding="utf-8")
    assert detect_git_identity(repo_root=tmp_path)["source_dirty"] is True


@pytest.mark.parametrize("dirty", [True, False, None])
def test_source_dirty_blocks_production_but_not_the_observation(
    dirty: object,
) -> None:
    """A developer with an unsaved file can still observe their own server."""
    proof = _proof(source_dirty=dirty)
    assert proof["persistent_backend_live"] is True
    assert proof["production_ready"] is False
    assert not proof_invariant_failures(proof)


def test_a_proof_does_not_imply_collectors_live() -> None:
    proof = _proof()
    assert proof["persistent_backend_live"] is True
    assert proof["collectors_live"] == 0
    assert proof["live_fetch_performed"] is False
    assert proof["live_source_coverage"] is False


def test_a_proof_does_not_imply_source_monitoring_live() -> None:
    proof = _proof()
    assert proof["source_monitoring_live"] is False
    assert proof["scheduler_attached"] is False


def test_every_proof_field_is_present() -> None:
    proof = _proof()
    for field in PROOF_FIELDS:
        assert field in proof, field


def test_every_proof_requirement_is_accounted_for_once() -> None:
    proof = _proof(healthcheck_status="failed")
    satisfied = set(proof["requirements_satisfied"])
    missing = set(proof["requirements_missing"])
    assert not satisfied & missing
    assert satisfied | missing == set(PROOF_REQUIREMENT_KEYS)


def test_the_proof_id_is_deterministic() -> None:
    assert _proof()["proof_id"] == _proof()["proof_id"]
    assert _proof()["proof_id"] != _proof(pid=9999)["proof_id"]


def test_a_weak_proof_cannot_satisfy_the_runtime_contract() -> None:
    weak = _proof(healthcheck_status="failed")
    assert as_runtime_contract_proof(weak) is None
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=as_runtime_contract_proof(weak)
    )
    assert contract["persistent_backend_live"] is False


def test_a_complete_proof_does_satisfy_the_runtime_contract() -> None:
    bridged = as_runtime_contract_proof(_proof())
    assert bridged is not None
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=bridged
    )
    assert contract["persistent_backend_live"] is True
    assert contract["collectors_live"] == 0
    assert contract["source_monitoring_live"] is False
    assert not backend_runtime_invariant_failures(contract)


def test_proof_invariants_reject_a_forged_live_claim() -> None:
    weak = _proof(healthcheck_status="failed")
    fails = proof_invariant_failures(dict(weak, persistent_backend_live=True))
    assert "live_without_a_passing_healthcheck" in fails


def test_proof_invariants_reject_a_tampered_id() -> None:
    fails = proof_invariant_failures(dict(_proof(), proof_id="0" * 64))
    assert "proof_id_not_derivable_from_the_observation" in fails


def test_proof_invariants_reject_a_url_pointing_elsewhere() -> None:
    fails = proof_invariant_failures(
        dict(_proof(), healthcheck_url="http://elsewhere.example/backend/health")
    )
    assert "healthcheck_url_does_not_target_the_loopback_host" in fails


@pytest.mark.parametrize(
    "key", ["source_monitoring_live", "scheduler_attached", "live_fetch_performed"]
)
def test_proof_invariants_reject_a_licence_claim(key: str) -> None:
    fails = proof_invariant_failures(dict(_proof(), **{key: True}))
    assert f"proof_claimed:{key}" in fails


# --------------------------------------------------------------------------
# 102C - lifespan hook
# --------------------------------------------------------------------------


def test_the_lifespan_hook_exists_and_is_wired() -> None:
    detected = detect_lifespan_hook_wired()
    assert detected["available"] is True
    assert detected["lifespan_defined"] is True
    assert detected["lifespan_passed_to_fastapi"] is True
    assert callable(lifespan)


def test_main_passes_the_lifespan_to_fastapi() -> None:
    """Parsed, not trusted: a defined-but-unwired hook is dead code."""
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"))
    passed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == "FastAPI":
                passed = any(kw.arg == "lifespan" for kw in node.keywords)
    assert passed, "FastAPI() is not given a lifespan"


def test_the_hook_fires_on_startup_and_shutdown() -> None:
    reset_lifespan_log()
    with TestClient(create_app()) as client:
        assert client.get("/backend/health").status_code == 200
        assert [t["phase"] for t in lifespan_transitions()] == ["startup"]
    phases = [t["phase"] for t in lifespan_transitions()]
    assert phases == ["startup", "shutdown"]
    assert not transition_invariant_failures(lifespan_transitions())


def test_the_hook_starts_no_scheduler() -> None:
    reset_lifespan_log()
    with TestClient(create_app()):
        pass
    for entry in lifespan_transitions():
        assert entry["scheduler_attached"] is False
    assert build_lifespan_hook_contract()["scheduler_attached"] is False


def test_the_hook_starts_no_collectors() -> None:
    reset_lifespan_log()
    with TestClient(create_app()):
        pass
    for entry in lifespan_transitions():
        assert entry["collectors_started"] is False
    assert build_lifespan_hook_contract()["collectors_started"] is False


def test_the_hook_fetches_no_urls() -> None:
    reset_lifespan_log()
    for entry in [record_startup(), record_shutdown()]:
        assert entry["urls_fetched"] is False
    assert build_lifespan_hook_contract()["urls_fetched"] is False


def test_the_hook_makes_no_network_call(monkeypatch) -> None:
    """Startup and shutdown, with sockets poisoned to raise."""
    import socket

    def _forbidden(*args, **kwargs):
        raise AssertionError("the lifespan hook attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    reset_lifespan_log()
    with TestClient(create_app()):
        pass
    assert [t["phase"] for t in lifespan_transitions()] == ["startup", "shutdown"]


def test_the_hook_leaves_monitoring_false() -> None:
    reset_lifespan_log()
    with TestClient(create_app()):
        pass
    for entry in lifespan_transitions():
        assert entry["source_monitoring_live"] is False


def test_the_lifespan_contract_lists_its_prerequisites() -> None:
    contract = build_lifespan_hook_contract()
    listed = {item["requirement"] for item in contract["attach_prerequisites"]}
    assert listed == {name for name, _ in ATTACH_PREREQUISITES}
    assert contract["blocked_reasons"]
    assert not lifespan_invariant_failures(contract)


def test_the_attach_point_is_named() -> None:
    contract = build_lifespan_hook_contract()
    assert contract["attach_point"] == SCHEDULER_ATTACH_POINT
    assert SCHEDULER_ATTACH_POINT == "nativeforge.main:lifespan"
    assert set(contract["future_scheduler_dependencies"]) == set(
        FUTURE_SCHEDULER_DEPENDENCIES
    )


def test_the_hook_does_not_import_the_scheduler_layer() -> None:
    """Boot must not depend on the scheduler layer for no benefit."""
    source = (
        REPO_ROOT
        / "src"
        / "nativeforge"
        / "services"
        / "backend_lifespan_hook_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for dependency in FUTURE_SCHEDULER_DEPENDENCIES:
        assert dependency not in imported, dependency


def test_transition_invariants_reject_a_forged_attachment() -> None:
    reset_lifespan_log()
    record_startup()
    forged = [dict(lifespan_transitions()[0], scheduler_attached=True)]
    assert "transition_claimed:scheduler_attached" in transition_invariant_failures(
        forged
    )


def test_transition_invariants_reject_shutdown_before_startup() -> None:
    reset_lifespan_log()
    record_shutdown()
    record_startup()
    fails = transition_invariant_failures(lifespan_transitions())
    assert "shutdown_without_a_startup" not in fails
    assert "shutdown_recorded_before_startup" in fails
    reset_lifespan_log()


def test_lifespan_phases_vocabulary_is_closed() -> None:
    assert LIFESPAN_PHASES == frozenset({"startup", "shutdown"})


def test_a_defined_but_unwired_lifespan_is_not_available(tmp_path: Path) -> None:
    """Both halves are true in the real tree, so the conjunction is invisible.

    A mutation reducing `passes_lifespan and defines_lifespan` to just
    `defines_lifespan` survived every other test here. This builds the one file
    that distinguishes them: a `main.py` that defines a lifespan and never
    hands it to FastAPI - dead code that would otherwise report a capability
    the application does not have.
    """
    src = tmp_path / "src" / "nativeforge"
    src.mkdir(parents=True)
    (src / "main.py").write_text(
        "from contextlib import asynccontextmanager\n"
        "from fastapi import FastAPI\n"
        "@asynccontextmanager\n"
        "async def lifespan(app):\n"
        "    yield\n"
        "app = FastAPI(title='x')\n",
        encoding="utf-8",
    )
    detected = detect_lifespan_hook_wired(repo_root=tmp_path)
    assert detected["lifespan_defined"] is True
    assert detected["lifespan_passed_to_fastapi"] is False
    assert detected["available"] is False


def test_a_wired_lifespan_is_available(tmp_path: Path) -> None:
    """The other side of the same check, so neither is vacuous."""
    src = tmp_path / "src" / "nativeforge"
    src.mkdir(parents=True)
    (src / "main.py").write_text(
        "from contextlib import asynccontextmanager\n"
        "from fastapi import FastAPI\n"
        "@asynccontextmanager\n"
        "async def lifespan(app):\n"
        "    yield\n"
        "app = FastAPI(title='x', lifespan=lifespan)\n",
        encoding="utf-8",
    )
    detected = detect_lifespan_hook_wired(repo_root=tmp_path)
    assert detected["available"] is True


def test_lifespan_invariants_reject_a_half_wired_hook() -> None:
    contract = build_lifespan_hook_contract()
    fails = lifespan_invariant_failures(
        dict(contract, lifespan_passed_to_fastapi=False)
    )
    assert "lifespan_availability_disagrees_with_its_halves" in fails


# --------------------------------------------------------------------------
# 102D - integration
# --------------------------------------------------------------------------


def test_scheduler_readiness_reports_the_hook_without_a_backend() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["lifespan_hook_available"] is True
    assert readiness["persistent_backend_live"] is False
    assert readiness["backend_process_proof_supplied"] is False
    assert readiness["in_process_scheduler_possible"] is False
    assert not scheduler_readiness_invariant_failures(readiness)


def test_an_in_process_scheduler_needs_both_halves() -> None:
    """A hook with nothing running is the easier half to mistake for progress."""
    with_proof = build_scheduler_readiness(
        process_proof=as_runtime_contract_proof(_proof())
    )
    assert with_proof["persistent_backend_live"] is True
    assert with_proof["lifespan_hook_available"] is True
    assert with_proof["in_process_scheduler_possible"] is True
    # And still not monitoring: no worker, no trigger, no payload store.
    assert with_proof["source_monitoring_live"] is False
    assert with_proof["ready_to_start_monitoring"] is False
    assert not scheduler_readiness_invariant_failures(with_proof)


def test_a_live_backend_without_a_hook_still_blocks_an_in_process_scheduler(
    monkeypatch,
) -> None:
    """The lifespan conjunct, forced into view.

    The hook is available in the real tree, so `lifespan_ok and backend_ok`
    reduces to `backend_ok` and a mutation dropping the first survived every
    other test here. This builds the world that distinguishes them: a proven
    live backend with no attach point in it. A scheduler has a process to run
    in and nowhere in that process to hook onto, so the answer must be false.
    """
    import nativeforge.services.source_scheduler_readiness_service as mod

    real = mod.detect_persistent_backend

    def live_but_hookless(*, repo_root=None, process_proof=None):
        record = dict(real(repo_root=repo_root, process_proof=process_proof))
        record["available"] = True
        record["backend_runtime_mode"] = "persistent_backend_live"
        record["process_proof_supplied"] = True
        record["lifespan_hook_available"] = False
        record["in_process_attach_possible"] = False
        return record

    monkeypatch.setattr(mod, "detect_persistent_backend", live_but_hookless)
    readiness = mod.build_scheduler_readiness()

    assert readiness["persistent_backend_live"] is True
    assert readiness["lifespan_hook_available"] is False
    # A process to run in, and nowhere in it to attach.
    assert readiness["in_process_scheduler_possible"] is False
    assert not scheduler_readiness_invariant_failures(readiness)


def test_readiness_invariants_reject_an_in_process_claim_without_a_backend() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, in_process_scheduler_possible=True)
    )
    assert "in_process_scheduler_disagrees_with_its_halves" in fails


def test_readiness_invariants_reject_a_live_backend_without_a_proof() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, persistent_backend_live=True)
    )
    assert "persistent_backend_without_a_process_proof" in fails


def test_the_worker_decision_requires_both_halves() -> None:
    decision = build_worker_runtime_decision()
    assert decision["lifespan_hook_available"] is True
    assert decision["persistent_backend_live"] is False
    assert decision["in_process_worker_possible"] is False
    assert "persistent_backend_not_live" in decision["blocked_reasons"]
    assert not worker_runtime_invariant_failures(decision)


def test_worker_invariants_reject_an_in_process_claim_without_a_hook() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, in_process_worker_possible=True, lifespan_hook_available=False)
    )
    assert "in_process_worker_without_a_lifespan_hook" in fails


def test_background_and_production_worker_remain_false() -> None:
    decision = build_worker_runtime_decision()
    assert decision["background_worker_available"] is False
    assert decision["production_worker_live"] is False


def test_may_fetch_live_now_remains_false() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["lifespan_hook_available"] is True
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


def test_policy_invariants_reject_a_hook_read_as_a_scheduler() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    fails = pol.policy_invariant_failures(dict(matrix, sources_may_schedule_monitor=2))
    assert "lifespan_hook_read_as_a_scheduler" in fails


def test_the_preflight_reports_the_hook_and_still_refuses() -> None:
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
    assert result["lifespan_hook_available"] is True
    assert result["safe_to_schedule"] is False
    assert result["safe_to_fetch_now"] is False
    assert not pre.preflight_invariant_failures(result)


# --------------------------------------------------------------------------
# 102D/E - the unit itself
# --------------------------------------------------------------------------


def test_the_install_plan_binds_loopback_only() -> None:
    bundle = build_process_proof_bundle(repo_root=REPO_ROOT)
    plan = bundle["install_plan"]
    assert plan["binds_loopback_only"] is True
    assert plan["host"] in LOOPBACK_HOSTS
    for line in plan["exec_start_lines"]:
        assert "--host 127.0.0.1" in line
        assert "0.0.0.0" not in line


def test_the_install_plan_contains_no_secrets() -> None:
    text = (REPO_ROOT / ARTIFACT_DIR / "backend_unit_install_plan.md").read_text(
        encoding="utf-8"
    )
    lowered = text.lower()
    for marker in ("password=", "api_key=", "postgresql://", "-----begin", "token="):
        assert marker not in lowered, marker


def test_the_install_plan_omits_the_enable_command() -> None:
    """The operator approved start, not enable."""
    assert ENABLED_BY_THIS_GATE is False
    for command in INSTALL_COMMANDS:
        assert "enable" not in command, command


def test_the_unit_is_enabled_only_under_a_recorded_approval() -> None:
    """Gate 102 approved start-only. Gate 130 approved enable, in writing.

    The original assertion was `not link.exists()`, and it was right for two
    years of gates: the operator had approved starting the backend, not
    installing it, and a unit surviving a reboot is a different decision from a
    unit running now.

    Gate 130's brief changed that decision explicitly - "backend service:
    active, enabled if safe" - after the backend twice failed to come back when
    the WSL systemd user manager cycled, which is the same event that took the
    tunnel down mid-demo and produced Cloudflare Error 1033.

    So enablement is permitted, and the thing worth asserting is that it stays
    loopback-only and secretless. Enablement without those would be the actual
    risk; enablement with them is a reliability fix the operator asked for.
    """
    text = UNIT_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("ExecStart"):
            assert "--host 127.0.0.1" in line
            assert "0.0.0.0" not in line
    lowered = text.lower()
    for marker in ("password=", "token=", "secret=", "postgresql://"):
        assert marker not in lowered, marker


def test_the_unit_template_still_binds_loopback_only() -> None:
    text = UNIT_PATH.read_text(encoding="utf-8")
    exec_lines = [
        line for line in text.splitlines() if line.strip().startswith("ExecStart")
    ]
    assert exec_lines
    for line in exec_lines:
        assert "--host 127.0.0.1" in line
        assert "0.0.0.0" not in line


# --------------------------------------------------------------------------
# 102 - the services do not fetch
# --------------------------------------------------------------------------


GATE102_SERVICES = (
    "backend_process_proof_service",
    "backend_lifespan_hook_service",
    "backend_process_proof_artifact_service",
)


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE102_SERVICES)
def test_no_gate102_service_imports_an_http_client(name: str) -> None:
    """The proof service is told what was observed; it never goes looking."""
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


@pytest.mark.parametrize("name", GATE102_SERVICES)
def test_no_gate102_service_imports_a_collector(name: str) -> None:
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
            )
        )
    }
    assert not offending, f"{name} imports {offending}"


@pytest.mark.parametrize("name", GATE102_SERVICES)
def test_every_gate102_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


# --------------------------------------------------------------------------
# 102F - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_process_proof_artifacts(repo_root=first)
    write_process_proof_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("process proof artifacts not generated in this tree")
    write_process_proof_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_five_artifacts_are_written(tmp_path: Path) -> None:
    result = write_process_proof_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 5
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    # The install plan is prose about install state; it carries the two that
    # matter for it rather than all nine.
    keys = (
        ("installed_by_this_gate", "enabled_by_this_gate")
        if name == "backend_unit_install_plan.md"
        else DECLARATION_KEYS
    )
    for key in keys:
        assert key in text, f"{name} omits {key}"


def test_the_artifacts_claim_no_live_work() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_process_proof_readiness.json"
    if not path.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False, key
    assert payload["backend_unit_template_available"] is True
    assert payload["lifespan_hook_available"] is True


def test_no_live_process_proof_reached_a_committed_artifact() -> None:
    """A pid or an observation timestamp here would never match a fresh run."""
    path = REPO_ROOT / ARTIFACT_DIR / "backend_process_proof_readiness.json"
    if not path.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["process_proof_committed"] is False
    example = payload["proof_contract"]["example"]
    assert example["observed_at"] == REFERENCE_OBSERVED_AT
    assert example["pid"] == REFERENCE_PID
    assert payload["proof_contract"]["example_only"] is True


def test_the_lifespan_artifact_records_nothing_attached() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_lifespan_hook_contract.json"
    if not path.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["lifespan_hook_available"] is True
    assert payload["scheduler_attached"] is False
    assert payload["collectors_started"] is False
    assert payload["urls_fetched"] is False
    assert payload["source_monitoring_live"] is False


def test_the_csv_stamps_declarations_on_every_row() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_process_proof_readiness.csv"
    if not path.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 1
    for line in lines[1:]:
        assert line.endswith("True,True,True,False,False,False,False,False,False"), line


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_process_proof_bundle(repo_root=REPO_ROOT)
    assert artifact_claim_failures(bundle, render_summary(bundle)) == []


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.backend_process_proof_artifact_service as mod

    real = mod.build_process_proof_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["persistent_backend_live"] = True
        return bundle

    monkeypatch.setattr(mod, "build_process_proof_bundle", lying)
    with pytest.raises(ProcessProofArtifactError):
        mod.write_process_proof_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_an_enabled_claim(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.backend_process_proof_artifact_service as mod

    real = mod.build_process_proof_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["enabled_by_this_gate"] = True
        return bundle

    monkeypatch.setattr(mod, "build_process_proof_bundle", lying)
    with pytest.raises(ProcessProofArtifactError):
        mod.write_process_proof_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_public_binding_plan(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.backend_process_proof_artifact_service as mod

    real = mod.build_process_proof_bundle

    def public(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["install_plan"] = dict(bundle["install_plan"], binds_loopback_only=False)
        return bundle

    monkeypatch.setattr(mod, "build_process_proof_bundle", public)
    with pytest.raises(ProcessProofArtifactError):
        mod.write_process_proof_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("process proof artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key=", "postgresql://", "password="):
            assert marker not in text, f"{path.name} contains {marker!r}"


def test_the_artifact_dir_is_not_gitignored() -> None:
    proc = subprocess.run(
        ["git", "check-ignore", "-q", f"{ARTIFACT_DIR}/{ARTIFACT_NAMES[0]}"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert proc.returncode != 0, "process proof artifacts are gitignored"


# --------------------------------------------------------------------------
# 102 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_attaches_nothing_and_does_no_live_work() -> None:
    lifespan_contract = build_lifespan_hook_contract()
    readiness = build_scheduler_readiness()
    assert lifespan_contract["scheduler_attached"] is False
    assert lifespan_contract["collectors_started"] is False
    assert lifespan_contract["urls_fetched"] is False
    assert readiness["scheduled_jobs_started"] == 0
    assert readiness["checks_executed"] == 0
    assert readiness["collectors_active"] is False
    assert readiness["live_source_coverage"] is False


def test_no_environment_variable_can_attach_a_scheduler(monkeypatch) -> None:
    for name in (
        "NF_SCHEDULER_ATTACH",
        "NF_START_SCHEDULER",
        "NF_COLLECTORS_ENABLED",
        "NF_SOURCE_MONITORING_LIVE",
    ):
        monkeypatch.setenv(name, "true")
    reset_lifespan_log()
    with TestClient(create_app()):
        pass
    for entry in lifespan_transitions():
        assert entry["scheduler_attached"] is False
        assert entry["collectors_started"] is False
    assert build_lifespan_hook_contract()["scheduler_attached"] is False
