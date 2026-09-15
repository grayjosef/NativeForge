"""Gate 154: can this deployment say what state it is in, and what to do next?

Three defects found while building this gate, each with a regression test here:

1. Lanes that are false BY DESIGN - customer_auth_live and the rest - were
   counted as health blockers. The model's own invariant caught it as
   `ready_alongside_blockers`. A lane waiting on an approver is not a fault,
   and treating it as one keeps the lane shut forever while sending an
   operator to fix something unbroken.

2. `operational_health_ready` weighed only REQUIRED components, so an
   unexpected verifier result was named in `blockers` and then ignored by the
   verdict. `required` governs how much UNKNOWN is tolerated; it never decided
   which faults count.

3. The verifier's "no service shells out" scan searched file bodies for the
   word `subprocess` and flagged three modules whose DOCSTRINGS say they start
   no subprocess. Substring versus meaning, committed by the tool built to
   prove those modules clean. It parses the AST now, and a control file proves
   the scan can still find a real one.

And one design correction: a dirty tree is not automatically `unknown`. An edit
made before the process started is an edit the process loaded.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    operational_health_artifact_gate154_service as art,
)
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    LANE_KEYS,
    build_beta_onboarding_summary,
)
from nativeforge.services.operational_health_model_service import (
    BACKEND_CODE_EDITED_SINCE_START,
    BACKEND_CODE_STALE,
    BACKEND_CODE_UNCOMMITTED,
    EXPECTED_FALSE_LANES,
    HEALTH_STATUSES,
    MIGRATION_AHEAD,
    MIGRATION_BEHIND,
    OPERATIONAL,
    REQUIRED_COMPONENTS,
    SKIPPED,
    STALE_STAMP_MISSING,
    STALE_STAMP_OLDER,
    UNKNOWN,
    build_operational_health_model,
    health_model_invariant_failures,
)
from nativeforge.services.readiness_verifier_registry_service import (
    VERIFIERS,
    build_verifier_registry,
    expected_result_for,
    registry_invariant_failures,
    verifier_expectations,
)
from nativeforge.services.runbook_health_service import (
    HUMAN_APPROVAL_REQUIRED,
    NO_ACTION,
    OPERATOR_RUNNABLE,
    build_runbook_health,
    runbook_health_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000154"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

VERIFIER_SCRIPT = (
    REPO_ROOT / "scripts" / "verify_nativeforge_operational_health_runbook.sh"
)

GATE_154_MODULES = (
    "src/nativeforge/services/operational_health_model_service.py",
    "src/nativeforge/services/runbook_health_service.py",
    "src/nativeforge/services/readiness_verifier_registry_service.py",
    "src/nativeforge/services/operational_health_artifact_gate154_service.py",
    "src/nativeforge/api/operational_health_routes.py",
)

HEALTHY = dict(
    backend_service_state="active",
    preview_service_state="active",
    tunnel_service_state="active",
    repo_head_sha="a" * 40,
    head_committed_at="2026-01-02T10:00:00Z",
    source_dirty=False,
    backend_process_started_at="2026-01-02T11:00:00Z",
    frontend_stamp_sha="a" * 40,
    repo_migration_head="0042",
    database_migration_current="0042",
)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _model(**overrides):
    return build_operational_health_model(**{**HEALTHY, **overrides})


# ------------------------------------------------------------ 154B the model


def test_the_health_model_is_deterministic():
    assert _model() == _model()


def test_a_healthy_deployment_is_ready():
    model = _model()
    assert model["operational_health_ready"] is True
    assert model["overall_status"] == OPERATIONAL
    assert model["blockers"] == []
    assert health_model_invariant_failures(model) == []


def test_a_model_supplied_nothing_is_unknown_and_not_ready():
    """Unknown is not a pass."""
    model = build_operational_health_model()
    assert model["operational_health_ready"] is False
    assert model["overall_status"] == UNKNOWN
    assert set(model["required_unknown"]) == set(REQUIRED_COMPONENTS)
    assert health_model_invariant_failures(model) == []


def test_every_required_component_is_always_present():
    names = {
        entry["component"] for entry in build_operational_health_model()["components"]
    }
    assert set(REQUIRED_COMPONENTS) <= names


def test_every_component_status_is_in_the_vocabulary():
    for entry in _model()["components"]:
        assert entry["status"] in HEALTH_STATUSES


def test_the_model_writes_nothing_and_contacts_nothing():
    model = _model()
    assert model["rows_written"] == 0
    assert model["shell_executed"] is False
    assert model["external_call_made"] is False
    assert model["email_sent"] is False
    assert model["live_source_called"] is False
    assert model["object_store_contacted"] is False
    assert model["real_organization_touched"] is False


def test_the_model_never_claims_production_monitoring():
    model = _model()
    assert model["production_monitoring_active"] is False
    assert model["external_monitoring_configured"] is False
    assert model["alerting_configured"] is False


def test_a_model_claiming_production_monitoring_is_refused():
    model = {**_model(), "production_monitoring_active": True}
    assert "model_claimed:production_monitoring_active" in (
        health_model_invariant_failures(model)
    )


def test_a_model_ready_alongside_blockers_is_refused():
    model = {**_model(), "blockers": ["something"]}
    assert "ready_alongside_blockers" in health_model_invariant_failures(model)


def test_a_model_ready_while_a_required_component_is_unknown_is_refused():
    model = {**_model(), "required_unknown": ["backend_service"]}
    assert "ready_while_a_required_component_is_unknown" in (
        health_model_invariant_failures(model)
    )


def test_a_model_missing_a_required_component_is_refused():
    model = _model()
    model["components"] = [
        e for e in model["components"] if e["component"] != "migration_head"
    ]
    assert any(
        f.startswith("required_component_absent")
        for f in health_model_invariant_failures(model)
    )


# -- the named failure modes -------------------------------------------------


@pytest.mark.parametrize(
    "override,expected_blocker",
    [
        ({"frontend_stamp_sha": "b" * 40}, STALE_STAMP_OLDER),
        ({"frontend_stamp_sha": None}, STALE_STAMP_MISSING),
        (
            {"backend_process_started_at": "2026-01-02T09:00:00Z"},
            BACKEND_CODE_STALE,
        ),
        ({"database_migration_current": "0041"}, MIGRATION_BEHIND),
        ({"database_migration_current": "0043"}, MIGRATION_AHEAD),
        ({"backend_service_state": "inactive"}, "backend_service_not_active"),
        ({"preview_service_state": "failed"}, "preview_service_not_active"),
        ({"tunnel_service_state": "inactive"}, "tunnel_service_not_active"),
        (
            {
                "source_dirty": True,
                "newest_tracked_change_at": "2026-01-02T12:00:00Z",
            },
            BACKEND_CODE_EDITED_SINCE_START,
        ),
    ],
)
def test_each_named_failure_mode_is_detected_and_named(override, expected_blocker):
    model = _model(**override)
    assert model["operational_health_ready"] is False
    assert expected_blocker in model["blockers"]
    assert health_model_invariant_failures(model) == []


@pytest.mark.parametrize(
    "override",
    [
        {"frontend_stamp_sha": "b" * 40},
        {"backend_process_started_at": "2026-01-02T09:00:00Z"},
        {"database_migration_current": "0041"},
        {"backend_service_state": "inactive"},
    ],
)
def test_each_named_failure_mode_gets_a_next_action(override):
    runbook = build_runbook_health(health_model=_model(**override))
    assert runbook["next_safe_action"]["kind"] != NO_ACTION
    assert runbook["next_safe_action"]["title"]
    assert runbook["unrecognised_blockers"] == []


def test_a_stale_stamp_is_degraded_not_blocked():
    """The preview serves; it serves the wrong commit."""
    component = next(
        e
        for e in _model(frontend_stamp_sha="b" * 40)["components"]
        if e["component"] == "frontend_stamp"
    )
    assert component["status"] == "degraded"
    assert "strict-public" in component["detail"]


def test_backend_freshness_is_inferred_from_time_not_from_a_sha():
    """Gate 154A proved /backend/health reports the repo, not the process."""
    component = next(
        e for e in _model()["components"] if e["component"] == "backend_code_freshness"
    )
    assert component["status"] == OPERATIONAL
    assert component["proof_strength"] == (
        "inferred_from_time_not_from_a_recorded_commit"
    )
    assert "PROBABLY" in component["detail"]


# -- the dirty tree correction -----------------------------------------------


def test_uncommitted_edits_the_process_already_loaded_are_not_a_fault():
    """A developer machine is dirty most of the time.

    An edit made before the process started is an edit the process contains,
    and calling that `unknown` would make this lane unreachable on any machine
    anybody is working on.
    """
    model = _model(source_dirty=True, newest_tracked_change_at="2026-01-02T10:30:00Z")
    assert model["operational_health_ready"] is True
    component = next(
        e for e in model["components"] if e["component"] == "backend_code_freshness"
    )
    assert component["state"] == BACKEND_CODE_UNCOMMITTED
    assert component["running_uncommitted_code"] is True


def test_uncommitted_edits_made_after_the_process_started_are_stale():
    model = _model(source_dirty=True, newest_tracked_change_at="2026-01-02T12:00:00Z")
    assert model["operational_health_ready"] is False
    assert BACKEND_CODE_EDITED_SINCE_START in model["blockers"]


def test_a_dirty_tree_with_no_edit_time_is_unknown():
    model = _model(source_dirty=True)
    component = next(
        e for e in model["components"] if e["component"] == "backend_code_freshness"
    )
    assert component["status"] == UNKNOWN


# -- lanes false by design ---------------------------------------------------


@pytest.mark.parametrize("lane", sorted(EXPECTED_FALSE_LANES))
def test_a_lane_false_by_design_is_not_a_health_blocker(lane):
    """The first draft counted these as blockers and closed the lane forever."""
    model = _model(lanes={lane: False})
    assert model["operational_health_ready"] is True
    assert f"lane_false:{lane}" not in model["blockers"]
    assert f"lane_false:{lane}" in model["awaiting_human_decision"]
    component = next(e for e in model["components"] if e["component"] == f"lane:{lane}")
    assert component["status"] == SKIPPED


def test_a_lane_false_that_nobody_declared_expected_is_a_real_blocker():
    model = _model(lanes={"some_lane_nobody_declared": False})
    assert model["operational_health_ready"] is False
    assert "lane_false:some_lane_nobody_declared" in model["blockers"]


def test_a_true_lane_is_operational():
    model = _model(lanes={"audit_replay_ready": True})
    component = next(
        e for e in model["components"] if e["component"] == "lane:audit_replay_ready"
    )
    assert component["status"] == OPERATIONAL


# -- verifier results --------------------------------------------------------


def test_an_expected_skip_is_not_reported_as_a_problem():
    """Gate 61/65 returning SKIP is the correct answer, not a finding."""
    model = _model(
        verifier_results={"backup_restore": "SKIP"},
        verifier_expectations=verifier_expectations(),
    )
    assert model["operational_health_ready"] is True
    component = next(
        e for e in model["components"] if e["component"] == "verifier:backup_restore"
    )
    assert component["status"] == SKIPPED


def test_an_unexpected_result_closes_the_lane():
    """The verdict must not ignore a blocker it already named."""
    model = _model(
        verifier_results={"backup_restore": "PASS"},
        verifier_expectations=verifier_expectations(),
    )
    assert model["operational_health_ready"] is False
    assert "verifier_result_unexpected:backup_restore" in model["blockers"]


def test_a_prior_verifier_failure_is_named_and_actioned():
    model = _model(
        verifier_results={"audit_replay_readiness": "BLOCKED"},
        verifier_expectations=verifier_expectations(),
    )
    assert "verifier_result_unexpected:audit_replay_readiness" in model["blockers"]
    runbook = build_runbook_health(health_model=model)
    assert runbook["next_safe_action"]["kind"] == OPERATOR_RUNNABLE
    assert "audit_replay_readiness" in runbook["next_safe_action"]["command"]


def test_a_verifier_nobody_ran_is_unknown_and_not_required():
    model = _model(verifier_results={"backup_restore": None})
    component = next(
        e for e in model["components"] if e["component"] == "verifier:backup_restore"
    )
    assert component["status"] == UNKNOWN
    assert component["required"] is False


# --------------------------------------------------------- 154D the registry


def test_the_registry_is_deterministic():
    assert build_verifier_registry() == build_verifier_registry()


def test_the_registry_has_no_invariant_failures():
    assert registry_invariant_failures(build_verifier_registry()) == []


def test_every_verifier_script_on_disk_is_registered():
    on_disk = {
        path.name.replace("verify_nativeforge_", "").replace(".sh", "")
        for path in (REPO_ROOT / "scripts").glob("verify_nativeforge_*.sh")
    }
    registered = set(build_verifier_registry()["verifier_names"])
    assert on_disk - registered == set()


def test_every_registered_verifier_has_a_script_that_exists():
    for entry in build_verifier_registry()["verifiers"]:
        assert (REPO_ROOT / entry["script"]).is_file(), entry["verifier"]


@pytest.mark.parametrize("gate", [str(n) for n in range(138, 155)])
def test_gates_138_to_154_are_each_represented(gate):
    gates = {str(entry["gate"]) for entry in VERIFIERS}
    assert gate in gates


def test_every_verifier_declares_a_lane_and_an_expected_result():
    for entry in VERIFIERS:
        assert entry["lane"], entry["verifier"]
        assert entry["expected_result"] in ("PASS", "SKIP"), entry["verifier"]


def test_every_dependency_names_a_registered_verifier():
    names = {entry["verifier"] for entry in VERIFIERS}
    for entry in VERIFIERS:
        for dependency in entry["depends_on"]:
            assert dependency in names, f"{entry['verifier']} -> {dependency}"


def test_the_registry_executes_nothing():
    registry = build_verifier_registry()
    assert registry["executes_verifiers"] is False
    assert registry["shell_executed"] is False


# -- the separation that must survive ---------------------------------------


def test_the_two_backup_harnesses_are_different_verifiers():
    separation = build_verifier_registry()["backup_lane_separation"]
    assert separation["production_harness"] == "backup_restore"
    assert separation["operational_harness"] == "backup_restore_readiness"
    assert separation["production_harness"] != separation["operational_harness"]


def test_the_production_backup_harness_is_expected_to_skip():
    assert expected_result_for("backup_restore") == "SKIP"


def test_the_gate_153_restore_harness_is_expected_to_pass():
    assert expected_result_for("backup_restore_readiness") == "PASS"


def test_the_two_backup_verifiers_do_not_share_a_lane():
    by_name = {entry["verifier"]: entry for entry in VERIFIERS}
    assert (
        by_name["backup_restore"]["lane"]
        != (by_name["backup_restore_readiness"]["lane"])
    )
    assert by_name["backup_restore"]["production"] is True
    assert by_name["backup_restore_readiness"]["production"] is False


def test_a_registry_that_merged_the_backup_lanes_is_refused():
    registry = build_verifier_registry()
    registry["backup_lane_separation"]["operational_harness"] = "backup_restore"
    assert "the_two_backup_harnesses_were_merged" in (
        registry_invariant_failures(registry)
    )


def test_a_registry_expecting_pass_from_the_production_harness_is_refused():
    registry = build_verifier_registry()
    for entry in registry["verifiers"]:
        if entry["verifier"] == "backup_restore":
            entry["expected_result"] = "PASS"
    assert "gate_61_65_backup_harness_expects_something_other_than_skip" in (
        registry_invariant_failures(registry)
    )


# ---------------------------------------------------------- 154C the runbook


def test_the_runbook_is_deterministic():
    model = _model()
    assert build_runbook_health(health_model=model) == build_runbook_health(
        health_model=model
    )


def test_a_healthy_deployment_has_nothing_to_do():
    runbook = build_runbook_health(health_model=_model())
    assert runbook["next_safe_action"]["kind"] == NO_ACTION
    assert runbook["actions"] == []
    assert runbook_health_invariant_failures(runbook) == []


def test_an_approval_gated_action_never_carries_a_command():
    """Printing the command next to 'needs approval' has already handed it over."""
    runbook = build_runbook_health(
        health_model=_model(database_migration_current="0043")
    )
    gated = [a for a in runbook["actions"] if a["kind"] == HUMAN_APPROVAL_REQUIRED]
    assert gated
    for action in gated:
        assert action["command"] is None


def test_a_runbook_that_handed_over_a_gated_command_is_refused():
    runbook = build_runbook_health(
        health_model=_model(database_migration_current="0043")
    )
    for action in runbook["actions"]:
        if action["kind"] == HUMAN_APPROVAL_REQUIRED:
            action["command"] = "rm -rf /"
    assert any(
        f.startswith("approval_gated_action_carried_a_command")
        for f in runbook_health_invariant_failures(runbook)
    )


def test_no_emitted_command_would_print_a_secret():
    """Gate 121D's rule, imported rather than reimplemented."""
    for override in (
        {"backend_service_state": "inactive"},
        {"frontend_stamp_sha": None},
        {"database_migration_current": "0041"},
    ):
        runbook = build_runbook_health(health_model=_model(**override))
        assert runbook_health_invariant_failures(runbook) == []
        for action in runbook["actions"]:
            command = action.get("command") or ""
            assert "echo $" not in command
            assert "printenv" not in command
            assert "set -x" not in command


def test_no_emitted_command_is_destructive_or_activates_a_capability():
    runbook = build_runbook_health(
        health_model=_model(backend_service_state="inactive")
    )
    for action in runbook["actions"]:
        assert action["destructive"] is False
        assert action["activates_a_capability"] is False


def test_an_unrecognised_blocker_gets_a_human_not_a_guess():
    model = {**_model(), "blockers": ["something_nobody_registered"]}
    runbook = build_runbook_health(health_model=model)
    assert runbook["unrecognised_blockers"] == ["something_nobody_registered"]
    assert runbook["actions"][0]["kind"] == HUMAN_APPROVAL_REQUIRED
    assert runbook["actions"][0]["command"] is None


def test_lanes_awaiting_a_person_are_still_shown():
    """Silence is the wrong answer to "what next" when a person must decide."""
    model = _model(lanes={"controlled_customer_pilot": False})
    runbook = build_runbook_health(health_model=model)
    assert runbook["awaiting_human_decision"] == [
        "lane_false:controlled_customer_pilot"
    ]
    assert runbook["human_approval_required_count"] == 1
    assert runbook["actions"][0]["who"]


def test_legacy_evidence_gaps_are_reported_and_never_backfilled():
    runbook = build_runbook_health(health_model=_model(), legacy_evidence_gaps=97)
    finding = next(
        f for f in runbook["findings"] if f["finding"] == "legacy_evidence_gaps"
    )
    assert finding["count"] == 97
    assert finding["must_not_be_backfilled"] is True
    assert finding["action_required"] is False


def test_a_legacy_gap_finding_that_lost_its_rule_is_refused():
    runbook = build_runbook_health(health_model=_model(), legacy_evidence_gaps=97)
    for finding in runbook["findings"]:
        finding.pop("must_not_be_backfilled", None)
    assert "legacy_gap_finding_lost_its_do_not_backfill_rule" in (
        runbook_health_invariant_failures(runbook)
    )


def test_fixture_residue_is_reported_as_a_finding():
    runbook = build_runbook_health(health_model=_model(), fixture_residue=True)
    finding = next(f for f in runbook["findings"] if f["finding"] == "fixture_residue")
    assert finding["action_required"] is True
    assert "fixture_cleanliness" in finding["detail"]


def test_the_runbook_never_claims_production_monitoring():
    runbook = build_runbook_health(health_model=_model())
    assert runbook["production_monitoring_active"] is False
    assert runbook["alerting_configured"] is False
    assert runbook["shell_executed"] is False
    assert runbook["rows_written"] == 0


def test_the_next_safe_action_is_derived_not_a_constant():
    """The one that was written down went stale nine gates ago."""
    healthy = build_runbook_health(health_model=_model())
    broken = build_runbook_health(health_model=_model(backend_service_state="inactive"))
    assert healthy["next_safe_action"] != broken["next_safe_action"]
    # The claim, not its spelling: the text must say the action comes from a
    # measured component and that the constant it replaces went stale.
    explanation = healthy["derived_not_declared"].lower()
    assert "component status" in explanation
    assert "stale" in explanation


# ---------------------------------------------- no shell anywhere in the gate


@pytest.mark.parametrize("module", GATE_154_MODULES)
def test_no_gate_154_module_imports_subprocess(module):
    """Parsed, not grepped.

    The verifier's first scan searched for the WORD `subprocess` and flagged
    modules whose docstrings say they start none.
    """
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "subprocess", module
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "subprocess", module


@pytest.mark.parametrize("module", GATE_154_MODULES)
def test_no_gate_154_module_calls_a_shell(module):
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if isinstance(func, ast.Attribute) and name in {"system", "popen", "spawn"}:
                owner = getattr(func.value, "id", "")
                assert owner not in {"os", "subprocess", "pty"}, module
            for keyword in node.keywords:
                assert not (
                    keyword.arg == "shell"
                    and getattr(keyword.value, "value", False) is True
                ), module


def test_the_shell_scan_can_actually_find_one():
    """A scan that finds nothing anywhere proves nothing about the clean files."""
    control = ast.parse(
        (
            REPO_ROOT / "src/nativeforge/services/backend_health_readiness_service.py"
        ).read_text(encoding="utf-8")
    )
    found = any(
        isinstance(node, ast.Import)
        and any(a.name.split(".")[0] == "subprocess" for a in node.names)
        for node in ast.walk(control)
    )
    assert found, "the control file no longer imports subprocess"


@pytest.mark.parametrize("module", GATE_154_MODULES)
def test_no_gate_154_module_calls_the_declaration_driven_observability_service(module):
    """`resolve_observability` returns production_monitoring on a caller's say-so."""
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "gate32_observability" not in (node.module or ""), module
            for alias in node.names:
                assert alias.name != "resolve_observability", module
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            assert name != "resolve_observability", module


# ----------------------------------------------------------- 154E the routes


ROUTES = (
    "summary",
    "verifier-registry",
    "runbook",
    "next-safe-action",
)


@pytest.mark.parametrize("path", ROUTES)
def test_every_route_requires_a_session(client, path):
    response = client.get(f"/v1/nf/demo/orgs/{DEMO}/operational-health/{path}")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_a_forged_header_cannot_override_the_org(client, path):
    headers = soh.forged_header_only(DEMO)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/{path}", headers=headers
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_another_organization_is_refused(client, path):
    soh.ensure_org(OTHER, "demo")
    headers = soh.session_headers(OTHER)
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/{path}", headers=headers
    )
    assert response.status_code in (403, 404)


@pytest.mark.parametrize("path", ROUTES)
def test_no_route_accepts_a_write_method(client, path):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for method in (client.post, client.put, client.patch, client.delete):
        response = method(
            f"/v1/nf/demo/orgs/{DEMO}/operational-health/{path}", headers=headers
        )
        assert response.status_code == 405


def test_the_summary_route_names_what_a_request_could_not_measure(client):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/summary",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json()
    # A request has no shell, so it does not claim the facts a shell provides.
    assert body["operational_health_ready"] is False
    assert set(body["requires_the_verifier"]) & set(body["required_unknown"])
    assert body["shell_executed"] is False
    assert body["production_monitoring_active"] is False


def test_the_summary_route_measures_migration_drift(client):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/summary",
        headers=soh.session_headers(DEMO),
    )
    component = next(
        e for e in response.json()["components"] if e["component"] == "migration_head"
    )
    # This one a request CAN answer, and does.
    assert component["status"] != UNKNOWN
    assert component["repo_head"] == component["database_current"]


def test_the_registry_route_returns_the_registry(client):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/verifier-registry",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verifier_count"] == len(VERIFIERS)
    assert body["backup_lane_separation"]["production_expected_result"] == "SKIP"


def test_the_next_safe_action_route_returns_one_action(client):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/operational-health/next-safe-action",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_safe_action"]["title"]
    assert body["production_monitoring_active"] is False


def test_no_route_response_carries_an_address_or_a_provider_subject(client):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for path in ROUTES:
        body = client.get(
            f"/v1/nf/demo/orgs/{DEMO}/operational-health/{path}", headers=headers
        ).text
        assert not ADDRESS_SHAPE.search(body), path
        assert not SUBJECT_SHAPE.search(body), path


# --------------------------------------------------------- 154F the cockpit


def test_the_cockpit_carries_the_four_durability_lanes():
    for key in (
        "tenant_digest_persistence",
        "audit_replay",
        "operational_backup_restore",
        "operational_health",
    ):
        assert key in LANE_KEYS


def test_the_cockpit_reports_readiness_only_without_a_verifier_run():
    """A summary that supplied its own proof would grade its own homework."""
    summary = build_beta_onboarding_summary()
    for key in (
        "tenant_digest_persistence",
        "audit_replay",
        "operational_backup_restore",
        "operational_health",
    ):
        assert summary["by_lane"][key]["status"] == "readiness_only"
        assert summary["by_lane"][key]["value"] is False


def test_the_cockpit_reports_operational_when_the_verifier_supplied_proof():
    summary = build_beta_onboarding_summary(
        tenant_digest_persistence_live=True,
        audit_replay_ready=True,
        operational_backup_restore_ready=True,
        operational_health_ready=True,
    )
    for key in (
        "tenant_digest_persistence",
        "audit_replay",
        "operational_backup_restore",
        "operational_health",
    ):
        assert summary["by_lane"][key]["status"] == "operational"


def test_the_cockpit_card_states_production_monitoring_is_not_active():
    card = build_beta_onboarding_summary()["operational_health_card"]
    assert card["production_monitoring_active"] is False
    assert "NOT active" in card["production_monitoring_statement"]
    assert card["controlled_customer_pilot_active"] is False


def test_the_cockpit_card_keeps_the_two_backup_harnesses_apart():
    card = build_beta_onboarding_summary()["operational_health_card"]
    registry = card["verifier_registry"]
    assert registry["they_are_different_lanes"] is True
    assert "SKIP" in registry["production_backup_harness"]
    assert "PASS" in registry["operational_restore_harness"]


def test_the_cockpit_card_names_the_blocked_lanes():
    card = build_beta_onboarding_summary()["operational_health_card"]
    for lane in (
        "customer_auth_live",
        "controlled_customer_pilot",
        "production_rollout",
    ):
        assert lane in card["blocked_customer_and_production_lanes"]


def test_the_cockpit_still_has_no_invariant_failures():
    from nativeforge.services.beta_onboarding_readiness_summary_service import (
        summary_invariant_failures,
    )

    assert summary_invariant_failures(build_beta_onboarding_summary()) == []


# ------------------------------------------------------- 154H the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = art.write_operational_health_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.operational_health_artifact_invariant_failures(result) == []


def test_the_artifacts_are_deterministic():
    assert (
        art.build_operational_health_artifacts()
        == art.build_operational_health_artifacts()
    )


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_operational_health_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_no_artifact_carries_an_address_or_a_provider_subject():
    for name, body in art.build_operational_health_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name


def test_no_artifact_claims_production_monitoring():
    blob = "\n".join(art.build_operational_health_artifacts().values()).lower()
    assert '"production_monitoring_active": true' not in blob
    assert '"alerting_configured": true' not in blob


def test_the_artifacts_record_the_substring_defect_this_gate_found():
    survey = json.loads(art.build_operational_health_artifacts()[art.SURVEY_FILE])
    not_observable = survey["what_was_not_observable_before_this_gate"]
    assert "request time" in not_observable["backend_stale_code"].lower()
    stamp = not_observable["stale_build_stamp"].lower()
    assert "tag exists" in stamp
    assert "never compares" in stamp


def test_the_artifacts_name_the_declaration_driven_service_they_do_not_extend():
    survey = json.loads(art.build_operational_health_artifacts()[art.SURVEY_FILE])
    named = survey["the_declaration_driven_services_this_gate_does_not_extend"]
    assert "gate32_observability_service" in named
    assert "keyword argument" in named["gate32_observability_service"]


def test_the_failure_modes_artifact_covers_every_named_mode():
    modes = json.loads(art.build_operational_health_artifacts()[art.FAILURE_MODES_FILE])
    names = {entry["mode"] for entry in modes["modes"]}
    for expected in (
        "stale_frontend_stamp",
        "unstamped_build",
        "backend_stale_code",
        "migration_not_applied",
        "prior_verifier_failed",
        "fixture_residue",
        "legacy_evidence_gaps",
        "customer_activation_blockers",
    ):
        assert expected in names


def test_the_failure_modes_artifact_carries_no_live_count():
    """Gate 153 pinned a row count and it went stale within an hour."""
    modes = json.loads(art.build_operational_health_artifacts()[art.FAILURE_MODES_FILE])
    residue = next(e for e in modes["modes"] if e["mode"] == "fixture_residue")
    # The numbers appear as a worked example of movement, explicitly labelled.
    assert "MOVE between runs" in residue["note"]


def test_an_artifact_result_missing_a_file_is_refused():
    assert any(
        f.startswith("artifact_files_missing")
        for f in art.operational_health_artifact_invariant_failures(
            {"files_written": list(art.ARTIFACT_FILES[:-1]), "file_count": 7}
        )
    )


# ------------------------------------------------------- 154G the verifier


def test_the_verifier_exists_and_is_executable():
    assert VERIFIER_SCRIPT.exists()
    assert VERIFIER_SCRIPT.stat().st_mode & 0o111


def test_the_verifier_does_not_claim_production_monitoring():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "THIS IS NOT PRODUCTION MONITORING" in body
    assert "production_monitoring=false" in body


def test_the_verifier_exercises_every_failure_mode():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    for mode in (
        "stale_frontend_stamp",
        "unstamped_build",
        "backend_stale_code",
        "code_edited_after_start",
        "migration_behind",
        "migration_ahead",
        "backend_unit_down",
    ):
        assert mode in body, mode


def test_the_verifier_parses_rather_than_greps_for_a_shell():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "import ast" in body
    assert "shell_scan_finds_a_known_offender" in body


def test_the_verifier_asserts_the_two_backup_lanes_stay_separate():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "backup_lanes_separate" in body
    assert "gate6165_expects_skip" in body


def test_the_verifier_proves_a_healthy_baseline_can_pass():
    """A detector that never passes is not a detector."""
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "detector_baseline_is_healthy" in body


def test_the_production_backup_harness_is_untouched_by_this_gate():
    body = (REPO_ROOT / "scripts" / "verify_nativeforge_backup_restore.sh").read_text(
        encoding="utf-8"
    )
    assert "operational_health_ready=true" not in body
