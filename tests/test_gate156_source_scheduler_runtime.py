"""Gate 156: a scheduler that evaluates 177 sources and refuses all 177.

The distinction this gate exists to hold:

```text
scheduler_runtime_ready   the machinery to evaluate a schedule exists
source_monitoring_live    something is polling a source
```

The first became true. The second is a constant `False` with no branch that
computes it. A runtime that refuses everything is exactly as far from monitoring
as no runtime at all — it is just honest about which of the two it is.

Two things this gate deliberately does NOT do:

1. It adds no scheduling package. Gate 143's blocker
   `scheduler_component_absent:scheduler_runtime` is `find_spec` over eight
   third-party packages, so `pip install apscheduler` would clear it without
   computing a single due date. The blocker stays listed and `uv.lock` is
   untouched.

2. It adds no migration. `nf_opportunity_sources` already carries
   `check_interval_days`, `next_check_due_at` and `last_checked_at`. A new
   table would duplicate ten columns and create two places to ask when a source
   is due.

It also does not write a second job model: `build_collection_job` composes Gate
99B's `build_source_job` rather than replacing it, because
`source_collection_job_model_service` sits one word from
`source_scheduler_job_model_service` and Gate 153 overwrote a 320-line module by
picking a name that was already taken.
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
    source_scheduler_artifact_gate156_service as art,
)
from nativeforge.services.readiness_verifier_registry_service import VERIFIERS
from nativeforge.services.source_collection_job_model_service import (
    JOB_FIELDS,
    build_collection_job,
    collection_job_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_health_service import (
    CONDITIONS,
    build_scheduler_health,
    scheduler_health_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    CYCLE_MODE_EVALUATE_ONLY,
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_scheduler_runtime_service import (
    BLOCK_ACTIVATION,
    BLOCK_DISABLED,
    BLOCK_HUMAN_REVIEW,
    BLOCK_NO_CADENCE,
    BLOCK_NO_COLLECTOR,
    BLOCK_TERMS,
    BLOCK_UNKNOWN_SOURCE,
    BLOCKED,
    DISABLED,
    DUE,
    RUNTIME_STATES,
    SCHEDULED,
    UNKNOWN,
    WAITING,
    compute_next_run_at,
    evaluate_source_schedule,
    schedule_evaluation_invariant_failures,
)
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000156"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

NOW = "2026-09-15T12:00:00Z"

VERIFIER_SCRIPT = (
    REPO_ROOT / "scripts" / "verify_nativeforge_source_scheduler_runtime.sh"
)

GATE_156_MODULES = (
    "src/nativeforge/services/source_collection_scheduler_runtime_service.py",
    "src/nativeforge/services/source_collection_job_model_service.py",
    "src/nativeforge/services/source_collection_scheduler_loop_service.py",
    "src/nativeforge/services/source_collection_scheduler_health_service.py",
    "src/nativeforge/api/source_collection_scheduler_routes.py",
)

#: Every prerequisite affirmatively true. The only input that permits.
PERMITTED = dict(
    activation_state="activation_approved",
    terms_state="terms_approved",
    human_review_state="human_review_cleared",
    is_enabled=True,
    collector_registered=True,
)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _evaluate(**overrides):
    return evaluate_source_schedule(
        **{
            "source_id": "s1",
            "now": NOW,
            "last_checked_at": "2026-09-01T12:00:00Z",
            "check_interval_days": 7,
            **PERMITTED,
            **overrides,
        }
    )


# ------------------------------------------------- 156B computing a next run


def test_a_next_run_is_computed_from_an_interval_and_a_last_check():
    """The one thing Gates 98-100 do not do."""
    result = compute_next_run_at(
        last_checked_at="2026-09-01T12:00:00Z", check_interval_days=7
    )
    assert result["next_run_at"] == "2026-09-08T12:00:00+00:00"
    assert result["source_of_truth"] == "computed"


def test_no_cadence_means_never_due_not_check_it_now():
    result = compute_next_run_at(last_checked_at="2026-09-01T12:00:00Z")
    assert result["next_run_at"] is None
    assert result["no_cadence_means_never_due"] is True


def test_never_checked_with_an_interval_is_still_undetermined():
    result = compute_next_run_at(check_interval_days=7)
    assert result["next_run_at"] is None
    assert result["source_of_truth"] == "undetermined"


def test_a_recorded_due_date_wins_and_the_disagreement_is_reported():
    result = compute_next_run_at(
        last_checked_at="2026-09-01T12:00:00Z",
        check_interval_days=7,
        recorded_next_check_due_at="2026-10-01T00:00:00Z",
    )
    assert result["source_of_truth"] == "recorded"
    assert result["next_run_at"] == "2026-10-01T00:00:00+00:00"
    assert result["disagrees"] is True


def test_a_zero_or_negative_interval_is_no_interval():
    for interval in (0, -1, "0"):
        result = compute_next_run_at(
            last_checked_at="2026-09-01T12:00:00Z", check_interval_days=interval
        )
        assert result["check_interval_days"] is None, interval


def test_an_unparseable_timestamp_is_unknown_not_an_exception():
    result = compute_next_run_at(last_checked_at="not-a-date", check_interval_days=7)
    assert result["next_run_at"] is None


def test_the_computation_is_deterministic():
    kwargs = {"last_checked_at": "2026-09-01T12:00:00Z", "check_interval_days": 7}
    assert compute_next_run_at(**kwargs) == compute_next_run_at(**kwargs)


# ---------------------------------------------------- the permitting branch


def test_the_permitting_branch_is_reachable():
    """A refusal nobody can escape proves nothing about the refusals."""
    result = _evaluate()
    assert result["executable"] is True
    assert result["runtime_state"] == DUE
    assert result["blockers"] == []
    assert schedule_evaluation_invariant_failures(result) == []


def test_a_job_not_yet_due_is_scheduled_not_executable():
    result = _evaluate(last_checked_at="2026-09-14T12:00:00Z", check_interval_days=30)
    assert result["runtime_state"] == SCHEDULED
    assert result["due"] is False
    assert result["executable"] is False


# ------------------------------------------------------ every refusal path


@pytest.mark.parametrize(
    "override,expected_blocker",
    [
        ({"terms_state": "terms_unknown"}, BLOCK_TERMS),
        ({"terms_state": None}, BLOCK_TERMS),
        ({"human_review_state": "human_review_required"}, BLOCK_HUMAN_REVIEW),
        ({"activation_state": "activation_blocked"}, BLOCK_ACTIVATION),
        ({"activation_state": None}, BLOCK_ACTIVATION),
        ({"collector_registered": False}, BLOCK_NO_COLLECTOR),
        ({"is_enabled": False}, BLOCK_DISABLED),
        ({"known_source": False}, BLOCK_UNKNOWN_SOURCE),
        ({"check_interval_days": None}, BLOCK_NO_CADENCE),
    ],
)
def test_each_refusal_path_refuses_and_names_itself(override, expected_blocker):
    result = _evaluate(**override)
    assert result["executable"] is False
    assert expected_blocker in result["blockers"]
    assert schedule_evaluation_invariant_failures(result) == []


def test_absence_is_never_permission():
    """A source whose terms nobody has read is UNKNOWN, and UNKNOWN blocks."""
    result = evaluate_source_schedule(source_id="s1", now=NOW, check_interval_days=7)
    assert result["executable"] is False
    assert BLOCK_TERMS in result["blockers"]
    assert BLOCK_ACTIVATION in result["blockers"]
    assert BLOCK_HUMAN_REVIEW in result["blockers"]


def test_an_enabled_schedule_alone_does_not_make_a_job_executable():
    result = evaluate_source_schedule(
        source_id="s1",
        now=NOW,
        last_checked_at="2026-09-01T12:00:00Z",
        check_interval_days=7,
        is_enabled=True,
    )
    assert result["due"] is True
    assert result["executable"] is False


def test_due_is_reported_even_when_the_job_is_blocked():
    """Hiding the clock behind the refusal makes a backlog invisible."""
    result = _evaluate(terms_state="terms_unknown")
    assert result["due"] is True
    assert result["executable"] is False
    assert result["runtime_state"] == BLOCKED


def test_a_disabled_source_reports_disabled_not_merely_blocked():
    assert _evaluate(is_enabled=False)["runtime_state"] == DISABLED


def test_an_unknown_source_reports_unknown():
    assert _evaluate(known_source=False)["runtime_state"] == UNKNOWN


def test_a_source_with_no_clock_is_waiting():
    result = evaluate_source_schedule(source_id="s1", now=None, **PERMITTED)
    assert result["runtime_state"] in (WAITING, BLOCKED)
    assert result["executable"] is False


@pytest.mark.parametrize("state", RUNTIME_STATES)
def test_every_runtime_state_is_in_the_vocabulary(state):
    assert state in RUNTIME_STATES


def test_an_evaluation_claiming_execution_is_refused():
    result = {**_evaluate(), "collector_invoked": True}
    assert "runtime_claimed:collector_invoked" in (
        schedule_evaluation_invariant_failures(result)
    )


def test_an_evaluation_executable_with_blockers_is_refused():
    result = {**_evaluate(), "blockers": ["something"], "blocker_count": 1}
    assert "executable_alongside_blockers" in (
        schedule_evaluation_invariant_failures(result)
    )


# ------------------------------------------------------- 156C the job model


def test_the_job_carries_every_declared_field():
    job = build_collection_job(source_id="s1", now=NOW, **PERMITTED)
    for field in JOB_FIELDS:
        assert field in job, field


def test_the_job_model_composes_gate_99b_rather_than_replacing_it():
    job = build_collection_job(source_id="s1", now=NOW, **PERMITTED)
    assert job["job_id"]
    assert "build_source_job" in job["built_on_gate_99b"]
    assert job["execution_mode"] == "dry_run"


def test_a_job_never_claims_execution():
    job = build_collection_job(source_id="s1", now=NOW, **PERMITTED)
    assert job["collector_invoked"] is False
    assert job["fetch_performed"] is False
    assert job["executed"] is False
    assert job["network_calls"] == 0
    assert job["rows_written"] == 0
    assert collection_job_invariant_failures(job) == []


def test_a_job_claiming_it_ran_is_refused():
    job = {
        **build_collection_job(source_id="s1", now=NOW, **PERMITTED),
        "executed": True,
    }
    assert "job_claimed:executed" in collection_job_invariant_failures(job)


def test_a_blocked_job_is_not_executable():
    job = build_collection_job(
        source_id="s1", now=NOW, **{**PERMITTED, "terms_state": "terms_unknown"}
    )
    assert job["executable"] is False
    assert job["blockers"]
    assert collection_job_invariant_failures(job) == []


def test_the_job_model_is_deterministic():
    kwargs = {"source_id": "s1", "now": NOW, **PERMITTED}
    assert build_collection_job(**kwargs) == build_collection_job(**kwargs)


# ------------------------------------------------------------ 156E the loop


def _sources(n: int = 3, **overrides):
    return [
        {
            "source_id": f"s{i}",
            "check_interval_days": 7,
            "last_checked_at": "2026-09-01T12:00:00Z",
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
            **overrides,
        }
        for i in range(n)
    ]


def test_a_cycle_is_deterministic():
    sources = _sources()
    assert run_scheduler_cycle(now=NOW, sources=sources) == run_scheduler_cycle(
        now=NOW, sources=sources
    )


def test_an_empty_allowlist_yields_zero_executable_jobs():
    cycle = run_scheduler_cycle(now=NOW, sources=_sources(5))
    assert cycle["jobs_known"] == 5
    assert cycle["jobs_executable"] == 0
    assert cycle["jobs_refused"] == 5
    assert cycle_invariant_failures(cycle) == []


def test_zero_executable_comes_from_counting_not_a_guard():
    """A guard that special-cases the safe state stops working when it changes.

    Proved behaviourally, not by reading the source. A first version scanned the
    module text for `allowlist_empty` and was tripped by the docstring that
    explains there is no such branch - substring versus meaning, in the scan
    built to rule the branch out.

    If a guard existed, permitting every prerequisite would still yield zero.
    The same loop, the same call, three executable jobs: there is no guard.
    """
    blocked = run_scheduler_cycle(now=NOW, sources=_sources(3))
    assert blocked["jobs_executable"] == 0

    permitted = run_scheduler_cycle(now=NOW, sources=_sources(3, **PERMITTED))
    assert permitted["jobs_executable"] == 3
    assert cycle_invariant_failures(permitted) == []


def test_a_cycle_counts_every_refusal_reason():
    cycle = run_scheduler_cycle(now=NOW, sources=_sources(4))
    assert cycle["refusal_reasons"][BLOCK_TERMS] == 4
    assert cycle["refusal_reasons"][BLOCK_ACTIVATION] == 4
    assert cycle["distinct_refusal_reasons"] >= 3


def test_every_job_in_a_cycle_has_a_state():
    cycle = run_scheduler_cycle(now=NOW, sources=_sources(6))
    assert sum(cycle["jobs_by_state"].values()) == cycle["jobs_known"]


def test_an_empty_source_list_is_an_empty_cycle():
    cycle = run_scheduler_cycle(now=NOW, sources=[])
    assert cycle["jobs_known"] == 0
    assert cycle["jobs_executable"] == 0
    assert cycle_invariant_failures(cycle) == []


def test_a_cycle_starts_no_thread_and_calls_nothing():
    cycle = run_scheduler_cycle(now=NOW, sources=_sources())
    assert cycle["threads_started"] == 0
    assert cycle["collectors_invoked"] == 0
    assert cycle["live_source_calls"] == 0
    assert cycle["network_calls"] == 0
    assert cycle["urls_fetched"] == 0
    assert cycle["raw_payloads_written"] == 0
    assert cycle["clock_is_injected"] is True


def test_a_cycle_in_an_unimplemented_mode_is_refused():
    cycle = {**run_scheduler_cycle(now=NOW, sources=_sources()), "mode": "dispatch"}
    assert "cycle_ran_in_an_unimplemented_mode:dispatch" in (
        cycle_invariant_failures(cycle)
    )


def test_a_cycle_that_counted_a_network_call_is_refused():
    cycle = {**run_scheduler_cycle(now=NOW, sources=_sources()), "network_calls": 1}
    assert "cycle_counted:network_calls" in cycle_invariant_failures(cycle)


def test_the_cycle_mode_is_evaluate_only():
    assert run_scheduler_cycle(now=NOW, sources=[])["mode"] == CYCLE_MODE_EVALUATE_ONLY


# ---------------------------------------------------------- 156F the health


def _health(**overrides):
    cycle = run_scheduler_cycle(now=NOW, sources=_sources(4))
    return build_scheduler_health(
        **{
            "cycle": cycle,
            "scheduler_process_active": None,
            "persistent_state_available": True,
            "activation_allowlist_count": 0,
            **overrides,
        }
    )


def test_the_scheduler_runtime_is_ready():
    health = _health()
    assert health["scheduler_runtime_ready"] is True
    assert health["blockers"] == []
    assert scheduler_health_invariant_failures(health) == []


def test_runtime_ready_does_not_mean_source_monitoring_live():
    """The whole point of the gate."""
    health = _health()
    assert health["scheduler_runtime_ready"] is True
    assert health["source_monitoring_live"] is False
    assert "polling" in health["runtime_ready_is_not_monitoring_live"]


def test_health_reports_zero_executable_jobs():
    health = _health()
    assert health["jobs_executable"] == 0
    assert health["activation_allowlist_count"] == 0
    assert health["jobs_blocked"] == 4


def test_a_health_claiming_monitoring_live_is_refused():
    health = {**_health(), "source_monitoring_live": True}
    assert "source_monitoring_live_became_true" in (
        scheduler_health_invariant_failures(health)
    )


def test_executable_jobs_with_an_empty_allowlist_are_refused():
    health = {**_health(), "jobs_executable": 3}
    failures = scheduler_health_invariant_failures(health)
    assert "executable_jobs_with_an_empty_allowlist" in failures
    assert "more_executable_jobs_than_approved_sources" in failures


def test_a_health_without_a_cycle_is_not_ready():
    health = build_scheduler_health(cycle=None)
    assert health["scheduler_runtime_ready"] is False
    assert health["blockers"]


def test_the_scheduler_process_is_unknown_not_assumed():
    """A process is Gate 157. A request cannot know, and does not guess."""
    health = _health()
    assert health["scheduler_process_active"] is None
    assert health["scheduler_process_is_gate_157"] is True


@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_health_condition_has_declared_evidence(condition):
    assert _health()["condition_evidence"].get(condition)


# ------------------------------------------- what this gate does not touch


def test_no_scheduling_package_was_added():
    """A package would clear Gate 143's blocker without computing a due date."""
    readiness = build_scheduler_readiness()
    assert readiness["scheduler_package_installed"] is False
    assert "scheduler_runtime" in readiness["components_missing"]


def test_no_migration_was_added():
    """nf_opportunity_sources already carries the scheduling columns."""
    versions = sorted(
        path.name for path in (REPO_ROOT / "alembic" / "versions").glob("0*.py")
    )
    assert versions[-1].startswith("0042")
    assert not any("scheduler" in name for name in versions)


@pytest.mark.parametrize("module", GATE_156_MODULES)
def test_no_scheduler_module_imports_the_network(module):
    """Parsed, not grepped."""
    network = {
        "httpx",
        "requests",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "aiohttp",
        "ftplib",
        "telnetlib",
        "smtplib",
        "subprocess",
    }
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in network, f"{module}:{alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in network, module


@pytest.mark.parametrize(
    "module",
    (
        "src/nativeforge/services/source_collection_scheduler_runtime_service.py",
        "src/nativeforge/services/source_collection_scheduler_loop_service.py",
    ),
)
def test_the_runtime_never_reads_the_wall_clock(module):
    """An injected clock is what makes a cycle reproducible."""
    tree = ast.parse((REPO_ROOT / module).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None)
            owner = getattr(getattr(node.func, "value", None), "id", None)
            assert not (
                name in {"now", "utcnow", "today"}
                and owner in {"datetime", "date", "time"}
            ), module


def test_no_credentials_are_required():
    cycle = run_scheduler_cycle(now=NOW, sources=_sources())
    assert cycle["api_key_required"] is False
    assert _health()["api_key_required"] is False


# ---------------------------------------------------------- 156H the routes


ROUTES = ("health", "jobs", "blockers")


@pytest.mark.parametrize("path", ROUTES)
def test_every_get_route_requires_a_session(client, path):
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/{path}"
    ).status_code in (401, 403)


def test_the_dry_run_route_requires_a_session(client):
    assert client.post(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/dry-run", json={}
    ).status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_a_forged_header_cannot_override_the_org(client, path):
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/{path}",
        headers=soh.forged_header_only(DEMO),
    ).status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_another_organization_is_refused(client, path):
    soh.ensure_org(OTHER, "demo")
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/{path}",
        headers=soh.session_headers(OTHER),
    ).status_code in (403, 404)


def test_the_health_route_reports_ready_and_not_live(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["scheduler_runtime_ready"] is True
    assert body["source_monitoring_live"] is False
    assert body["jobs_executable"] == 0


def test_the_jobs_route_reports_every_source_refusing(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/jobs",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["jobs_known"] > 0
    assert body["jobs_executable"] == 0
    assert body["jobs_refused"] == body["jobs_known"]


def test_the_blockers_route_says_what_would_have_to_change(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/blockers",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["refusal_reasons"]
    assert body["activation_allowlist_count"] == 0
    assert any("terms" in item for item in body["what_would_have_to_change"])


def test_the_dry_run_route_evaluates_and_changes_nothing(client):
    soh.ensure_org(DEMO, "demo")
    body = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/dry-run",
        headers=soh.session_headers(DEMO),
        json={"now": NOW},
    ).json()
    assert body["jobs_executable"] == 0
    assert body["collectors_invoked"] == 0
    assert body["live_source_calls"] == 0
    assert body["rows_written"] == 0
    assert body["activation_changed"] is False
    assert body["source_approved"] is False
    assert body["source_monitoring_live"] is False


def test_no_route_response_carries_an_address_a_subject_or_the_real_org(client):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for path in ROUTES:
        body = client.get(
            f"/v1/nf/demo/orgs/{DEMO}/source-scheduler/{path}", headers=headers
        ).text
        assert not ADDRESS_SHAPE.search(body), path
        assert not SUBJECT_SHAPE.search(body), path
        assert REAL not in body, path


# -------------------------------------------------------- 156K the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = art.write_scheduler_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.scheduler_artifact_invariant_failures(result) == []
    assert result["file_count"] == 8


def test_the_artifacts_are_deterministic():
    assert art.build_scheduler_artifacts() == art.build_scheduler_artifacts()


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_scheduler_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_no_artifact_carries_an_address_a_subject_or_the_real_org():
    for name, body in art.build_scheduler_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        assert REAL not in body, name


def test_no_artifact_claims_monitoring_is_live():
    blob = "\n".join(art.build_scheduler_artifacts().values()).lower()
    assert '"source_monitoring_live": true' not in blob


def test_the_survey_artifact_explains_the_package_blocker_it_leaves_alone():
    survey = json.loads(art.build_scheduler_artifacts()[art.SURVEY_FILE])
    two = survey["the_two_things_called_scheduler_runtime"]
    assert two["is_this_a_defect"].startswith("no")
    assert "without computing a single due date" in two["the_consequence"]


def test_the_survey_artifact_explains_why_no_migration_was_added():
    survey = json.loads(art.build_scheduler_artifacts()[art.SURVEY_FILE])
    assert survey["no_migration_was_added"]["alembic_head_unchanged"] is True
    assert "check_interval_days" in survey["no_migration_was_added"]["why"]


def test_the_blockers_artifact_refuses_the_monitoring_claim():
    body = art.build_scheduler_artifacts()[art.BLOCKERS_FILE]
    assert "NativeForge monitors grant sources" in body
    assert "It does not" in body


# --------------------------------------------------------- 156I the verifier


def test_the_verifier_exists_and_is_executable():
    assert VERIFIER_SCRIPT.exists()
    assert VERIFIER_SCRIPT.stat().st_mode & 0o111


def test_the_verifier_runs_the_existing_guards_rather_than_assuming_them():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    loop = body.split("for v in ", 1)[1].split("done", 1)[0]
    assert "no_live_source_calls" in loop
    assert "source_monitoring_preflight" in loop


def test_the_verifier_proves_the_permitting_branch_is_reachable():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "permitting_branch_is_reachable" in body


def test_the_verifier_states_it_does_not_make_monitoring_live():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "DOES NOT MAKE SOURCE MONITORING LIVE" in body
    assert "source_monitoring_live=false" in body


def test_this_gates_verifier_is_in_the_registry():
    """Gate 154's registry guard caught Gate 155 omitting this."""
    entry = next(e for e in VERIFIERS if e["verifier"] == "source_scheduler_runtime")
    assert entry["gate"] == "156"
    assert entry["lane"] == "scheduler_runtime_ready"
    assert "no_live_source_calls" in entry["depends_on"]


def test_the_no_live_source_call_guard_is_untouched():
    body = (
        REPO_ROOT / "scripts" / "verify_nativeforge_no_live_source_calls.sh"
    ).read_text(encoding="utf-8")
    assert "scheduler_runtime_ready=true" not in body
