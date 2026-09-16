"""Gate 157: a worker that claims every job and is refused by every one.

```text
worker_runtime_ready     true
source_monitoring_live   false
```

The defect this gate found in its own verifier is the one worth reading first.
The cleanup deleted `WHERE job_id LIKE 'nf-verify-157%'`, but `job_id` is Gate
99B's sha256 digest, not the `source_id` prefix the verifier supplies. So the
delete removed one row of 278, and `fixture_rows_remaining` counted the same
empty pattern and reported 0.

**A green check with the wrong cause** — the same shape as Gate 152's
`storage_allowed` and Gate 153's digest-key mistake. Cleanup now scopes by
organization, counts the whole table, and a separate check asserts the cleanup
had something to clean: "0 remaining" on a run that wrote nothing would
otherwise pass.

The other thing worth stating: an activation refusal is **not** a retry. With
zero approved sources all 177 jobs land in a non-retrying class, and a retry
queue filling up here would be the clearest possible sign the classification
was wrong.
"""

from __future__ import annotations

import ast
import json
import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    source_worker_artifact_gate157_service as art,
)
from nativeforge.services.readiness_verifier_registry_service import VERIFIERS
from nativeforge.services.source_collection_job_lease_service import (
    CLAIMED,
    DEFAULT_MAX_ATTEMPTS,
    LEASE_STATUSES,
    REFUSED,
    TABLE_NAME,
    claim_job,
    lease_invariant_failures,
    read_lease,
    record_outcome,
)
from nativeforge.services.source_collection_retry_policy_service import (
    HUMAN_REVIEW_BLOCKED,
    MAX_BACKOFF_SECONDS,
    NONE,
    PERMANENT_WORKER_FAILURE,
    REFUSED_BY_ACTIVATION,
    RETRYABLE_CLASSES,
    TERMS_BLOCKED,
    TRANSIENT_WORKER_FAILURE,
    UNKNOWN,
    classify_blockers,
    compute_backoff_seconds,
    evaluate_retry,
    retry_invariant_failures,
)
from nativeforge.services.source_collection_worker_health_service import (
    CONDITIONS,
    build_worker_health,
    worker_health_invariant_failures,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    HANDLER_EVALUATE_ONLY,
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000157"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

T0 = "2026-09-15T12:00:00Z"
T_LATER = "2026-09-15T12:10:00Z"

VERIFIER_SCRIPT = REPO_ROOT / "scripts" / "verify_nativeforge_source_worker_runtime.sh"
WORKER_SCRIPT = REPO_ROOT / "scripts" / "run_source_collection_worker.py"

GATE_157_MODULES = (
    "src/nativeforge/services/source_collection_worker_runtime_service.py",
    "src/nativeforge/services/source_collection_job_lease_service.py",
    "src/nativeforge/services/source_collection_retry_policy_service.py",
    "src/nativeforge/services/source_collection_worker_health_service.py",
    "src/nativeforge/services/source_worker_artifact_gate157_service.py",
    "src/nativeforge/api/source_collection_worker_routes.py",
    "scripts/run_source_collection_worker.py",
)

BLOCKED_JOB = {
    "job_id": "test-job-blocked",
    "source_id": "test-src",
    "executable": False,
    "blockers": [
        "source_terms_not_approved",
        "source_activation_not_approved",
        "source_requires_human_review",
    ],
}


@pytest.fixture
def db_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(DEMO, "demo")
    with SessionLocal() as session:
        yield session
        session.rollback()


@pytest.fixture
def connection(db_session):
    return db_session.connection()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _job(job_id: str, **overrides):
    return {**BLOCKED_JOB, "job_id": job_id, **overrides}


# ------------------------------------------------------------ 157C the lease


def test_a_worker_can_claim_a_job(connection):
    result = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=f"t-{uuid.uuid4().hex[:8]}",
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    assert result["claimed"] is True
    assert result["lease"]["lease_owner"] == "worker-1"
    assert result["lease"]["lease_status"] == CLAIMED
    assert lease_invariant_failures(result) == []


def test_a_duplicate_claim_is_refused(connection):
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    first = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    assert first["claimed"] is True

    second = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-2",
        now=T0,
    )
    assert second["claimed"] is False
    assert "job_is_already_claimed_by_another_worker" in second["blocked_reasons"]
    assert "lease_has_not_expired_and_cannot_be_stolen" in second["blocked_reasons"]


def test_a_live_lease_cannot_be_stolen_even_by_the_same_worker_id(connection):
    """Two processes sharing an id is a race, not an entitlement."""
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    again = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    assert again["claimed"] is False


def test_an_expired_lease_can_be_reclaimed(connection):
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
        lease_seconds=300,
    )
    reclaim = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-2",
        now=T_LATER,
    )
    assert reclaim["claimed"] is True
    assert reclaim["reclaimed_expired_lease"] is True
    assert reclaim["lease"]["lease_owner"] == "worker-2"


def test_a_lease_without_a_worker_id_is_refused(connection):
    result = claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id="t-no-worker",
        source_id="src",
        worker_id=None,
        now=T0,
    )
    assert result["claimed"] is False
    assert "no_worker_id_supplied" in result["blocked_reasons"]


def test_the_real_organization_is_refused_by_name(connection):
    result = claim_job(
        connection=connection,
        organization_id=REAL,
        job_id="t-real",
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    assert result["claimed"] is False
    assert "real_organization_refused_by_name" in result["blocked_reasons"]


def test_an_outcome_from_a_worker_that_does_not_hold_the_lease_is_refused(
    connection,
):
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    result = record_outcome(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        worker_id="worker-2",
        lease_status=REFUSED,
        now=T0,
    )
    assert (
        "outcome_recorded_by_a_worker_that_does_not_hold_it"
        in (result["blocked_reasons"])
    )


def test_recording_an_outcome_releases_the_lease(connection):
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    record_outcome(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        worker_id="worker-1",
        lease_status=REFUSED,
        failure_class=TERMS_BLOCKED,
        blocked_reasons=["source_terms_not_approved"],
        now=T0,
    )
    lease = read_lease(
        connection=connection, organization_id=DEMO, job_id=job_id, now=T0
    )["lease"]
    assert lease["lease_owner"] is None
    assert lease["lease_status"] == REFUSED
    assert lease["failure_class"] == TERMS_BLOCKED


def test_a_lease_status_outside_the_vocabulary_is_refused(connection):
    result = record_outcome(
        connection=connection,
        organization_id=DEMO,
        job_id="t-x",
        lease_status="made_up",
        now=T0,
    )
    assert any(
        r.startswith("lease_status_outside_vocabulary")
        for r in result["blocked_reasons"]
    )


def test_the_database_refuses_a_row_claiming_a_fetch(connection):
    """The three columns exist to be checked, and cannot be set true."""
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    claim_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        source_id="src",
        worker_id="worker-1",
        now=T0,
    )
    with pytest.raises(sa.exc.IntegrityError):
        connection.execute(
            sa.text(f"UPDATE {TABLE_NAME} SET collector_invoked = 1 WHERE job_id = :j"),
            {"j": job_id},
        )


@pytest.mark.parametrize("status", LEASE_STATUSES)
def test_every_lease_status_is_in_the_vocabulary(status):
    assert status in LEASE_STATUSES


# --------------------------------------------------------- 157D the retry


@pytest.mark.parametrize(
    "klass",
    [
        REFUSED_BY_ACTIVATION,
        TERMS_BLOCKED,
        HUMAN_REVIEW_BLOCKED,
        PERMANENT_WORKER_FAILURE,
        UNKNOWN,
        NONE,
    ],
)
def test_a_non_transient_failure_is_never_retried(klass):
    """An activation refusal is not a hiccup."""
    decision = evaluate_retry(
        failure_class=klass, attempt_count=0, max_attempts=3, now=T0
    )
    assert decision["should_retry"] is False
    assert decision["why_not_retried"]
    assert retry_invariant_failures(decision) == []


def test_a_transient_failure_is_retried():
    """The retry branch must be reachable, or the refusals prove nothing."""
    decision = evaluate_retry(
        failure_class=TRANSIENT_WORKER_FAILURE,
        attempt_count=0,
        max_attempts=3,
        now=T0,
    )
    assert decision["should_retry"] is True
    assert decision["backoff_seconds"] == 60
    assert decision["next_retry_at"]
    assert retry_invariant_failures(decision) == []


def test_only_one_class_retries():
    assert RETRYABLE_CLASSES == frozenset({TRANSIENT_WORKER_FAILURE})


def test_the_retry_budget_is_bounded():
    at_budget = evaluate_retry(
        failure_class=TRANSIENT_WORKER_FAILURE,
        attempt_count=3,
        max_attempts=3,
        now=T0,
    )
    assert at_budget["should_retry"] is False
    assert "attempt_budget_exhausted" in at_budget["not_retried_because"]


def test_the_backoff_is_deterministic_and_capped():
    assert compute_backoff_seconds(1) == 60
    assert compute_backoff_seconds(2) == 120
    assert compute_backoff_seconds(3) == 240
    assert compute_backoff_seconds(99) == MAX_BACKOFF_SECONDS
    assert compute_backoff_seconds(1) == compute_backoff_seconds(1)


def test_a_retry_decision_claiming_to_retry_a_human_blocker_is_refused():
    decision = {
        **evaluate_retry(failure_class=TERMS_BLOCKED, attempt_count=0, now=T0),
        "should_retry": True,
    }
    assert f"retried_a_non_transient_failure:{TERMS_BLOCKED}" in (
        retry_invariant_failures(decision)
    )


def test_terms_is_classified_before_activation():
    """The terms review is the thing a person does first."""
    assert (
        classify_blockers(
            ["source_activation_not_approved", "source_terms_not_approved"]
        )
        == TERMS_BLOCKED
    )


def test_an_unmapped_blocker_is_not_assumed_transient():
    """Assuming it would make UNKNOWN a retry loop."""
    assert classify_blockers(["something_nobody_mapped"]) == UNKNOWN
    decision = evaluate_retry(failure_class=UNKNOWN, attempt_count=0, now=T0)
    assert decision["should_retry"] is False


def test_no_blockers_classifies_as_none():
    assert classify_blockers([]) == NONE


def test_blockers_are_matched_by_exact_value_not_substring():
    """`source_terms_not_approved` and `source_activation_not_approved` differ
    by one word; a substring match over either would catch the other."""
    assert classify_blockers(["source_terms_not_approved"]) == TERMS_BLOCKED
    assert (
        classify_blockers(["source_activation_not_approved"]) == REFUSED_BY_ACTIVATION
    )


# --------------------------------------------------------- 157B the worker


def test_a_worker_cycle_claims_and_refuses(connection):
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="worker-cycle",
        jobs=[_job(f"t-{uuid.uuid4().hex[:8]}-{i}") for i in range(5)],
        now=T0,
    )
    assert cycle["jobs_claimed"] == 5
    assert cycle["jobs_refused"] == 5
    assert cycle["jobs_completed"] == 0
    assert cycle["jobs_retryable"] == 0
    assert worker_cycle_invariant_failures(cycle) == []


def test_a_worker_cycle_is_deterministic_in_its_counts(connection):
    jobs = [_job(f"t-{uuid.uuid4().hex[:8]}-{i}") for i in range(3)]
    first = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=jobs,
        now=T0,
    )
    # A second pass over the same jobs finds them already recorded, so the
    # claim counts differ - what must not differ is the classification.
    assert first["jobs_seen"] == 3
    assert [r["failure_class"] for r in first["results"]] == [TERMS_BLOCKED] * 3


def test_a_worker_without_an_id_refuses_to_run(connection):
    cycle = run_worker_cycle(
        connection=connection, organization_id=DEMO, worker_id=None, jobs=[], now=T0
    )
    assert cycle["ran"] is False
    assert "no_worker_id_supplied" in cycle["blocked_reasons"]


def test_a_worker_without_a_connection_refuses_to_run():
    """This is what makes the route's dry-run safe rather than merely intended."""
    cycle = run_worker_cycle(
        connection=None, organization_id=DEMO, worker_id="w", jobs=[], now=T0
    )
    assert cycle["ran"] is False
    assert "no_connection_supplied" in cycle["blocked_reasons"]


def test_a_worker_without_a_clock_refuses_to_run(connection):
    cycle = run_worker_cycle(
        connection=connection, organization_id=DEMO, worker_id="w", jobs=[], now=None
    )
    assert cycle["ran"] is False
    assert "no_clock_supplied" in cycle["blocked_reasons"]


def test_an_unimplemented_handler_refuses_to_run(connection):
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=[],
        now=T0,
        handler="fetch",
    )
    assert cycle["ran"] is False
    assert "handler_not_implemented:fetch" in cycle["blocked_reasons"]


def test_an_executable_job_still_cannot_complete(connection):
    """There is no handler. The permitting branch is reachable and refuses."""
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=[
            {
                "job_id": f"t-{uuid.uuid4().hex[:8]}",
                "source_id": "src",
                "executable": True,
                "blockers": [],
            }
        ],
        now=T0,
    )
    assert cycle["jobs_claimed"] == 1
    assert cycle["jobs_completed"] == 0
    assert cycle["results"][0]["blocked_reasons"] == [
        "no_handler_implemented_in_gate_157"
    ]


def test_a_truncated_batch_says_so(connection):
    """A batch limit nobody can see is how a backlog goes unnoticed."""
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=[_job(f"t-{uuid.uuid4().hex[:8]}-{i}") for i in range(10)],
        now=T0,
        max_jobs=4,
    )
    assert cycle["jobs_offered"] == 10
    assert cycle["jobs_seen"] == 4
    assert cycle["jobs_not_reached_this_cycle"] == 6
    assert cycle["batch_was_truncated"] is True
    assert worker_cycle_invariant_failures(cycle) == []


def test_a_cycle_whose_numbers_do_not_add_up_is_refused(connection):
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=[_job(f"t-{uuid.uuid4().hex[:8]}")],
        now=T0,
    )
    cycle["jobs_offered"] = 99
    assert "jobs_offered_does_not_account_for_every_job" in (
        worker_cycle_invariant_failures(cycle)
    )


def test_a_cycle_claiming_a_completed_job_is_refused(connection):
    cycle = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="w",
        jobs=[_job(f"t-{uuid.uuid4().hex[:8]}")],
        now=T0,
    )
    cycle["results"][0]["status"] = "completed"
    cycle["jobs_completed"] = 1
    cycle["jobs_refused"] = 0
    assert any(
        f.startswith("a_job_completed_but_no_handler_exists")
        for f in worker_cycle_invariant_failures(cycle)
    )


def test_a_cycle_that_counted_a_network_call_is_refused(connection):
    cycle = run_worker_cycle(
        connection=connection, organization_id=DEMO, worker_id="w", jobs=[], now=T0
    )
    cycle["network_calls"] = 1
    assert "cycle_counted:network_calls" in worker_cycle_invariant_failures(cycle)


def test_the_worker_does_not_recompute_permission(connection):
    """It reads the scheduler's `executable`; two places would disagree."""
    cycle = run_worker_cycle(
        connection=connection, organization_id=DEMO, worker_id="w", jobs=[], now=T0
    )
    assert "reads it" in cycle["permission_is_read_not_recomputed"]
    assert cycle["handler"] == HANDLER_EVALUATE_ONLY


def test_restart_recovery_the_state_is_the_table(connection):
    """A restarted worker reads the lease table; nothing lives in memory."""
    job_id = f"t-{uuid.uuid4().hex[:8]}"
    run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="worker-before-restart",
        jobs=[_job(job_id)],
        now=T0,
    )
    # A "restarted" worker is simply a new call with a new id.
    lease = read_lease(
        connection=connection, organization_id=DEMO, job_id=job_id, now=T_LATER
    )["lease"]
    assert lease is not None
    assert lease["lease_status"] == REFUSED
    assert lease["failure_class"] == TERMS_BLOCKED


# --------------------------------------------------------- 157G the health


def _health(**overrides):
    cycle = {
        "results": [],
        "jobs_claimed": 0,
        "jobs_completed": 0,
        "jobs_refused": 0,
        "jobs_retryable": 0,
        "jobs_failed": 0,
        "jobs_seen": 0,
        "jobs_offered": 0,
        "jobs_not_reached_this_cycle": 0,
        "batch_was_truncated": False,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "invariant_failures": [],
        "worker_id": "w",
        "handler": HANDLER_EVALUATE_ONLY,
    }
    return build_worker_health(
        **{
            "cycle": cycle,
            "duplicate_claim_refused": True,
            "expired_lease_reclaimed": True,
            "retry_bounded": True,
            "activation_allowlist_count": 0,
            **overrides,
        }
    )


def test_the_worker_runtime_is_ready():
    health = _health()
    assert health["worker_runtime_ready"] is True
    assert health["blockers"] == []
    assert worker_health_invariant_failures(health) == []


def test_worker_ready_does_not_mean_source_monitoring_live():
    health = _health()
    assert health["worker_runtime_ready"] is True
    assert health["source_monitoring_live"] is False
    assert "polling" in health["worker_ready_is_not_monitoring_live"]


def test_a_health_claiming_monitoring_live_is_refused():
    assert "source_monitoring_live_became_true" in (
        worker_health_invariant_failures({**_health(), "source_monitoring_live": True})
    )


def test_a_completed_job_is_refused_because_no_handler_exists():
    assert "a_job_completed_but_no_handler_exists" in (
        worker_health_invariant_failures({**_health(), "jobs_completed": 1})
    )


def test_retryable_jobs_with_an_empty_allowlist_are_refused():
    assert "retryable_jobs_with_an_empty_allowlist" in (
        worker_health_invariant_failures({**_health(), "jobs_retryable": 2})
    )


@pytest.mark.parametrize(
    "condition", ["claim_is_atomic", "expired_lease_reclaimed", "retries_are_bounded"]
)
def test_each_health_condition_can_block_the_lane(condition):
    mapping = {
        "claim_is_atomic": "duplicate_claim_refused",
        "expired_lease_reclaimed": "expired_lease_reclaimed",
        "retries_are_bounded": "retry_bounded",
    }
    health = _health(**{mapping[condition]: False})
    assert health["worker_runtime_ready"] is False
    assert f"condition_not_met:{condition}" in health["blockers"]


def test_a_health_without_a_cycle_is_not_ready():
    health = build_worker_health(cycle=None)
    assert health["worker_runtime_ready"] is False


def test_the_worker_process_is_unknown_not_assumed():
    assert _health()["worker_process_active"] is None


@pytest.mark.parametrize("condition", CONDITIONS)
def test_every_health_condition_has_declared_evidence(condition):
    assert _health()["condition_evidence"].get(condition)


# ------------------------------------------- no network, no credentials


@pytest.mark.parametrize("module", GATE_157_MODULES)
def test_no_worker_module_imports_the_network(module):
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


def test_no_credentials_are_required(connection):
    cycle = run_worker_cycle(
        connection=connection, organization_id=DEMO, worker_id="w", jobs=[], now=T0
    )
    assert cycle["api_key_required"] is False
    assert _health()["api_key_required"] is False


def test_the_worker_script_takes_no_secret_arguments():
    body = WORKER_SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("--token", "--api-key", "--password", "--secret"):
        assert forbidden not in body


def test_the_worker_script_has_no_unbounded_loop():
    body = WORKER_SCRIPT.read_text(encoding="utf-8")
    assert "while True" not in body
    assert "max-cycles" in body


# ---------------------------------------------------------- 157H the routes


ROUTES = ("health", "jobs", "leases")


@pytest.mark.parametrize("path", ROUTES)
def test_every_get_route_requires_a_session(client, path):
    assert client.get(f"/v1/nf/demo/orgs/{DEMO}/source-worker/{path}").status_code in (
        401,
        403,
    )


def test_the_dry_run_route_requires_a_session(client):
    assert client.post(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/dry-run", json={}
    ).status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_a_forged_header_cannot_override_the_org(client, path):
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/{path}",
        headers=soh.forged_header_only(DEMO),
    ).status_code in (401, 403)


@pytest.mark.parametrize("path", ROUTES)
def test_another_organization_is_refused(client, path):
    soh.ensure_org(OTHER, "demo")
    assert client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/{path}",
        headers=soh.session_headers(OTHER),
    ).status_code in (403, 404)


def test_the_dry_run_route_claims_no_lease(client):
    """A route taking a claim would hold it until expiry."""
    soh.ensure_org(DEMO, "demo")
    body = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/dry-run",
        headers=soh.session_headers(DEMO),
        json={"now": T0},
    ).json()
    assert body["ran"] is False
    assert "no_connection_supplied" in body["why_not"]
    assert body["leases_taken"] == 0
    assert body["rows_written"] == 0
    assert body["source_monitoring_live"] is False


def test_the_health_route_reports_not_live(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["source_monitoring_live"] is False
    assert body["measured_by_the_verifier"]


def test_the_jobs_route_reports_every_job_refusing(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/jobs",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["jobs_available"] > 0
    assert body["jobs_claimable"] == 0
    assert body["jobs_would_refuse"] == body["jobs_available"]


def test_the_leases_route_sweeps_nothing(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/source-worker/leases",
        headers=soh.session_headers(DEMO),
    ).json()
    assert "nothing_here_sweeps_a_lease" in body
    assert body["source_monitoring_live"] is False


def test_no_route_response_carries_an_address_a_subject_or_the_real_org(client):
    soh.ensure_org(DEMO, "demo")
    headers = soh.session_headers(DEMO)
    for path in ROUTES:
        body = client.get(
            f"/v1/nf/demo/orgs/{DEMO}/source-worker/{path}", headers=headers
        ).text
        assert not ADDRESS_SHAPE.search(body), path
        assert not SUBJECT_SHAPE.search(body), path
        assert REAL not in body, path


# -------------------------------------------------------- 157K the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = art.write_worker_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.worker_artifact_invariant_failures(result) == []
    assert result["file_count"] == 9


def test_the_artifacts_are_deterministic():
    assert art.build_worker_artifacts() == art.build_worker_artifacts()


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_worker_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_no_artifact_carries_an_address_a_subject_or_the_real_org():
    for name, body in art.build_worker_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        assert REAL not in body, name


def test_no_artifact_claims_monitoring_is_live():
    blob = "\n".join(art.build_worker_artifacts().values()).lower()
    assert '"source_monitoring_live": true' not in blob


def test_the_survey_explains_why_a_new_table_was_required():
    survey = json.loads(art.build_worker_artifacts()[art.SURVEY_FILE])
    why = survey["why_a_new_table_was_required"]
    assert why["closest"] == "nf_source_check_runs"
    assert "a check ran when nothing did" in why["why_it_does_not_fit"]
    assert why["migration"] == "0043"


def test_the_retry_artifact_records_that_only_one_class_retries():
    policy = json.loads(art.build_worker_artifacts()[art.RETRY_FILE])
    assert policy["only_one_class_retries"] is True
    assert policy["backoff"]["jitter"] is False


def test_the_blockers_artifact_refuses_the_collection_claim():
    body = art.build_worker_artifacts()[art.BLOCKERS_FILE]
    assert "NativeForge has a worker collecting grant data" in body
    assert "Nothing is collected" in body


# -------------------------------------------------------- 157I the verifier


def test_the_verifier_exists_and_is_executable():
    assert VERIFIER_SCRIPT.exists()
    assert VERIFIER_SCRIPT.stat().st_mode & 0o111


def test_the_verifier_cleans_up_by_organization_not_by_a_job_id_prefix():
    """The defect this gate found in itself.

    `job_id` is Gate 99B's sha256 digest. A LIKE over a source_id prefix
    matched nothing the verifier created, so 277 rows survived a run that
    reported a clean exit.
    """
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "WHERE organization_id = :o" in body
    assert "job_id LIKE '{PREFIX}%'" not in body
    assert "cleanup_had_something_to_clean" in body


def test_the_verifier_proves_the_retry_branch_is_reachable():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "transient_failure_is_retried" in body
    assert "permitting_branch_reachable_and_still_refuses" in body


def test_the_verifier_states_it_does_not_make_monitoring_live():
    body = VERIFIER_SCRIPT.read_text(encoding="utf-8")
    assert "DOES NOT MAKE SOURCE MONITORING LIVE" in body
    assert "source_monitoring_live=false" in body


def test_this_gates_verifier_is_in_the_registry():
    entry = next(e for e in VERIFIERS if e["verifier"] == "source_worker_runtime")
    assert entry["gate"] == "157"
    assert entry["lane"] == "worker_runtime_ready"
    assert "source_scheduler_runtime" in entry["depends_on"]


def test_the_migration_stores_no_body_no_credential_no_customer_data():
    body = (
        REPO_ROOT / "alembic/versions/0043_source_collection_job_leases.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "response_body",
        "raw_payload_ref",
        "api_key",
        "access_token",
        "recipient_email",
    ):
        assert f'sa.Column("{forbidden}"' not in body, forbidden
    # The three constants the database refuses to set true.
    assert "ck_nf_source_collection_job_leases_no_collector" in body
    assert "ck_nf_source_collection_job_leases_no_fetch" in body
    assert "ck_nf_source_collection_job_leases_no_payload" in body


def test_the_attempt_budget_is_bounded_in_the_schema():
    body = (
        REPO_ROOT / "alembic/versions/0043_source_collection_job_leases.py"
    ).read_text(encoding="utf-8")
    assert "attempt_count <= max_attempts" in body
    assert DEFAULT_MAX_ATTEMPTS == 3
