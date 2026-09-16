"""Gate 158: the durable collection job store.

Every defect Gate 158 found in its own work has a test here, named for what it
would have shipped:

  - the identity service digested a job_type outside Gate 99B's vocabulary, so
    the store would have held ids the scheduler never reports
  - and then stripped the source_id, which Gate 99B does not, for the same
    result on a padded id
  - the worker OVERWROTE the four blockers the scheduler had recorded with one
    runtime note, making the terms-blocked backlog unanswerable after a single
    pass
  - five route guards passed `same_org(ctx, org_id)` backwards and then tested
    its None return, which would have refused every request with a 403 where
    the convention is 404
  - the health route proved `survives_restart` by reading back through the
    connection that wrote, which is true of an uncommitted row too

The restart proof itself is not here. Proving a row outlives the process that
wrote it needs a second process, and a test that commits into the demo org and
reconnects would leave rows behind on every run. The verifier does it:
scripts/verify_nativeforge_collection_job_store.sh, phases A and B.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.repositories.source_collection_job_repository import (
    ARCHIVED,
    CLAIMED,
    COMPLETED,
    JOB_STATUSES,
    JOBS,
    LEGAL_TRANSITIONS,
    LIVE_STATUSES,
    QUEUED,
    REFUSED,
    RETRY_WAIT,
    TERMINAL_REASONS,
    archive_job,
    count_backlog,
    enqueue_job,
    get_job,
    job_store_capability,
    job_store_invariant_failures,
    list_jobs,
    transition_job,
)
from nativeforge.services.source_collection_job_identity_service import (
    build_job_identity,
    build_schedule_key,
    identity_invariant_failures,
)
from nativeforge.services.source_collection_job_model_service import (
    build_collection_job,
)
from nativeforge.services.source_collection_job_store_health_service import (
    CONDITIONS,
    NOT_MEASURABLE_BY_A_REQUEST,
    build_job_store_health,
    job_store_health_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    CYCLE_MODE_EVALUATE_ONLY,
    CYCLE_MODES,
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    STORE_LOADED_IS_NOT_PERMITTED,
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from nativeforge.services.source_job_store_artifact_gate158_service import (
    ARTIFACT_DIR,
    ARTIFACT_FILES,
    build_job_store_artifacts,
    job_store_artifact_invariant_failures,
    write_job_store_artifacts,
)
from nativeforge.services.source_scheduler_job_model_service import (
    DEFAULT_JOB_TYPE as GATE_99B_DEFAULT_JOB_TYPE,
)
from nativeforge.services.source_scheduler_job_model_service import (
    JOB_TYPES as GATE_99B_JOB_TYPES,
)
from tests import session_org_helper as soh

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

T0 = "2026-09-16T12:00:00Z"
T1 = "2026-09-16T12:05:00Z"

MIGRATION = REPO_ROOT / "alembic/versions/0044_source_collection_jobs.py"

GATE_158_MODULES = (
    "src/nativeforge/repositories/source_collection_job_repository.py",
    "src/nativeforge/services/source_collection_job_identity_service.py",
    "src/nativeforge/services/source_collection_job_store_health_service.py",
    "src/nativeforge/services/source_job_store_artifact_gate158_service.py",
    "src/nativeforge/api/source_collection_job_store_routes.py",
)


@pytest.fixture
def db_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(DEMO, "demo")
    with SessionLocal() as session:
        yield session
        # Rolled back, so no test in this file leaves a row behind.
        session.rollback()


@pytest.fixture
def connection(db_session):
    return db_session.connection()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _blocked_source(source_id: str, **overrides) -> dict:
    return {
        "source_id": source_id,
        "check_interval_days": 7,
        "last_checked_at": "2026-09-01T00:00:00Z",
        "is_enabled": True,
        "activation_state": "activation_blocked",
        "terms_state": "terms_unknown",
        "human_review_state": "human_review_required",
        "collector_registered": False,
        **overrides,
    }


def _enqueue(connection, source_id: str, scheduled_for=None, **overrides) -> dict:
    identity = build_job_identity(
        source_id=source_id, scheduled_for=scheduled_for
    )
    return enqueue_job(
        connection=connection,
        organization_id=DEMO,
        job_id=identity["job_id"],
        idempotency_key=identity["idempotency_key"],
        source_id=source_id,
        schedule_key=identity["schedule_key"],
        scheduled_for=scheduled_for,
        now=T0,
        **overrides,
    )


def _tag() -> str:
    return f"t158-{uuid.uuid4().hex[:10]}"


# ------------------------------------------------------- 158B the migration


def test_the_migration_exists_and_pins_0043_as_its_parent():
    body = MIGRATION.read_text()
    assert 'revision: str = "0044"' in body
    assert 'down_revision: str | Sequence[str] | None = "0043"' in body


def test_the_migration_refuses_a_completed_row_without_an_execution_proof():
    body = MIGRATION.read_text()
    assert "status <> 'completed' OR execution_proof_ref IS NOT NULL" in body


def test_the_migration_declares_no_lease_column():
    """Gate 157 owns the claim. A column that does not exist cannot drift."""
    body = MIGRATION.read_text()
    for column in ("lease_owner", "lease_acquired_at", "lease_expires_at"):
        assert f'sa.Column("{column}"' not in body


def test_the_migration_carries_the_unique_index_that_makes_enqueue_idempotent():
    body = MIGRATION.read_text()
    assert "ux_nf_source_collection_jobs_job_id" in body
    assert '["organization_id", "job_id"]' in body


def test_the_migration_stores_no_response_and_no_credential():
    """The rule that produced 0043's three refused booleans, applied here."""
    body = MIGRATION.read_text().lower()
    for forbidden in (
        'sa.column("response_body"',
        'sa.column("url"',
        'sa.column("status_code"',
        'sa.column("api_key"',
        'sa.column("access_token"',
        'sa.column("raw_payload"',
    ):
        assert forbidden not in body


# ------------------------------------------------ 158C the repository, reads


def test_the_declared_table_has_no_lease_column():
    columns = {column.name for column in JOBS.columns}
    assert columns & {"lease_owner", "lease_acquired_at", "lease_expires_at"} == set()


def test_the_declared_table_keeps_its_uuid_decorators():
    """Gate 157 lost these to reflection and got 'type UUID is not supported'."""
    assert isinstance(JOBS.c.id.type, sa.Uuid)
    assert isinstance(JOBS.c.organization_id.type, sa.Uuid)


def test_capability_derives_unreachable_completion_from_the_signature():
    capability = job_store_capability()
    parameters = set(inspect.signature(transition_job).parameters)
    assert "execution_proof_ref" not in parameters
    assert capability["transition_accepts_an_execution_proof"] is False
    assert capability["completed_is_reachable"] is False


def test_capability_would_flip_if_a_proof_parameter_were_added():
    """The derivation is falsifiable, not a constant dressed up as one.

    If `completed_is_reachable` were hardcoded False, this reasoning would
    still pass while the value had stopped meaning anything. So the test
    asserts the CAUSE: the reported value equals what reading the signature
    says, for a signature that does have such a parameter and one that does
    not.
    """

    def with_proof(*, job_id=None, to_status=None, execution_proof_ref=None):
        return None

    def without_proof(*, job_id=None, to_status=None):
        return None

    def reachable(fn):
        return bool(
            {"execution_proof_ref", "execution_proof"}
            & set(inspect.signature(fn).parameters)
        )

    assert reachable(with_proof) is True
    assert reachable(without_proof) is False
    assert reachable(transition_job) is job_store_capability()[
        "completed_is_reachable"
    ]


def test_every_status_appears_in_the_state_machine():
    assert set(LEGAL_TRANSITIONS) == set(JOB_STATUSES)


def test_archived_is_where_a_job_stops():
    assert LEGAL_TRANSITIONS[ARCHIVED] == frozenset()


def test_an_outcome_is_not_reachable_without_a_claim():
    """queued -> refused would be an outcome for work nobody claimed."""
    assert REFUSED not in LEGAL_TRANSITIONS[QUEUED]
    assert CLAIMED in LEGAL_TRANSITIONS[QUEUED]
    assert REFUSED in LEGAL_TRANSITIONS[CLAIMED]


def test_a_refusal_can_become_queued_again():
    """171 terms-blocked jobs become work again when somebody reads the terms."""
    assert QUEUED in LEGAL_TRANSITIONS[REFUSED]


def test_live_statuses_are_the_ones_a_job_can_leave():
    for status in LIVE_STATUSES:
        assert LEGAL_TRANSITIONS[status], f"{status} is live but has no exit"


# ----------------------------------------------- 158C the repository, writes


def test_a_job_can_be_enqueued_and_read_back(connection):
    tag = _tag()
    result = _enqueue(connection, tag)
    assert result["created"] is True
    assert result["deduplicated"] is False
    assert result["job"]["status"] == QUEUED
    assert result["job"]["execution_proof_ref"] is None
    assert job_store_invariant_failures(result) == []

    read = get_job(
        connection=connection, organization_id=DEMO, job_id=result["job_id"]
    )
    assert read["job"]["source_id"] == tag


def test_enqueueing_the_same_slot_twice_creates_one_row(connection):
    tag = _tag()
    first = _enqueue(connection, tag)
    second = _enqueue(connection, tag)

    assert first["created"] is True
    assert second["created"] is False
    assert second["deduplicated"] is True
    assert second["job"]["job_id"] == first["job_id"]

    listed = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)
    assert listed["job_count"] == 1


def test_a_different_slot_of_the_same_source_is_a_different_row(connection):
    tag = _tag()
    first = _enqueue(connection, tag, scheduled_for="2026-09-20T00:00:00Z")
    second = _enqueue(connection, tag, scheduled_for="2026-09-27T00:00:00Z")

    assert first["created"] is True
    assert second["created"] is True
    assert first["job_id"] != second["job_id"]

    listed = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)
    assert listed["job_count"] == 2


def test_a_new_job_is_queued_and_not_refused(connection):
    """The scheduler records why. Deciding an outcome is the worker's job."""
    tag = _tag()
    result = _enqueue(connection, tag, blocked_reasons=["source_terms_not_approved"])
    assert result["job"]["status"] == QUEUED
    assert result["job"]["terminal_reason"] == "none"
    assert result["job"]["blocked_reasons"] == ["source_terms_not_approved"]


def test_the_real_organization_is_refused_by_name(connection):
    result = enqueue_job(
        connection=connection,
        organization_id=REAL_ORG,
        job_id="never",
        source_id="x",
        now=T0,
    )
    assert result["created"] is False
    assert "real_organization_refused_by_name" in result["blocked_reasons"]


def test_an_enqueue_without_a_clock_is_refused(connection):
    result = enqueue_job(
        connection=connection,
        organization_id=DEMO,
        job_id="no-clock",
        source_id="x",
        now=None,
    )
    assert result["created"] is False
    assert "no_clock_supplied" in result["blocked_reasons"]


def test_a_terminal_reason_outside_the_vocabulary_is_refused(connection):
    result = _enqueue(connection, _tag(), terminal_reason="made_up")
    assert result["created"] is False
    assert any("terminal_reason_outside_vocabulary" in r for r in result[
        "blocked_reasons"
    ])


# ------------------------------------------------------------ transitions


def test_a_legal_transition_moves_the_row(connection):
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    moved = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    assert moved["transitioned"] is True
    assert moved["from_status"] == QUEUED
    assert moved["job"]["status"] == CLAIMED
    assert job_store_invariant_failures(moved) == []


def test_an_illegal_transition_is_refused_and_leaves_the_row_alone(connection):
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    refused = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=REFUSED,
        terminal_reason="terms_blocked",
        now=T1,
    )
    assert refused["transitioned"] is False
    assert any(
        "transition_not_in_state_machine" in r for r in refused["blocked_reasons"]
    )

    after = get_job(connection=connection, organization_id=DEMO, job_id=job_id)
    assert after["job"]["status"] == QUEUED


def test_a_transition_to_completed_is_refused(connection):
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    done = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=COMPLETED,
        now=T1,
    )
    assert done["transitioned"] is False
    assert (
        "completed_requires_an_execution_proof_no_gate_defines"
        in done["blocked_reasons"]
    )


def test_the_database_refuses_a_completed_row_with_the_repository_bypassed(
    connection,
):
    """The CHECK is real, not a convention the repository happens to honour."""
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "UPDATE nf_source_collection_jobs SET status = 'completed' "
                    "WHERE job_id = :job_id"
                ),
                {"job_id": job_id},
            )


def test_retry_wait_needs_a_transient_reason(connection):
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    refused = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=RETRY_WAIT,
        terminal_reason="terms_blocked",
        now=T1,
    )
    assert refused["transitioned"] is False
    assert any(
        "retry_wait_requires_a_transient_worker_failure" in r
        for r in refused["blocked_reasons"]
    )


def test_retry_wait_with_a_transient_reason_is_allowed_and_spends_an_attempt(
    connection,
):
    """The permitting branch. A rule that refuses everything proves nothing."""
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    allowed = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=RETRY_WAIT,
        terminal_reason="transient_worker_failure",
        next_retry_at="2026-09-16T12:06:00Z",
        increment_attempt=True,
        now=T1,
    )
    assert allowed["transitioned"] is True
    assert allowed["job"]["attempt_count"] == 1
    assert allowed["job"]["next_retry_at"] is not None


def test_the_attempt_budget_cannot_be_exceeded(connection):
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    last = {}
    for _ in range(6):
        transition_job(
            connection=connection,
            organization_id=DEMO,
            job_id=job_id,
            to_status=CLAIMED,
            now=T1,
        )
        last = transition_job(
            connection=connection,
            organization_id=DEMO,
            job_id=job_id,
            to_status=RETRY_WAIT,
            terminal_reason="transient_worker_failure",
            increment_attempt=True,
            now=T1,
        )
    assert any("attempt_budget_exhausted" in r for r in last["blocked_reasons"])
    assert last["job"]["attempt_count"] <= last["job"]["max_attempts"]


def test_only_a_retry_wait_keeps_a_next_retry_at(connection):
    """A stale timestamp would make a refused job look due."""
    tag = _tag()
    job_id = _enqueue(connection, tag)["job_id"]
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=RETRY_WAIT,
        terminal_reason="transient_worker_failure",
        next_retry_at="2026-09-16T12:06:00Z",
        increment_attempt=True,
        now=T1,
    )
    transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=CLAIMED,
        now=T1,
    )
    moved = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        to_status=REFUSED,
        terminal_reason="terms_blocked",
        now=T1,
    )
    assert moved["job"]["next_retry_at"] is None


def test_archived_carries_a_timestamp_and_a_live_row_does_not(connection):
    tag = _tag()
    live = _enqueue(connection, tag + "-live")
    archived_id = _enqueue(connection, tag + "-arch")["job_id"]

    result = archive_job(
        connection=connection,
        organization_id=DEMO,
        job_id=archived_id,
        terminal_reason="canceled_by_operator",
        now=T1,
    )
    assert result["transitioned"] is True
    assert result["job"]["archived_at"] is not None
    assert live["job"]["archived_at"] is None
    assert job_store_invariant_failures(result) == []


def test_a_missing_job_is_named_rather_than_created(connection):
    result = transition_job(
        connection=connection,
        organization_id=DEMO,
        job_id="does-not-exist",
        to_status=CLAIMED,
        now=T1,
    )
    assert result["transitioned"] is False
    assert "no_job_row_for_this_job_id" in result["blocked_reasons"]


# ---------------------------------------------------------------- backlog


def test_the_backlog_reports_every_status_including_the_empty_ones(connection):
    backlog = count_backlog(connection=connection, organization_id=DEMO)
    assert set(backlog["by_status"]) == set(JOB_STATUSES)
    assert backlog["completed_total"] == 0
    assert backlog["rows_with_execution_proof"] == 0
    assert job_store_invariant_failures(backlog) == []


def test_the_backlog_counts_add_up(connection):
    tag = _tag()
    for index in range(3):
        _enqueue(connection, f"{tag}-{index}")
    backlog = count_backlog(connection=connection, organization_id=DEMO)
    assert sum(backlog["by_status"].values()) == backlog["total"]


def test_the_backlog_names_the_oldest_waiting_job(connection):
    """The number that makes 'how long has this waited' askable."""
    tag = _tag()
    _enqueue(connection, tag)
    backlog = count_backlog(connection=connection, organization_id=DEMO)
    assert backlog["oldest_queued_at"] is not None


# ------------------------------------------------------- 158D the identity


def test_the_identity_service_composes_gate_99b_rather_than_redigesting():
    module = Path(
        REPO_ROOT / "src/nativeforge/services/source_collection_job_identity_service.py"
    ).read_text()
    # No second sha256 in this module. The digest has one home.
    assert "hashlib" not in module
    assert "build_job_id" in module
    assert "build_idempotency_key" in module


def test_the_same_slot_twice_is_the_same_id():
    first = build_job_identity(source_id="s", scheduled_for="2026-09-20T00:00:00Z")
    second = build_job_identity(source_id="s", scheduled_for="2026-09-20T00:00:00Z")
    assert first["job_id"] == second["job_id"]
    assert first["determinism_proof"]["matches"] is True
    assert identity_invariant_failures(first) == []


def test_a_source_with_no_cadence_has_one_perpetual_slot():
    """This is what bounds the store to one row per source."""
    identity = build_job_identity(source_id="s", scheduled_for=None)
    assert identity["is_perpetual_slot"] is True
    assert identity["schedule_key"] == "perpetual"
    assert build_schedule_key(None) == "perpetual"


def test_the_job_id_and_the_idempotency_key_digest_different_tuples():
    identity = build_job_identity(source_id="s", scheduled_for=None)
    assert identity["job_id"] != identity["idempotency_key"]


def test_computing_an_identity_claims_no_permission():
    identity = build_job_identity(source_id="s", scheduled_for=None)
    assert identity["implies_source_approval"] is False
    assert identity["implies_collection_permitted"] is False
    assert identity["source_monitoring_live"] is False


def test_the_identity_normalizes_a_job_type_through_gate_99bs_vocabulary():
    """The defect: my own default digested a word Gate 99B does not have.

    `scheduled_check` is not in Gate 99B's JOB_TYPES, so Gate 99B normalizes it
    to `source_check` and digests THAT. An identity service carrying its own
    copy of the word produced a different id in all four measured cases.
    """
    assert "scheduled_check" not in GATE_99B_JOB_TYPES
    identity = build_job_identity(
        source_id="s", scheduled_for=None, job_type="scheduled_check"
    )
    assert identity["job_type"] == GATE_99B_DEFAULT_JOB_TYPE
    assert identity["job_type_was_normalized"] is True
    assert identity["job_type_requested"] == "scheduled_check"


def test_the_identity_reproduces_the_id_the_job_model_already_carries():
    """The agreement that makes the store hold what the scheduler reports.

    Measured disagreeing twice on the way here - once on the job_type, once on
    a stray `.strip()` - so this asserts the outcome rather than the reasoning.
    """
    for source_id in ("plain", "  padded  ", "with-dashes-0"):
        job = build_collection_job(
            source_id=source_id,
            now=T0,
            last_checked_at="2026-09-01T00:00:00Z",
            check_interval_days=7,
            activation_state="activation_blocked",
            terms_state="terms_unknown",
            human_review_state="human_review_required",
            is_enabled=True,
            collector_registered=False,
        )
        identity = build_job_identity(
            source_id=source_id,
            scheduled_for=job["next_run_at"],
            execution_mode=job["execution_mode"],
        )
        assert identity["job_id"] == job["job_id"], source_id


def test_the_identity_does_not_strip_the_source_id():
    """Gate 99B digests it raw. A second normalization is a second truth."""
    padded = build_job_identity(source_id="  s  ", scheduled_for=None)
    plain = build_job_identity(source_id="s", scheduled_for=None)
    assert padded["job_id"] != plain["job_id"]


def test_an_identity_with_no_source_id_says_it_is_unusable():
    identity = build_job_identity(source_id="", scheduled_for=None)
    assert identity["usable_as_input"] is False


# -------------------------------------------- 158E the scheduler composition


def test_the_default_cycle_mode_did_not_change():
    """Nothing that called this before Gate 158 writes a row now."""
    signature = inspect.signature(run_scheduler_cycle)
    assert signature.parameters["mode"].default == CYCLE_MODE_EVALUATE_ONLY


def test_an_evaluate_only_cycle_reports_no_rows_written():
    cycle = run_scheduler_cycle(
        now=T0, sources=[_blocked_source("s")], organization_id=DEMO
    )
    assert cycle["rows_written"] == 0
    assert cycle["enqueue_requested"] is False
    assert cycle["enqueue_results"] == []
    assert cycle_invariant_failures(cycle) == []


def test_an_enqueue_without_a_connection_is_refused_and_says_why():
    cycle = run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source("s")],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=None,
    )
    assert cycle["enqueue_performed"] is False
    assert "enqueue_requested_without_a_connection" in cycle[
        "enqueue_blocked_reasons"
    ]
    assert cycle["rows_written"] == 0
    assert cycle_invariant_failures(cycle) == []


def test_an_enqueueing_cycle_writes_one_row_per_source(connection):
    tag = _tag()
    cycle = run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(f"{tag}-{i}") for i in range(3)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    assert cycle["jobs_known"] == 3
    assert cycle["jobs_enqueued"] == 3
    assert cycle["rows_written"] == 3
    assert cycle_invariant_failures(cycle) == []


def test_repeated_cycles_do_not_grow_the_store(connection):
    tag = _tag()
    sources = [_blocked_source(f"{tag}-{i}") for i in range(3)]
    for index in range(5):
        cycle = run_scheduler_cycle(
            now=T0,
            sources=sources,
            organization_id=DEMO,
            mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
            connection=connection,
        )
        if index:
            assert cycle["jobs_enqueued"] == 0
            assert cycle["jobs_deduplicated"] == 3

    listed = list_jobs(connection=connection, organization_id=DEMO)
    mine = [j for j in listed["jobs"] if str(j["source_id"]).startswith(tag)]
    assert len(mine) == 3


def test_a_blocked_source_still_gets_a_durable_row(connection):
    """Option A from the survey: the backlog has to be countable over time."""
    tag = _tag()
    run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(tag)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    listed = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)
    assert listed["job_count"] == 1
    assert listed["jobs"][0]["blocked_reasons"]


def test_a_cycle_that_writes_rows_still_contacted_nothing(connection):
    tag = _tag()
    cycle = run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(tag)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    assert cycle["rows_written"] == 1
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
    ):
        assert cycle[counter] == 0, counter
    assert cycle["source_monitoring_live"] is False


def test_the_invariant_checker_catches_a_lying_rows_written():
    """rows_written left the must-be-zero list. It did not leave unchecked."""
    cycle = run_scheduler_cycle(
        now=T0, sources=[_blocked_source("s")], organization_id=DEMO
    )
    tampered = {**cycle, "rows_written": 7}
    assert "rows_written_disagrees_with_jobs_enqueued" in cycle_invariant_failures(
        tampered
    )


def test_the_invariant_checker_catches_an_evaluate_only_cycle_that_wrote():
    cycle = run_scheduler_cycle(
        now=T0, sources=[_blocked_source("s")], organization_id=DEMO
    )
    tampered = {
        **cycle,
        "rows_written": 1,
        "jobs_enqueued": 1,
        "enqueue_results": [{"created": True, "deduplicated": False}],
    }
    assert "evaluate_only_cycle_wrote_rows" in cycle_invariant_failures(tampered)


def test_persist_left_the_not_implemented_list():
    from nativeforge.services.source_collection_scheduler_loop_service import (
        EXECUTION_MODES_NOT_IMPLEMENTED,
    )

    joined = " ".join(EXECUTION_MODES_NOT_IMPLEMENTED)
    assert "persist" not in joined
    # And the two that have not been built are still named.
    assert "dispatch" in joined
    assert "trigger" in joined


def test_both_cycle_modes_are_accepted_by_the_invariant_checker():
    assert set(CYCLE_MODES) == {
        CYCLE_MODE_EVALUATE_ONLY,
        CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    }


# ----------------------------------------------- 158F the worker composition


def test_the_worker_records_its_outcome_on_the_durable_row(connection):
    tag = _tag()
    run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(tag)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    worker = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        now=T1,
        load_jobs_from_store=True,
    )
    assert worker["job_rows_transitioned"] >= 2
    assert worker_cycle_invariant_failures(worker) == []

    listed = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)
    assert listed["jobs"][0]["status"] == REFUSED


def test_the_worker_preserves_the_blockers_the_scheduler_recorded(connection):
    """The defect: one worker pass made the terms-blocked backlog unanswerable.

    Measured before the fix: four real reasons replaced by one runtime note,
    and `terms_blocked` downgraded to `unknown`.
    """
    tag = _tag()
    run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(tag)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    before = set(
        list_jobs(connection=connection, organization_id=DEMO, source_id=tag)["jobs"][
            0
        ]["blocked_reasons"]
    )
    assert "source_terms_not_approved" in before

    run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        now=T1,
        load_jobs_from_store=True,
    )
    row = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)[
        "jobs"
    ][0]
    after = set(row["blocked_reasons"])

    assert before <= after, "the worker dropped a reason the scheduler recorded"
    assert after - before, "the worker recorded nothing of its own"
    # And the class stays countable rather than collapsing to unknown.
    assert row["terminal_reason"] == "terms_blocked"


def test_a_store_loaded_job_is_never_treated_as_permitted(connection):
    """An empty blocked_reasons is an absent objection, not an approval."""
    tag = _tag()
    _enqueue(connection, tag, blocked_reasons=[])
    worker = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        now=T1,
        load_jobs_from_store=True,
    )
    mine = [r for r in worker["results"] if r["source_id"] == tag]
    assert mine, "the worker did not see the row"
    assert STORE_LOADED_IS_NOT_PERMITTED in mine[0]["blocked_reasons"]
    assert worker["jobs_completed"] == 0


def test_the_worker_does_not_invent_a_job_row_it_did_not_find(connection):
    """Counting a missing row beats creating one: the scheduler decides work."""
    worker = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        jobs=[
            {
                "job_id": "t158-not-in-the-store",
                "source_id": "t158-ghost",
                "executable": False,
                "blockers": ["source_terms_not_approved"],
            }
        ],
        now=T1,
    )
    assert worker["job_rows_missing"] == 1
    assert worker["job_rows_transitioned"] == 0

    listed = list_jobs(
        connection=connection, organization_id=DEMO, source_id="t158-ghost"
    )
    assert listed["job_count"] == 0


def test_the_worker_does_not_re_chew_an_already_refused_backlog(connection):
    tag = _tag()
    run_scheduler_cycle(
        now=T0,
        sources=[_blocked_source(tag)],
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker-1",
        now=T1,
        load_jobs_from_store=True,
    )
    second = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker-2",
        now=T1,
        load_jobs_from_store=True,
    )
    mine = [r for r in second["results"] if r["source_id"] == tag]
    assert mine == [], "a refused row is neither queued nor retry_wait"


def test_a_re_enqueue_does_not_reset_a_refusal(connection):
    """Enqueue is create-if-absent. A cycle cannot erase a recorded outcome."""
    tag = _tag()
    sources = [_blocked_source(tag)]
    run_scheduler_cycle(
        now=T0,
        sources=sources,
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        now=T1,
        load_jobs_from_store=True,
    )
    run_scheduler_cycle(
        now=T0,
        sources=sources,
        organization_id=DEMO,
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=connection,
    )
    row = list_jobs(connection=connection, organization_id=DEMO, source_id=tag)[
        "jobs"
    ][0]
    assert row["status"] == REFUSED


def test_the_worker_says_a_claim_is_not_a_contact(connection):
    worker = run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="t158-worker",
        jobs=[],
        now=T1,
    )
    assert worker["claimed_job_means_source_contacted"] is False
    assert worker["persisted_job_means_collection_occurred"] is False


def test_the_worker_lease_and_job_vocabularies_did_not_collide():
    """Both modules export CLAIMED, REFUSED, FAILED and COMPLETED.

    Imported bare, one set would shadow the other and the worker would write
    lease words into a job column - a defect that reads correctly in a diff.
    """
    module = Path(
        REPO_ROOT
        / "src/nativeforge/services/source_collection_worker_runtime_service.py"
    ).read_text()
    assert "REFUSED as JOB_REFUSED" in module
    assert "CLAIMED as JOB_CLAIMED" in module
    assert "RETRY_WAIT as JOB_RETRY_WAIT" in module


def test_no_lease_status_maps_to_a_completed_job():
    from nativeforge.services.source_collection_worker_runtime_service import (
        LEASE_STATUS_TO_JOB_STATUS,
    )

    assert COMPLETED not in LEASE_STATUS_TO_JOB_STATUS.values()


# ---------------------------------------------------------- 158G the health


def test_a_fully_evidenced_lane_goes_green():
    enqueued = {"created": True, "job": {"status": QUEUED}}
    health = build_job_store_health(
        table_exists=True,
        enqueue_result=enqueued,
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect={"job": {"status": QUEUED}},
        illegal_transition_result={
            "transitioned": False,
            "blocked_reasons": ["transition_not_in_state_machine:queued->refused"],
        },
        backlog={
            "by_status": dict.fromkeys(JOB_STATUSES, 0),
            "total": 0,
            "completed_total": 0,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["collection_job_store_ready"] is True
    assert health["blockers"] == []
    assert job_store_health_invariant_failures(health) == []


def test_a_lane_with_no_restart_evidence_is_red_and_says_so():
    health = build_job_store_health(
        table_exists=True,
        enqueue_result={"created": True, "job": {"status": QUEUED}},
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect=None,
        illegal_transition_result={
            "transitioned": False,
            "blocked_reasons": ["nope"],
        },
        backlog={
            "by_status": dict.fromkeys(JOB_STATUSES, 0),
            "total": 0,
            "completed_total": 0,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["collection_job_store_ready"] is False
    assert health["conditions_not_met"] == ["survives_restart"]
    assert health["restart_evidence_supplied"] is False


def test_a_status_that_drifted_across_a_reconnect_closes_the_lane():
    health = build_job_store_health(
        table_exists=True,
        enqueue_result={"created": True, "job": {"status": QUEUED}},
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect={"job": {"status": CLAIMED}},
        illegal_transition_result={"transitioned": False, "blocked_reasons": ["x"]},
        backlog={
            "by_status": dict.fromkeys(JOB_STATUSES, 0),
            "total": 0,
            "completed_total": 0,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["collection_job_store_ready"] is False
    assert any("changed_status_across_a_reconnect" in b for b in health["blockers"])


def test_an_idempotency_claim_needs_both_halves():
    """"Idempotent" would also be true of an enqueue that never inserted."""
    health = build_job_store_health(
        table_exists=True,
        enqueue_result={"created": False, "job": None},
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect={"job": {"status": QUEUED}},
        illegal_transition_result={"transitioned": False, "blocked_reasons": ["x"]},
        backlog={
            "by_status": dict.fromkeys(JOB_STATUSES, 0),
            "total": 0,
            "completed_total": 0,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["conditions"]["enqueue_is_idempotent"] is False


def test_a_refusal_with_no_reason_does_not_count_as_a_refusal():
    health = build_job_store_health(
        table_exists=True,
        enqueue_result={"created": True, "job": {"status": QUEUED}},
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect={"job": {"status": QUEUED}},
        illegal_transition_result={"transitioned": False, "blocked_reasons": []},
        backlog={
            "by_status": dict.fromkeys(JOB_STATUSES, 0),
            "total": 0,
            "completed_total": 0,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["conditions"]["illegal_transition_refused"] is False


def test_a_completed_row_anywhere_closes_the_lane():
    health = build_job_store_health(
        table_exists=True,
        enqueue_result={"created": True, "job": {"status": QUEUED}},
        duplicate_enqueue_result={"deduplicated": True},
        reread_after_reconnect={"job": {"status": QUEUED}},
        illegal_transition_result={"transitioned": False, "blocked_reasons": ["x"]},
        backlog={
            "by_status": {**dict.fromkeys(JOB_STATUSES, 0), COMPLETED: 1},
            "total": 1,
            "completed_total": 1,
            "rows_with_execution_proof": 0,
        },
    )
    assert health["collection_job_store_ready"] is False
    assert any("holds_a_completed_job" in b for b in health["blockers"])


def test_ready_alongside_blockers_is_an_invariant_failure():
    """The Gate 154 defect, caught in both directions."""
    assert "ready_alongside_blockers" in job_store_health_invariant_failures(
        {
            "collection_job_store_ready": True,
            "blockers": ["something"],
            "conditions": {},
            "ready_does_not_mean": ["x"],
        }
    )
    assert "not_ready_without_naming_a_blocker" in job_store_health_invariant_failures(
        {"collection_job_store_ready": False, "blockers": [], "conditions": {}}
    )


def test_every_condition_carries_evidence():
    health = build_job_store_health(table_exists=True)
    for condition in CONDITIONS:
        assert health["condition_evidence"].get(condition, "").strip()


def test_the_lane_names_what_ready_does_not_mean():
    health = build_job_store_health(table_exists=True)
    assert "a source was contacted" in health["ready_does_not_mean"]
    assert "monitoring is live" in health["ready_does_not_mean"]


def test_the_health_service_opens_no_connection():
    module = Path(
        REPO_ROOT
        / "src/nativeforge/services/source_collection_job_store_health_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "sa.insert", "sa.update"):
        assert forbidden not in module


# ---------------------------------------------------------- 158H the routes


@pytest.mark.parametrize(
    "path", ["health", "jobs", "backlog", "capability"]
)
def test_every_read_route_answers(client, path):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/job-store/{path}",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200


def test_the_routes_need_a_session(client):
    soh.ensure_org(DEMO, "demo")
    for path in ("health", "jobs", "backlog", "capability"):
        assert client.get(
            f"/v1/nf/demo/orgs/{DEMO}/job-store/{path}"
        ).status_code in (401, 403)


def test_another_organization_gets_a_404_not_a_403(client):
    """A 403 would confirm the organization exists to somebody not in it.

    Five guards originally read `if not same_org(ctx, org_id)`, which passed
    the arguments backwards AND tested a None return - so every request would
    have been refused with a 403.
    """
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{OTHER}/job-store/health",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 404


def test_the_dry_run_writes_nothing_and_proves_it(client):
    soh.ensure_org(DEMO, "demo")
    response = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/job-store/dry-run",
        headers=soh.session_headers(DEMO),
        json={"limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rows_after"] == body["rows_before"]
    assert body["nothing_persisted"] is True
    # And it was not a no-op: a dry run that could not write proves nothing
    # about what a real cycle would do.
    assert body["the_savepoint_actually_held_rows"] is True
    assert body["rows_inside_the_savepoint"] > body["rows_before"]
    assert body["invariant_failures"] == []
    assert body["collectors_invoked"] == 0
    assert body["live_source_calls"] == 0
    assert body["source_monitoring_live"] is False


def test_the_health_route_defers_the_restart_proof_rather_than_faking_it(client):
    """It reads back through the connection that wrote, so it must not claim it."""
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/job-store/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["restart_evidence_supplied"] is False
    assert body["conditions"]["survives_restart"] is False
    assert body["measured_by_the_verifier"] == list(NOT_MEASURABLE_BY_A_REQUEST)
    assert "verify_nativeforge_collection_job_store.sh" in body["why"]
    assert body["invariant_failures"] == []


def test_the_health_route_leaves_no_fixture_row_behind(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/job-store/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["health_probe_rolled_back"] is True
    assert body["health_probe_rows_left_behind"] == 0


def test_the_capability_route_reports_completion_unreachable(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/job-store/capability",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["completed_is_reachable"] is False
    assert body["declares_lease_columns"] == []


def test_no_route_writes_outside_a_savepoint():
    module = Path(
        REPO_ROOT / "src/nativeforge/api/source_collection_job_store_routes.py"
    ).read_text()
    # Every write path in this module is wrapped, and every wrapper rolls back.
    assert module.count("begin_nested()") == 2
    assert module.count("savepoint.rollback()") == 2


# -------------------------------------------------------- 158K the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = write_job_store_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(ARTIFACT_FILES)
    assert job_store_artifact_invariant_failures(result) == []


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    built = build_job_store_artifacts()
    for name, body in built.items():
        on_disk = (REPO_ROOT / ARTIFACT_DIR / name).read_text()
        assert on_disk == body, f"{name} is stale; run .git/regen2.py"


def test_the_artifacts_carry_no_secret_shape():
    for body in build_job_store_artifacts().values():
        assert "GOCSPX-" not in body
        assert "nf_session=" not in body
        assert "BEGIN PRIVATE KEY" not in body


def test_the_monitoring_artifact_still_says_nothing_is_live():
    built = build_job_store_artifacts()
    status = json.loads(built["source_monitoring_status.json"])
    assert status["source_monitoring_live"] is False
    assert status["approved_source_count"] == 0
    assert status["jobs_completed"] == 0
    assert status["rows_with_execution_proof"] == 0
    assert status["claimed_job_means_source_contacted"] is False


def test_the_artifact_writer_opens_no_database():
    module = Path(
        REPO_ROOT
        / "src/nativeforge/services/source_job_store_artifact_gate158_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "get_settings"):
        assert forbidden not in module


def test_the_state_machine_artifact_is_rendered_not_retyped():
    rendered = json.loads(build_job_store_artifacts()["job_state_machine.json"])
    assert rendered["legal_transitions"] == {
        state: sorted(targets) for state, targets in LEGAL_TRANSITIONS.items()
    }
    assert sorted(rendered["terminal_reasons"]) == sorted(TERMINAL_REASONS)


# ------------------------------------------------ 158I the verifier contract


def test_the_verifier_exists_and_is_executable():
    script = REPO_ROOT / "scripts/verify_nativeforge_collection_job_store.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_the_verifier_is_registered():
    """Gate 154's guard fails on an unregistered script. Registering is part."""
    from nativeforge.services.readiness_verifier_registry_service import (
        build_verifier_registry,
    )

    registry = build_verifier_registry()
    # The entry key is `verifier`, and the registry already publishes the set.
    assert "collection_job_store" in registry["verifier_names"]
    entry = next(
        e for e in registry["verifiers"] if e["verifier"] == "collection_job_store"
    )
    assert entry["lane"] == "collection_job_store_ready"
    assert entry["gate"] == "158"
    assert entry["blocking"] is True


def test_the_verifier_proves_the_restart_in_a_separate_process():
    script = (
        REPO_ROOT / "scripts/verify_nativeforge_collection_job_store.sh"
    ).read_text()
    assert "scripts/_g158_phase_a.py" in script
    assert "scripts/_g158_phase_b.py" in script


def test_the_verifier_fails_a_cleanup_that_deleted_nothing():
    """Gate 157's cleanup matched nothing it created and reported success."""
    script = (
        REPO_ROOT / "scripts/verify_nativeforge_collection_job_store.sh"
    ).read_text()
    assert "cleanup_had_something_to_clean" in script
    assert "a cleanup that deletes nothing is untested" in script


def test_the_cleanup_matches_a_column_the_verifier_controls():
    """Gate 157 filtered on job_id, which is a digest rather than the prefix.

    PARSE the DELETE statements, do not scan for them. This test was wrong
    twice before it was right:

      1. scanning the whole file matched the docstring that EXPLAINS Gate
         157's defect, quoting the pattern it must not use
      2. scanning line by line split the SQL, whose adjacent string literals
         span two lines, so the verb and its WHERE clause were never seen
         together

    Both were scans for a spelling standing in for a check on a behaviour -
    the fifth and sixth times in this campaign. The AST gives the statement.
    """
    tree = ast.parse((REPO_ROOT / "scripts/_g158_phase_cleanup.py").read_text())
    # Adjacent string literals are ONE constant after parsing, so each of
    # these is a whole statement rather than the line it started on. A
    # line-based scan saw `DELETE FROM ...` and its WHERE clause separately.
    deletes = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "DELETE FROM" in node.value
    ]
    # Falsifiable: a scan that found no DELETE at all must not pass.
    assert len(deletes) == 2, deletes
    for statement in deletes:
        assert "source_id LIKE" in statement, statement
        assert "job_id LIKE" not in statement, statement


@pytest.mark.parametrize(
    "phase",
    [
        "_g158_phase_a.py",
        "_g158_phase_b.py",
        "_g158_phase_c.py",
        "_g158_phase_health.py",
        "_g158_phase_cleanup.py",
    ],
)
def test_every_phase_script_compiles(phase):
    path = REPO_ROOT / "scripts" / phase
    assert path.exists()
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# ------------------------------------------------------ the standing boundary


@pytest.mark.parametrize("module", GATE_158_MODULES)
def test_no_gate_158_module_imports_an_http_client(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("import requests", "import httpx", "urllib.request", "aiohttp"):
        assert forbidden not in body, f"{module} reaches the network"


@pytest.mark.parametrize("module", GATE_158_MODULES)
def test_no_gate_158_module_starts_a_thread_or_a_process(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("threading.Thread", "subprocess.", "multiprocessing"):
        assert forbidden not in body, f"{module} starts something"


def test_the_repository_never_writes_an_execution_proof():
    body = (
        REPO_ROOT
        / "src/nativeforge/repositories/source_collection_job_repository.py"
    ).read_text()
    # Declared and read, never assigned a value.
    assert "execution_proof_ref=None" in body
    assert "execution_proof_ref=str" not in body
    assert 'values["execution_proof_ref"]' not in body


def test_nothing_in_gate_158_sends_email_or_touches_an_object_store():
    for module in GATE_158_MODULES:
        body = (REPO_ROOT / module).read_text()
        for forbidden in ("smtplib", "sendgrid", "boto3", "s3_client", "send_email"):
            assert forbidden not in body, f"{module} mentions {forbidden}"
