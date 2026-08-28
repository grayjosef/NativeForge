"""Gate 101 - persistent backend process and health boundary.

Hermetic. Nothing here starts a backend, installs a unit, enables a service,
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

from nativeforge.main import create_app
from nativeforge.services.backend_health_readiness_service import (
    CREDENTIAL_KEY_FRAGMENTS,
    HEALTH_FIELDS,
    READINESS_FIELDS,
    SERVICE_NAME,
    UNKNOWN_SHA,
    build_backend_health,
    build_backend_readiness,
    detect_git_identity,
    health_invariant_failures,
    readiness_invariant_failures,
)
from nativeforge.services.backend_runtime_contract_service import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HEALTHCHECK_PATH,
    LOOPBACK_HOSTS,
    NEXT_ACTION_SEQUENCE,
    PERSISTENT_LIVE_MODES,
    READINESS_PATH,
    RUNTIME_AVAILABLE_MODES,
    RUNTIME_MODES,
    SYSTEMD_UNIT_RELATIVE_PATH,
    backend_runtime_invariant_failures,
    build_backend_runtime_contract,
    detect_lifespan_hook,
    detect_smoke_script_startup,
    detect_systemd_unit_template,
)
from nativeforge.services.backend_runtime_readiness_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    FALSE_DECLARATION_KEYS,
    REFERENCE_GIT_SHA,
    BackendRuntimeArtifactError,
    artifact_claim_failures,
    build_backend_readiness_bundle,
    render_readiness_summary,
    write_backend_runtime_artifacts,
)
from nativeforge.services.source_scheduler_readiness_service import (
    RUNTIME_COMPONENT_KEYS,
    build_scheduler_readiness,
    detect_persistent_backend,
    scheduler_readiness_invariant_failures,
)
from nativeforge.services.source_worker_runtime_decision_service import (
    build_worker_runtime_decision,
    worker_runtime_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_PATH = REPO_ROOT / SYSTEMD_UNIT_RELATIVE_PATH

PROCESS_PROOF = {
    "observed": True,
    "pid": 4242,
    "observed_at": "2026-01-01T12:00:00+00:00",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


# --------------------------------------------------------------------------
# 101B - runtime contract
# --------------------------------------------------------------------------


def test_the_contract_defaults_safe() -> None:
    contract = build_backend_runtime_contract()
    assert contract["persistent_backend_live"] is False
    assert contract["backend_started"] is False
    assert contract["customer_auth_live"] is False
    assert contract["collectors_live"] == 0
    assert not backend_runtime_invariant_failures(contract)


def test_smoke_script_only_does_not_count_as_a_persistent_backend() -> None:
    """Four scripts start the API. Every one kills it on exit."""
    smoke = detect_smoke_script_startup()
    assert smoke["available"] is True
    assert smoke["counts_as_persistent_backend"] is False
    assert len(smoke["scripts"]) >= 3

    forged = dict(
        build_backend_runtime_contract(),
        runtime_mode="smoke_script_only",
        backend_runtime_available=True,
    )
    fails = backend_runtime_invariant_failures(forged)
    assert "smoke_script_read_as_a_backend_runtime" in fails


def test_smoke_script_only_is_not_in_the_available_modes() -> None:
    assert "smoke_script_only" not in RUNTIME_AVAILABLE_MODES
    assert "smoke_script_only" not in PERSISTENT_LIVE_MODES


def test_a_loopback_contract_does_not_imply_a_live_process() -> None:
    contract = build_backend_runtime_contract()
    assert contract["runtime_mode"] == "loopback_backend_contract"
    assert contract["backend_runtime_contract_available"] is True
    assert contract["persistent_backend_live"] is False
    assert contract["trust_endpoint_available"] is False


def test_persistent_backend_live_remains_false_without_process_proof() -> None:
    contract = build_backend_runtime_contract(systemd_unit_installed=True)
    assert contract["runtime_mode"] == "loopback_backend_configured"
    assert contract["persistent_backend_live"] is False
    assert "no_long_running_process_proof" in contract["blocked_reasons"]


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {},
        {"observed": True},
        {"observed": True, "pid": 1},
        {"observed": False, "pid": 1, "observed_at": "2026-01-01T00:00:00+00:00"},
        "yes",
    ],
)
def test_an_incomplete_proof_is_not_a_proof(proof: object) -> None:
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=proof
    )
    assert contract["persistent_backend_live"] is False
    assert contract["process_proof_supplied"] is False


def test_a_complete_proof_with_an_installed_unit_reaches_live() -> None:
    """Not a hardcoded false: give it both halves and the mode changes."""
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=PROCESS_PROOF
    )
    assert contract["runtime_mode"] == "persistent_backend_live"
    assert contract["persistent_backend_live"] is True
    assert contract["trust_endpoint_available"] is True
    assert not backend_runtime_invariant_failures(contract)


def test_a_proof_without_an_installed_unit_is_not_live() -> None:
    contract = build_backend_runtime_contract(process_proof=PROCESS_PROOF)
    assert contract["persistent_backend_live"] is False


def test_backend_runtime_does_not_imply_collectors_live() -> None:
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=PROCESS_PROOF
    )
    assert contract["backend_runtime_available"] is True
    assert contract["persistent_backend_live"] is True
    assert contract["collectors_live"] == 0
    assert contract["live_fetch_performed"] is False
    assert contract["live_source_coverage"] is False


def test_backend_runtime_does_not_imply_scheduler_live() -> None:
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=PROCESS_PROOF
    )
    assert contract["scheduler_live"] is False
    assert contract["source_monitoring_live"] is False


def test_backend_runtime_does_not_imply_customer_auth() -> None:
    contract = build_backend_runtime_contract(
        systemd_unit_installed=True, process_proof=PROCESS_PROOF
    )
    assert contract["customer_auth_live"] is False


@pytest.mark.parametrize("host", sorted(LOOPBACK_HOSTS))
def test_loopback_hosts_are_accepted(host: str) -> None:
    contract = build_backend_runtime_contract(host=host)
    assert contract["loopback_only"] is True
    assert "backend_host_is_not_loopback" not in backend_runtime_invariant_failures(
        contract
    )


@pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.5", "::", "example.com"])
def test_a_non_loopback_host_fails_an_invariant(host: str) -> None:
    """A public bind on this host would reach the running Cloudflare tunnel."""
    contract = build_backend_runtime_contract(host=host)
    assert contract["loopback_only"] is False
    assert "backend_host_is_not_loopback" in backend_runtime_invariant_failures(
        contract
    )


def test_the_default_host_and_port() -> None:
    contract = build_backend_runtime_contract()
    assert contract["host"] == DEFAULT_HOST == "127.0.0.1"
    assert contract["port"] == DEFAULT_PORT == 8000


def test_main_now_has_a_lifespan_hook() -> None:
    """Gate 101 asserted the absence of one. Gate 102C added it.

    The assertion is inverted rather than deleted, because the detector is what
    Gate 101 contributed and it must keep working - it now has to *find* a hook
    where it previously had to correctly report none.
    """
    detected = detect_lifespan_hook()
    assert detected["available"] is True
    assert "lifespan_argument" in detected["hooks_found"]
    assert build_backend_runtime_contract()["lifespan_hook_available"] is True


def test_the_lifespan_detector_finds_a_hook_when_one_exists(tmp_path: Path) -> None:
    """Not a hardcoded false: parse a file that does have one."""
    import nativeforge.services.backend_runtime_contract_service as mod

    src = tmp_path / "src" / "nativeforge"
    src.mkdir(parents=True)
    (src / "main.py").write_text(
        "from contextlib import asynccontextmanager\n"
        "@asynccontextmanager\n"
        "async def lifespan(app):\n"
        "    yield\n",
        encoding="utf-8",
    )
    real_root = mod.REPO_ROOT
    try:
        mod.REPO_ROOT = tmp_path
        assert mod.detect_lifespan_hook()["available"] is True
    finally:
        mod.REPO_ROOT = real_root


def test_the_contract_prerequisites_are_ordered() -> None:
    contract = build_backend_runtime_contract()
    actions = [a["action"] for a in contract["next_required_actions"]]
    assert actions == [a for a, _ in NEXT_ACTION_SEQUENCE]
    assert actions[0] == "install_backend_systemd_unit"
    assert actions.index("prove_a_long_running_process") < actions.index(
        "add_a_lifespan_hook"
    )


def test_contract_invariants_reject_a_forged_live_backend() -> None:
    contract = build_backend_runtime_contract()
    fails = backend_runtime_invariant_failures(
        dict(contract, persistent_backend_live=True)
    )
    assert "persistent_backend_live_without_process_proof" in fails


def test_contract_invariants_reject_enabled_without_installed() -> None:
    contract = build_backend_runtime_contract(systemd_unit_enabled=True)
    fails = backend_runtime_invariant_failures(contract)
    assert "unit_enabled_without_being_installed" in fails


def test_contract_invariants_reject_health_colliding_with_the_static_stamp() -> None:
    contract = build_backend_runtime_contract()
    fails = backend_runtime_invariant_failures(
        dict(contract, healthcheck_path="/health")
    )
    assert "backend_health_collides_with_the_static_stamp" in fails


def test_runtime_mode_vocabulary_is_closed() -> None:
    assert build_backend_runtime_contract()["runtime_mode"] in RUNTIME_MODES
    fails = backend_runtime_invariant_failures(
        dict(build_backend_runtime_contract(), runtime_mode="turbo")
    )
    assert "runtime_mode_out_of_vocabulary" in fails


# --------------------------------------------------------------------------
# 101C - health and readiness
# --------------------------------------------------------------------------


def test_the_health_contract_carries_git_sha_and_source_dirty() -> None:
    health = build_backend_health(now="2026-01-01T00:00:00+00:00")
    for field in HEALTH_FIELDS:
        assert field in health, field
    assert "git_sha" in health
    assert "source_dirty" in health
    assert not health_invariant_failures(health)


def test_a_sha_we_could_not_read_is_unknown_not_invented(tmp_path: Path) -> None:
    identity = detect_git_identity(repo_root=tmp_path)
    assert identity["git_sha"] == UNKNOWN_SHA
    assert identity["source_dirty"] is None
    health = build_backend_health(repo_root=tmp_path, now="2026-01-01T00:00:00+00:00")
    assert health["git_sha"] == UNKNOWN_SHA
    assert not health_invariant_failures(health)


def test_health_never_claims_production_readiness() -> None:
    health = build_backend_health(now="2026-01-01T00:00:00+00:00")
    assert health["production_ready"] is False
    fails = health_invariant_failures(dict(health, production_ready=True))
    assert "health_claimed_production_ready" in fails


def test_health_invariants_reject_an_invented_sha() -> None:
    health = build_backend_health(now="2026-01-01T00:00:00+00:00")
    fails = health_invariant_failures(dict(health, git_sha="probably-main"))
    assert "health_git_sha_is_not_a_commit" in fails


def test_the_readiness_contract_carries_the_production_blockers() -> None:
    readiness = build_backend_readiness(database_ready=False)
    for field in READINESS_FIELDS:
        assert field in readiness, field
    assert readiness["persistent_backend_live"] is False
    assert readiness["collectors_live"] == 0
    assert readiness["source_monitoring_live"] is False
    assert readiness["blocked_reasons"]
    assert not readiness_invariant_failures(readiness)


def test_readiness_preserves_the_no_go_statuses() -> None:
    readiness = build_backend_readiness(database_ready=True)
    assert readiness["customer_auth_live"] is False
    assert readiness["production_rollout"] is False
    assert readiness["controlled_customer_pilot"] is False
    assert readiness["live_source_coverage"] is False
    assert readiness["live_fetch_performed"] is False
    assert readiness["ready_to_start_monitoring"] is False


@pytest.mark.parametrize(
    "key",
    [
        "customer_auth_live",
        "production_rollout",
        "controlled_customer_pilot",
        "live_source_coverage",
        "live_fetch_performed",
    ],
)
def test_readiness_invariants_reject_a_softened_boundary(key: str) -> None:
    readiness = build_backend_readiness(database_ready=True)
    fails = readiness_invariant_failures(dict(readiness, **{key: True}))
    assert f"readiness_claimed:{key}" in fails


def test_readiness_invariants_reject_live_collectors() -> None:
    readiness = build_backend_readiness(database_ready=True)
    fails = readiness_invariant_failures(dict(readiness, collectors_live=2))
    assert "readiness_claimed_live_collectors" in fails


def test_neither_contract_carries_a_credential_key() -> None:
    health = build_backend_health(now="2026-01-01T00:00:00+00:00")
    readiness = build_backend_readiness(database_ready=True)
    for record in (health, readiness):
        for key in record:
            lowered = str(key).lower()
            for fragment in CREDENTIAL_KEY_FRAGMENTS:
                assert fragment not in lowered, key


def test_the_health_endpoint_answers(client: TestClient) -> None:
    response = client.get(HEALTHCHECK_PATH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == SERVICE_NAME
    assert payload["status"] == "ok"
    assert payload["production_ready"] is False
    assert not health_invariant_failures(payload)


def test_the_readiness_endpoint_answers(client: TestClient) -> None:
    response = client.get(READINESS_PATH)
    assert response.status_code == 200
    payload = response.json()
    assert payload["persistent_backend_live"] is False
    assert payload["collectors_live"] == 0
    assert payload["customer_auth_live"] is False
    assert not readiness_invariant_failures(payload)


def test_the_backend_health_path_is_not_the_static_stamp_path() -> None:
    """The Vite preview serves a static /health that answers ok regardless."""
    assert HEALTHCHECK_PATH == "/backend/health"
    assert HEALTHCHECK_PATH != "/health"


def test_the_original_health_endpoint_is_untouched(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "nativeforge"}


def test_no_endpoint_body_contains_a_secret(client: TestClient) -> None:
    bodies = client.get(HEALTHCHECK_PATH).text + client.get(READINESS_PATH).text
    for marker in ("-----BEGIN", "eyJ", "Bearer ", "postgresql://", "password="):
        assert marker not in bodies, marker


# --------------------------------------------------------------------------
# 101D - systemd unit template
# --------------------------------------------------------------------------


def test_the_unit_template_exists() -> None:
    assert UNIT_PATH.is_file()
    assert detect_systemd_unit_template()["available"] is True


def test_the_unit_template_binds_loopback_only() -> None:
    """A public bind here would be published through the running tunnel."""
    text = UNIT_PATH.read_text(encoding="utf-8")
    exec_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("ExecStart")
    ]
    assert exec_lines, "template has no ExecStart"
    for line in exec_lines:
        assert "--host 127.0.0.1" in line, line
        assert "0.0.0.0" not in line, line
        assert "--host ::" not in line, line
    assert detect_systemd_unit_template()["binds_loopback_only"] is True


def test_the_unit_template_contains_no_secrets() -> None:
    """Scans directives, not prose.

    The unit's own comment says "No secrets in this unit", and a first version
    of this test failed on that sentence - the Gate 93 defect where a guard
    fires on its own disclaimer. Comment lines are stripped, because a comment
    saying there are no secrets is the opposite of a leak.
    """
    text = UNIT_PATH.read_text(encoding="utf-8")
    directives = [
        line
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    lowered = "\n".join(directives).lower()
    for marker in (
        "password",
        "secret",
        "api_key",
        "token=",
        "postgresql://",
        "-----begin",
        "aws_access",
    ):
        assert marker not in lowered, f"{marker} appears in a unit directive"

    # Environment values may be referenced by file, never inlined.
    for line in directives:
        if line.strip().startswith("Environment="):
            raise AssertionError(f"inline Environment= in unit: {line}")

    # And the guard must not be vacuous: a real directive would be caught.
    poisoned = [*directives, "Environment=NF_API_TOKEN=abc123"]
    poisoned_lower = "\n".join(poisoned).lower()
    assert "token=" in poisoned_lower


def test_the_unit_template_documents_health_and_restart() -> None:
    text = UNIT_PATH.read_text(encoding="utf-8")
    assert HEALTHCHECK_PATH in text
    assert "Restart=" in text
    assert "WorkingDirectory=" in text


def test_gate_101_reports_no_install_of_its_own() -> None:
    """Gate 101 installed nothing, and its contract still says so by default.

    The host check that used to live here has moved to Gate 102, which owns
    host state: Gate 102 installed the unit with explicit operator approval, so
    a Gate 101 test asserting the file is absent would now fail for a reason
    that says nothing about Gate 101.

    What Gate 101 can still assert is its own default: the contract reports no
    installed unit unless a caller says otherwise, because it never inspects
    the host.
    """
    contract = build_backend_runtime_contract()
    assert contract["systemd_unit_installed"] is False
    assert contract["systemd_unit_enabled"] is False


def test_the_loopback_detector_rejects_a_public_template(tmp_path: Path) -> None:
    """Not a hardcoded true: give it a bad template and it says so."""
    unit = tmp_path / SYSTEMD_UNIT_RELATIVE_PATH
    unit.parent.mkdir(parents=True)
    unit.write_text(
        "[Service]\nExecStart=/x/uvicorn app --host 0.0.0.0 --port 8000\n",
        encoding="utf-8",
    )
    detected = detect_systemd_unit_template(repo_root=tmp_path)
    assert detected["available"] is True
    assert detected["binds_loopback_only"] is False


# --------------------------------------------------------------------------
# 101E - readiness integration
# --------------------------------------------------------------------------


def test_the_scheduler_readiness_detects_the_missing_backend() -> None:
    detected = detect_persistent_backend()
    assert detected["available"] is False
    assert detected["backend_runtime_mode"] == "loopback_backend_contract"
    assert detected["backend_runtime_contract_available"] is True


def test_scheduler_readiness_reports_the_backend_apart_from_its_contract() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["persistent_backend_live"] is False
    assert readiness["backend_runtime_contract_available"] is True
    assert readiness["backend_runtime_mode"] == "loopback_backend_contract"
    assert not scheduler_readiness_invariant_failures(readiness)


def test_the_backend_is_remaining_work_unlike_the_dry_run_components() -> None:
    readiness = build_scheduler_readiness()
    assert "persistent_backend" in readiness["components_missing"]
    assert "persistent_backend" in readiness["remaining_work"]
    assert set(readiness["remaining_work"]) <= RUNTIME_COMPONENT_KEYS


def test_monitoring_cannot_be_live_without_a_persistent_backend() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["source_monitoring_live"] is False
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, source_monitoring_live=True)
    )
    assert "monitoring_live_without_a_persistent_backend" in fails


def test_monitoring_stays_false_when_only_the_backend_is_missing(monkeypatch) -> None:
    """The backend conjunct in `source_monitoring_live`, forced into view.

    Today `runtime_mode` is never live, so every conjunct after the first is
    unobservable and a mutation dropping this one survived the rest of the file.
    This builds the one world that distinguishes them: a live runtime mode, a
    worker, a trigger - and no backend process. The answer must still be false.
    """
    import nativeforge.services.source_scheduler_readiness_service as mod

    monkeypatch.setattr(
        mod,
        "detect_runtime_mode",
        lambda *, repo_root=None: {
            "runtime_mode": "production_worker_live",
            "evidence": "test",
            "detection_method": "test",
            "dry_run_runtime_available": True,
            "background_worker_available": True,
            "periodic_trigger_available": True,
            "executes_jobs": True,
        },
    )
    monkeypatch.setattr(
        mod,
        "detect_background_worker",
        lambda: {
            "available": True,
            "detection_method": "test",
            "worker_modules": ["nativeforge.workers"],
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
            "trigger_files": ["deploy/systemd/x.timer"],
            "searched_directories": [],
            "searched_suffixes": [],
            "host_schedulers_inspected": False,
        },
    )

    readiness = mod.build_scheduler_readiness()
    assert readiness["background_worker_available"] is True
    assert readiness["periodic_trigger_available"] is True
    assert readiness["runtime_mode"] == "production_worker_live"
    assert readiness["persistent_backend_live"] is False
    # Three of four conjuncts true, and it is still not monitoring.
    assert readiness["source_monitoring_live"] is False


def test_readiness_still_says_not_ready_to_start_monitoring() -> None:
    assert build_scheduler_readiness()["ready_to_start_monitoring"] is False


def test_an_in_process_worker_is_blocked_without_a_persistent_backend() -> None:
    decision = build_worker_runtime_decision()
    assert decision["persistent_backend_live"] is False
    assert decision["in_process_worker_possible"] is False
    assert "persistent_backend_not_live" in decision["blocked_reasons"]
    assert not worker_runtime_invariant_failures(decision)


def test_worker_invariants_reject_an_in_process_claim_without_a_backend() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, in_process_worker_possible=True)
    )
    assert "in_process_possibility_disagrees_with_the_backend" in fails


def test_worker_invariants_reject_a_production_worker_without_a_backend() -> None:
    decision = build_worker_runtime_decision()
    fails = worker_runtime_invariant_failures(
        dict(decision, production_worker_live=True)
    )
    assert "production_worker_live_without_a_persistent_backend" in fails


def test_background_worker_and_production_worker_remain_false() -> None:
    decision = build_worker_runtime_decision()
    assert decision["background_worker_available"] is False
    assert decision["production_worker_live"] is False
    assert build_scheduler_readiness()["background_worker_available"] is False


def test_the_dry_run_worker_remains_available() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["dry_run_worker_available"] is True
    assert readiness["dry_run_runtime_available"] is True


def test_may_fetch_live_now_remains_false() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    assert matrix["sources_may_fetch_live_now"] == 0
    assert matrix["persistent_backend_live"] is False
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


def test_policy_invariants_reject_scheduling_without_a_backend() -> None:
    import nativeforge.services.phase1_collector_activation_policy_service as pol

    matrix = pol.build_phase1_activation_matrix(
        preflight_by_source=pol.default_phase1_preflights()
    )
    fails = pol.policy_invariant_failures(
        dict(matrix, sources_may_schedule_monitor=3)
    )
    assert "scheduling_without_a_persistent_backend" in fails


def test_preflight_invariants_reject_scheduling_without_a_backend() -> None:
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
    assert result["persistent_backend_live"] is False
    assert result["safe_to_schedule"] is False
    fails = pre.preflight_invariant_failures(dict(result, safe_to_schedule=True))
    assert "safe_to_schedule_without_a_persistent_backend" in fails


# --------------------------------------------------------------------------
# 101 - the services do not fetch
# --------------------------------------------------------------------------


GATE101_SERVICES = (
    "backend_runtime_contract_service",
    "backend_runtime_readiness_artifact_service",
)


def _service_source(name: str) -> str:
    return (REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", GATE101_SERVICES)
def test_no_gate101_service_imports_an_http_client(name: str) -> None:
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


@pytest.mark.parametrize("name", GATE101_SERVICES)
def test_no_gate101_service_imports_a_collector(name: str) -> None:
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


@pytest.mark.parametrize(
    "name",
    [
        *GATE101_SERVICES,
        "backend_health_readiness_service",
    ],
)
def test_every_gate101_service_declares_a_schema_version(name: str) -> None:
    module = __import__(f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"])
    assert module.SCHEMA_VERSION.startswith("nf_")


# --------------------------------------------------------------------------
# 101F - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_backend_runtime_artifacts(repo_root=first)
    write_backend_runtime_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    write_backend_runtime_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_five_artifacts_are_written(tmp_path: Path) -> None:
    result = write_backend_runtime_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 5
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_seven_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


def test_the_artifacts_declare_no_live_work() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_runtime_readiness.json"
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["backend_runtime_contract_available"] is True
    assert payload["collectors_live"] == 0
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False, key


def test_the_systemd_contract_records_nothing_was_installed() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_systemd_unit_contract.json"
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["installed_by_this_gate"] is False
    assert payload["enabled_by_this_gate"] is False
    assert payload["binds_loopback_only"] is True
    assert payload["carries_secrets"] is False


def test_the_health_contract_uses_a_placeholder_sha_not_a_real_commit() -> None:
    """A real sha would make the committed artifact stale on the next commit."""
    path = REPO_ROOT / ARTIFACT_DIR / "backend_health_contract.json"
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["example_only"] is True
    assert payload["example"]["git_sha"] == REFERENCE_GIT_SHA
    assert payload["health_claims_production_readiness"] is False


def test_the_readiness_artifact_omits_the_database_check() -> None:
    """A host property in a committed artifact never matches a fresh run."""
    path = REPO_ROOT / ARTIFACT_DIR / "backend_runtime_readiness.json"
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "database_ready" not in payload["readiness"]


def test_the_csv_stamps_declarations_on_every_row() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "backend_runtime_readiness.csv"
    if not path.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 1
    for line in lines[1:]:
        assert line.endswith("True,False,False,0,False,False,False"), line


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_backend_readiness_bundle(repo_root=REPO_ROOT)
    assert artifact_claim_failures(bundle, render_readiness_summary(bundle)) == []


def test_the_writer_refuses_a_forged_declaration(tmp_path: Path, monkeypatch) -> None:
    import nativeforge.services.backend_runtime_readiness_artifact_service as mod

    real = mod.build_backend_readiness_bundle

    def lying(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["persistent_backend_live"] = True
        return bundle

    monkeypatch.setattr(mod, "build_backend_readiness_bundle", lying)
    with pytest.raises(BackendRuntimeArtifactError):
        mod.write_backend_runtime_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_the_writer_refuses_a_public_binding_template(
    tmp_path: Path, monkeypatch
) -> None:
    """The one mistake in this gate that would actually matter."""
    import nativeforge.services.backend_runtime_readiness_artifact_service as mod

    real = mod.build_backend_readiness_bundle

    def public(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["systemd_contract"] = dict(
            bundle["systemd_contract"], binds_loopback_only=False
        )
        return bundle

    monkeypatch.setattr(mod, "build_backend_readiness_bundle", public)
    with pytest.raises(BackendRuntimeArtifactError):
        mod.write_backend_runtime_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_no_artifact_contains_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("backend runtime artifacts not generated in this tree")
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
    assert proc.returncode != 0, "backend runtime artifacts are gitignored"


# --------------------------------------------------------------------------
# 101 - cross-cutting
# --------------------------------------------------------------------------


def test_the_gate_starts_no_backend_and_does_no_live_work() -> None:
    contract = build_backend_runtime_contract()
    readiness = build_scheduler_readiness()
    assert contract["backend_started"] is False
    assert contract["live_fetch_performed"] is False
    assert contract["collectors_live"] == 0
    assert readiness["scheduled_jobs_started"] == 0
    assert readiness["checks_executed"] == 0
    assert readiness["collectors_active"] is False
    assert readiness["live_source_coverage"] is False


def test_no_environment_variable_can_declare_a_live_backend(monkeypatch) -> None:
    for name in (
        "NF_BACKEND_LIVE",
        "NF_PERSISTENT_BACKEND",
        "NF_PRODUCTION_ROLLOUT",
        "NF_CUSTOMER_AUTH_LIVE",
    ):
        monkeypatch.setenv(name, "true")
    contract = build_backend_runtime_contract()
    assert contract["persistent_backend_live"] is False
    assert contract["customer_auth_live"] is False
    assert build_backend_readiness(database_ready=True)["production_rollout"] is False
