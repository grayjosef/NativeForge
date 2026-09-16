"""Gate 159: the periodic orchestration runtime.

Every defect this gate found in its own work has a test here, named for what it
would have shipped:

  - `read_last_served_slot` counted a CRASHED slot as served, so the trigger
    refused before acquisition and the expired-ownership reclaim was
    unreachable. The expiry existed, the reclaim existed, and nothing could
    reach it - one crashed orchestrator would have blocked its slot forever.
  - the health lane's `catchup_is_bounded` compared a count with itself, which
    is true of every input
  - the orchestrator script had no default clock, so its documented default
    invocation refused with `no_clock_supplied` and printed a report of nulls
  - a probe measured "a live owner" and "an expired owner" in the SAME hourly
    slot, so it tested the expired case twice under two names

The restart proof itself is not here. Proving a row outlives the process that
wrote it needs a second process, and a test that commits into the demo org and
reconnects would leave rows behind on every run. The verifier does it:
scripts/verify_nativeforge_source_orchestration_runtime.sh, phases A and B.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.repositories.source_collection_job_repository import list_jobs
from nativeforge.repositories.source_collection_orchestration_lock_repository import (
    ACQUIRED,
    CYCLE_OUTCOMES,
    CYCLE_STATUSES,
    CYCLES,
    RELEASED,
    acquire_cycle,
    count_cycles,
    list_stale_owners,
    orchestration_lock_invariant_failures,
    read_last_served_slot,
    release_cycle,
)
from nativeforge.services.source_collection_missed_window_service import (
    missed_window_invariant_failures,
    recover_missed_windows,
)
from nativeforge.services.source_collection_orchestration_health_service import (
    CONDITIONS,
    NOT_MEASURABLE_BY_A_REQUEST,
    build_orchestration_health,
    orchestration_health_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_identity_service import (
    CADENCE_SECONDS,
    DEFAULT_CADENCE,
    build_cycle_id,
    build_orchestration_identity,
    build_owner_id,
    build_slot_key,
    compute_slot_index,
    normalize_cadence,
    orchestration_identity_invariant_failures,
    slot_started_at,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (
    CYCLE_MODE_EVALUATE_AND_PERSIST,
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)
from nativeforge.services.source_collection_periodic_trigger_service import (
    ALREADY_TRIGGERED,
    BLOCKED,
    DUE,
    MISSED_WINDOW,
    RECOVERED,
    TRIGGER_PERMITS_A_CYCLE,
    TRIGGER_STATES,
    compute_next_wake_at,
    evaluate_trigger,
    trigger_invariant_failures,
)
from nativeforge.services.source_orchestration_artifact_gate159_service import (
    ARTIFACT_DIR,
    ARTIFACT_FILES,
    build_orchestration_artifacts,
    orchestration_artifact_invariant_failures,
    write_orchestration_artifacts,
)
from tests import session_org_helper as soh

REPO_ROOT = Path(__file__).resolve().parents[1]

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-aaaaaaaaaaaa"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

T_SLOT = "2026-09-16T12:00:00Z"
T_SLOT_LATE = "2026-09-16T12:59:59Z"
T_NEXT = "2026-09-16T13:00:00Z"
T_GAP = "2026-09-16T18:00:00Z"

MIGRATION = REPO_ROOT / "alembic/versions/0045_source_orchestration_cycles.py"
UNIT = REPO_ROOT / "ops/systemd/nativeforge-source-orchestrator.service"
SCRIPT = REPO_ROOT / "scripts/run_source_collection_orchestrator.py"

GATE_159_MODULES = (
    "src/nativeforge/services/source_collection_orchestration_identity_service.py",
    "src/nativeforge/services/source_collection_periodic_trigger_service.py",
    "src/nativeforge/services/source_collection_missed_window_service.py",
    "src/nativeforge/services/source_collection_orchestration_runtime_service.py",
    "src/nativeforge/services/source_collection_orchestration_health_service.py",
    "src/nativeforge/services/source_orchestration_artifact_gate159_service.py",
    "src/nativeforge/repositories/source_collection_orchestration_lock_repository.py",
    "src/nativeforge/api/source_collection_orchestration_routes.py",
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


def _sources(tag: str, count: int = 3) -> list[dict]:
    return [
        {
            "source_id": f"{tag}-{index}",
            "check_interval_days": 7,
            "last_checked_at": "2026-09-01T00:00:00Z",
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for index in range(count)
    ]


def _cycle(connection, now, owner, tag="t159", **kwargs):
    return run_orchestration_cycle(
        connection=connection,
        organization_id=DEMO,
        owner_id=owner,
        sources=_sources(tag),
        now=now,
        **kwargs,
    )


def _take(connection, now, owner, lease=600, **kwargs):
    identity = build_orchestration_identity(now=now, cadence="hourly")
    return acquire_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=identity["cycle_id"],
        owner_id=owner,
        cadence="hourly",
        slot_index=identity["slot_index"],
        slot_key=identity["slot_key"],
        orchestration_version=identity["orchestration_version"],
        now=now,
        lease_seconds=lease,
        **kwargs,
    )


# ------------------------------------------------------ 159E the migration


def test_the_migration_exists_and_pins_0044_as_its_parent():
    body = MIGRATION.read_text()
    assert 'revision: str = "0045"' in body
    assert 'down_revision: str | Sequence[str] | None = "0044"' in body


def test_the_migration_refuses_a_cycle_that_claims_work_it_did_not_do():
    body = MIGRATION.read_text()
    assert "jobs_completed = 0" in body
    assert "collectors_invoked = 0" in body
    assert "live_source_calls = 0" in body


def test_the_migration_refuses_an_owner_with_no_expiry():
    """An owner that could never expire is how one crash blocks a slot."""
    assert "owner_has_an_expiry" in MIGRATION.read_text()


def test_the_migration_declares_no_job_lease_column():
    """Gate 157 owns the job claim. This table is per-cycle."""
    body = MIGRATION.read_text()
    for column in ("lease_owner", "lease_acquired_at", "lease_expires_at"):
        assert f'sa.Column("{column}"' not in body


def test_the_cycle_table_shares_no_column_name_with_the_job_lease():
    from nativeforge.services.source_collection_job_lease_service import LEASES

    cycle_columns = {column.name for column in CYCLES.columns}
    lease_only = {
        "lease_owner",
        "lease_acquired_at",
        "lease_expires_at",
        "lease_status",
        "failure_class",
        "attempt_count",
        "max_attempts",
        "next_retry_at",
    }
    assert cycle_columns & lease_only == set()
    # And the lease table is untouched by this gate.
    assert "cycle_id" not in {column.name for column in LEASES.columns}


def test_the_migration_carries_the_unique_index_that_suppresses_duplicates():
    body = MIGRATION.read_text()
    assert "ux_nf_source_orchestration_cycles_cycle_id" in body
    assert '["organization_id", "cycle_id"]' in body


# ------------------------------------------------------- 159D the identity


def test_the_same_slot_is_always_the_same_cycle():
    first = build_orchestration_identity(now=T_SLOT)
    second = build_orchestration_identity(now=T_SLOT_LATE)
    assert first["cycle_id"] == second["cycle_id"]
    assert first["slot_index"] == second["slot_index"]
    assert first["determinism_proof"]["matches"] is True
    assert orchestration_identity_invariant_failures(first) == []


def test_a_different_slot_is_a_different_cycle():
    assert (
        build_orchestration_identity(now=T_SLOT)["cycle_id"]
        != build_orchestration_identity(now=T_NEXT)["cycle_id"]
    )


def test_a_different_cadence_is_a_different_cycle():
    """Slot index 5 at daily and at hourly are different instants."""
    assert (
        build_orchestration_identity(now=T_SLOT, cadence="hourly")["cycle_id"]
        != build_orchestration_identity(now=T_SLOT, cadence="daily")["cycle_id"]
    )


def test_the_slot_is_a_floor_not_a_rounding():
    assert compute_slot_index(now=T_SLOT) == compute_slot_index(now=T_SLOT_LATE)
    assert compute_slot_index(now=T_NEXT) == compute_slot_index(now=T_SLOT) + 1


@pytest.mark.parametrize("cadence", sorted(CADENCE_SECONDS))
def test_every_cadence_produces_a_usable_identity(cadence):
    identity = build_orchestration_identity(now=T_SLOT, cadence=cadence)
    assert identity["usable"] is True
    assert orchestration_identity_invariant_failures(identity) == []


def test_an_unknown_cadence_normalizes_rather_than_widening():
    assert normalize_cadence("every_millisecond") == DEFAULT_CADENCE
    identity = build_orchestration_identity(now=T_SLOT, cadence="every_millisecond")
    assert identity["cadence"] == DEFAULT_CADENCE
    assert identity["cadence_was_normalized"] is True


def test_the_cycle_id_does_not_depend_on_a_pid_or_a_clock_position():
    identity = build_orchestration_identity(now=T_SLOT)
    for forbidden in ("pid", "worker_id", "startup_timestamp", "random_uuid"):
        assert forbidden in identity["not_derived_from"]
    # And the id is reproducible from the slot alone.
    assert identity["cycle_id"] == build_cycle_id(
        slot_index=identity["slot_index"], cadence=DEFAULT_CADENCE
    )


def test_an_owner_id_is_deliberately_NOT_deterministic():
    """Two contenders must be distinguishable, or the loser thinks it won."""
    assert build_owner_id(host="h", pid=1) != build_owner_id(host="h", pid=1)


def test_an_owner_id_is_never_part_of_a_cycle_id():
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_collection_orchestration_identity_service.py"
    ).read_text()
    tree = ast.parse(module)
    build = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_cycle_id"
    )
    # Parsed, not scanned: the docstrings in this module discuss owner ids at
    # length, so a text search would match the prose explaining the rule.
    names = {
        node.id for node in ast.walk(build) if isinstance(node, ast.Name)
    } | {
        node.arg for node in ast.walk(build) if isinstance(node, ast.arg)
    }
    assert "owner_id" not in names
    assert "nonce" not in names


def test_a_cycle_id_is_not_a_collection_job_id():
    identity = build_orchestration_identity(now=T_SLOT)
    assert identity["is_a_collection_job_id"] is False
    # And the identity module never imports Gate 99B's job digest.
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_collection_orchestration_identity_service.py"
    ).read_text()
    assert "build_job_id" not in module


def test_no_clock_yields_no_cycle_id_and_says_why():
    identity = build_orchestration_identity(now=None)
    assert identity["usable"] is False
    assert identity["cycle_id"] is None
    assert identity["blocked_reasons"] == ["no_clock_supplied"]
    assert orchestration_identity_invariant_failures(identity) == []


def test_the_slot_key_is_readable_and_not_part_of_the_digest():
    assert build_slot_key(now=T_SLOT) == "2026-09-16T12:00:00Z"
    assert slot_started_at(slot_index=compute_slot_index(now=T_SLOT)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ) == build_slot_key(now=T_SLOT)


# -------------------------------------------------------- 159C the trigger


def test_nothing_ever_served_is_due_not_a_century_of_missed_windows():
    decision = evaluate_trigger(now=T_SLOT, last_served_slot_index=None)
    assert decision["state"] == DUE
    assert decision["missed_slot_count"] == 0


def test_the_same_slot_again_is_already_triggered():
    current = compute_slot_index(now=T_SLOT)
    decision = evaluate_trigger(now=T_SLOT_LATE, last_served_slot_index=current)
    assert decision["state"] == ALREADY_TRIGGERED
    assert decision["should_run_a_cycle"] is False
    assert trigger_invariant_failures(decision) == []


def test_the_next_slot_is_due():
    current = compute_slot_index(now=T_SLOT)
    decision = evaluate_trigger(now=T_NEXT, last_served_slot_index=current)
    assert decision["state"] == DUE
    assert decision["should_run_a_cycle"] is True


def test_a_gap_is_a_missed_window():
    current = compute_slot_index(now=T_SLOT)
    decision = evaluate_trigger(now=T_GAP, last_served_slot_index=current)
    assert decision["state"] == MISSED_WINDOW
    assert decision["missed_slot_count"] == 6
    assert decision["should_run_a_cycle"] is True


def test_a_clock_that_went_backwards_is_blocked_not_reinterpreted():
    current = compute_slot_index(now=T_GAP)
    decision = evaluate_trigger(now=T_SLOT, last_served_slot_index=current)
    assert decision["state"] == BLOCKED
    assert "last_served_slot_is_in_the_future" in decision["blocked_reasons"]
    assert decision["should_run_a_cycle"] is False


def test_a_disabled_trigger_is_blocked_and_names_the_reason():
    decision = evaluate_trigger(
        now=T_SLOT, last_served_slot_index=None, trigger_enabled=False
    )
    assert decision["state"] == BLOCKED
    assert "periodic_trigger_is_not_enabled" in decision["blocked_reasons"]


def test_should_run_a_cycle_agrees_with_the_permitting_set():
    for state in TRIGGER_STATES:
        # The invariant checker enforces this for whatever state arrives, so a
        # state added later that nobody wired in refuses rather than permits.
        fabricated = {
            "state": state,
            "should_run_a_cycle": state in TRIGGER_PERMITS_A_CYCLE,
            "blocked_reasons": ["x"] if state == BLOCKED else [],
            "max_catchup_slots": 6,
            "recoverable_slot_indexes": [],
            "recoverable_slot_count": 0,
            "missed_slot_indexes": [],
            "missed_slot_count": 0,
            "slots_dropped_by_the_bound": 0,
            "catchup_was_bounded": False,
            "clock_is_injected": True,
        }
        failures = trigger_invariant_failures(fabricated)
        if state == RECOVERED:
            # Only the recovery pass may report this one. Matched on the exact
            # failure key: an earlier version of this assertion looked for the
            # phrase "only recovery may report", which is the same words with
            # spaces instead of underscores and never matched.
            assert (
                "the_trigger_reported_a_state_only_recovery_may_report" in failures
            ), failures
        else:
            assert not any("should_run_a_cycle_disagrees" in f for f in failures)


def test_a_lying_should_run_a_cycle_is_caught():
    decision = evaluate_trigger(now=T_SLOT, last_served_slot_index=None)
    tampered = {**decision, "state": ALREADY_TRIGGERED}
    assert any(
        "should_run_a_cycle_disagrees_with_state" in f
        for f in trigger_invariant_failures(tampered)
    )


def test_the_catchup_bound_holds_and_reports_what_it_dropped():
    current = compute_slot_index(now=T_SLOT)
    decision = evaluate_trigger(
        now="2026-09-18T00:00:00Z",
        last_served_slot_index=current,
        max_catchup_slots=4,
    )
    assert decision["missed_slot_count"] > 4
    assert decision["recoverable_slot_count"] == 4
    assert decision["slots_dropped_by_the_bound"] == (
        decision["missed_slot_count"] - 4
    )
    assert decision["catchup_was_bounded"] is True
    assert trigger_invariant_failures(decision) == []


def test_the_bound_keeps_the_most_recent_slots():
    """The oldest slots describe work the newest already covers."""
    current = compute_slot_index(now=T_SLOT)
    decision = evaluate_trigger(
        now="2026-09-18T00:00:00Z",
        last_served_slot_index=current,
        max_catchup_slots=3,
    )
    assert decision["recoverable_slot_indexes"] == decision[
        "missed_slot_indexes"
    ][-3:]


def test_a_recoverable_set_larger_than_the_bound_is_an_invariant_failure():
    decision = evaluate_trigger(now=T_GAP, last_served_slot_index=None)
    tampered = {
        **decision,
        "recoverable_slot_indexes": list(range(99)),
        "recoverable_slot_count": 99,
        "max_catchup_slots": 4,
    }
    assert (
        "recoverable_slots_exceed_the_catchup_bound"
        in trigger_invariant_failures(tampered)
    )


def test_the_next_wake_is_a_slot_boundary():
    """Not now + interval, which would drift off the cadence."""
    wake = compute_next_wake_at(now=T_SLOT_LATE)
    assert wake == slot_started_at(slot_index=compute_slot_index(now=T_NEXT))


def test_the_trigger_reads_no_wall_clock():
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_collection_periodic_trigger_service.py"
    ).read_text()
    tree = ast.parse(module)
    calls = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and "now" in ast.unparse(node.func)
    ]
    # Parsed, not scanned: this module's docstring discusses datetime.now() to
    # explain why it must not call it.
    assert not any("datetime.now" in call for call in calls), calls


# ---------------------------------------------------------- 159E the lock


def test_a_cycle_can_be_acquired_and_released(connection):
    taken = _take(connection, T_SLOT, "owner-a")
    assert taken["acquired"] is True
    assert taken["cycle"]["cycle_status"] == ACQUIRED
    assert taken["cycle"]["owner_id"] == "owner-a"
    assert orchestration_lock_invariant_failures(taken) == []

    done = release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-a",
        now=T_SLOT_LATE,
    )
    assert done["released"] is True
    assert done["cycle"]["cycle_status"] == RELEASED
    assert done["cycle"]["released_at"] is not None


def test_a_live_owner_cannot_be_stolen_from(connection):
    _take(connection, T_SLOT, "owner-alive", lease=3600)
    theft = _take(connection, "2026-09-16T12:10:00Z", "owner-thief")
    assert theft["acquired"] is False
    assert theft["duplicate_suppressed"] is True
    assert (
        "ownership_has_not_expired_and_cannot_be_stolen" in theft["blocked_reasons"]
    )


def test_an_expired_owner_is_reclaimable(connection):
    """The permitting branch. A lock that refused everything proves nothing."""
    _take(connection, T_SLOT, "owner-dies", lease=60)
    rescue = _take(connection, "2026-09-16T12:30:00Z", "owner-rescuer")
    assert rescue["acquired"] is True
    assert rescue["reclaimed"] is True
    assert rescue["cycle"]["owner_id"] == "owner-rescuer"
    assert rescue["cycle"]["reclaim_count"] == 1
    assert rescue["cycle"]["cycle_outcome"] == "reclaimed_from_an_expired_owner"


def test_a_recovery_pass_does_not_reclaim(connection):
    """Catching up on history must not steal a slot from the present."""
    _take(connection, T_SLOT, "owner-dies", lease=60)
    refused = _take(
        connection, "2026-09-16T12:30:00Z", "recovery", allow_reclaim=False
    )
    assert refused["acquired"] is False


def test_a_released_slot_is_refused_as_already_served(connection):
    taken = _take(connection, T_SLOT, "owner-a")
    release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-a",
        now=T_SLOT,
    )
    again = _take(connection, T_SLOT_LATE, "owner-b")
    assert again["acquired"] is False
    assert "this_slot_has_already_been_served" in again["blocked_reasons"]


def test_a_non_owner_cannot_release(connection):
    taken = _take(connection, T_SLOT, "owner-a")
    stolen = release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-b",
        now=T_SLOT,
    )
    assert stolen["released"] is False
    assert "caller_does_not_own_this_cycle" in stolen["blocked_reasons"]


def test_the_real_organization_is_refused_by_name(connection):
    refused = acquire_cycle(
        connection=connection,
        organization_id=REAL_ORG,
        cycle_id="never",
        owner_id="x",
        cadence="hourly",
        slot_index=1,
        now=T_SLOT,
    )
    assert refused["acquired"] is False
    assert "real_organization_refused_by_name" in refused["blocked_reasons"]


def test_a_crashed_slot_reads_as_unfinished_not_served(connection):
    """THE defect: this is what made the reclaim path unreachable.

    History counted a row in any status as served, so a process that acquired
    a slot and crashed left an `acquired` row, every later process inside that
    slot was told `already_triggered`, and the expired ownership was never
    reclaimed - for that slot, forever.
    """
    _take(connection, T_SLOT, "owner-dies", lease=60)

    # Still inside the lease: actively owned, so it counts as served.
    live = read_last_served_slot(
        connection=connection,
        organization_id=DEMO,
        cadence="hourly",
        now="2026-09-16T12:00:30Z",
    )
    assert live["last_served_slot_index"] == compute_slot_index(now=T_SLOT)
    assert live["unfinished_slot_count"] == 0

    # After the lease lapses: unfinished, and NOT served.
    crashed = read_last_served_slot(
        connection=connection,
        organization_id=DEMO,
        cadence="hourly",
        now="2026-09-16T12:30:00Z",
    )
    assert crashed["last_served_slot_index"] is None
    assert crashed["unfinished_slot_count"] == 1
    assert crashed["served_definition"] == "released_or_still_actively_owned"


def test_the_reclaim_path_is_reachable_through_the_runtime(connection):
    """Not just present. The first draft had a reclaim nothing could reach."""
    first = _cycle(connection, T_SLOT, "owner-dies", lease_seconds=60,
                   run_worker=False)
    assert first["ran"] is True
    # Put the row back the way a crash leaves it: owned, never released.
    connection.execute(
        sa.text(
            "UPDATE nf_source_orchestration_cycles SET cycle_status='acquired', "
            "released_at=NULL, completed_at=NULL WHERE cycle_id=:cycle_id"
        ),
        {"cycle_id": first["orchestration_cycle_id"]},
    )
    rescue = _cycle(
        connection, "2026-09-16T12:30:00Z", "owner-rescuer", run_worker=False
    )
    assert rescue["ran"] is True
    assert rescue["reclaimed_an_expired_owner"] is True
    assert rescue["unfinished_slots"] == 1


def test_stale_owners_are_derived_against_the_supplied_clock(connection):
    _take(connection, T_SLOT, "owner-dies", lease=60)
    fresh = list_stale_owners(
        connection=connection, organization_id=DEMO, now="2026-09-16T12:00:30Z"
    )
    lapsed = list_stale_owners(
        connection=connection, organization_id=DEMO, now="2026-09-16T12:30:00Z"
    )
    assert fresh["stale_owner_count"] == 0
    assert lapsed["stale_owner_count"] == 1


def test_the_counts_report_every_status_including_the_empty_ones(connection):
    counts = count_cycles(connection=connection, organization_id=DEMO)
    assert set(counts["by_status"]) == set(CYCLE_STATUSES)
    assert counts["rows_claiming_a_completion"] == 0
    assert counts["rows_claiming_a_collector"] == 0
    assert counts["rows_claiming_a_live_call"] == 0
    assert orchestration_lock_invariant_failures(counts) == []


def test_the_database_refuses_a_cycle_claiming_a_collector(connection):
    """The CHECK is real, not a convention the repository happens to honour."""
    _take(connection, T_SLOT, "owner-a")
    with pytest.raises(sa.exc.IntegrityError):
        with connection.begin_nested():
            connection.execute(
                sa.text(
                    "UPDATE nf_source_orchestration_cycles "
                    "SET collectors_invoked = 1"
                )
            )


def test_release_cannot_smuggle_a_completion(connection):
    """`jobs_completed` is not in the list of counters release accepts."""
    taken = _take(connection, T_SLOT, "owner-a")
    done = release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-a",
        now=T_SLOT,
        counters={"jobs_completed": 5, "collectors_invoked": 9, "jobs_created": 3},
    )
    assert done["released"] is True
    assert done["cycle"]["jobs_completed"] == 0
    assert done["cycle"]["collectors_invoked"] == 0
    assert done["cycle"]["jobs_created"] == 3


@pytest.mark.parametrize("outcome", sorted(CYCLE_OUTCOMES))
def test_every_outcome_in_the_vocabulary_is_accepted(connection, outcome):
    taken = _take(connection, T_SLOT, "owner-a")
    done = release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-a",
        now=T_SLOT,
        outcome=outcome,
    )
    assert done["released"] is True


def test_an_outcome_outside_the_vocabulary_is_refused(connection):
    taken = _take(connection, T_SLOT, "owner-a")
    done = release_cycle(
        connection=connection,
        organization_id=DEMO,
        cycle_id=taken["cycle_id"],
        owner_id="owner-a",
        now=T_SLOT,
        outcome="invented",
    )
    assert done["released"] is False


# ------------------------------------------------------ 159B the runtime


def test_a_cycle_composes_scheduler_store_and_worker(connection):
    report = _cycle(connection, T_SLOT, "owner-a", tag="t159a")
    assert report["ran"] is True
    assert report["trigger_state"] == DUE
    assert report["sources_seen"] == 3
    assert report["jobs_created"] == 3
    assert report["jobs_claimed"] == 3
    assert report["jobs_refused"] == 3
    assert report["jobs_blocked"] == 3
    assert orchestration_cycle_invariant_failures(report) == []


def test_the_same_slot_twice_produces_one_effect(connection):
    first = _cycle(connection, T_SLOT, "owner-a", tag="t159b")
    before = list_jobs(connection=connection, organization_id=DEMO)["job_count"]
    second = _cycle(connection, T_SLOT_LATE, "owner-a", tag="t159b")
    after = list_jobs(connection=connection, organization_id=DEMO)["job_count"]

    assert first["ran"] is True
    assert second["ran"] is False
    assert second["trigger_state"] == ALREADY_TRIGGERED
    assert second["duplicate_triggers_suppressed"] == 1
    assert second["jobs_created"] == 0
    assert after == before


def test_a_different_owner_in_the_same_slot_is_refused(connection):
    _cycle(connection, T_SLOT, "owner-a", tag="t159c")
    second = _cycle(connection, T_SLOT, "owner-b", tag="t159c")
    assert second["ran"] is False
    assert second["jobs_created"] == 0


def test_a_new_slot_runs_and_reuses_the_same_work(connection):
    _cycle(connection, T_SLOT, "owner-a", tag="t159d")
    later = _cycle(connection, T_NEXT, "owner-a", tag="t159d")
    assert later["ran"] is True
    assert later["jobs_created"] == 0
    assert later["jobs_reused"] == 3


def test_a_cycle_without_a_connection_is_refused_and_says_why():
    report = run_orchestration_cycle(
        connection=None,
        organization_id=DEMO,
        owner_id="owner-a",
        sources=[],
        now=T_SLOT,
    )
    assert report["ran"] is False
    assert "no_connection_supplied" in report["blocked_reasons"]
    assert orchestration_cycle_invariant_failures(report) == []


def test_a_cycle_without_a_clock_is_refused():
    report = run_orchestration_cycle(
        connection=None, organization_id=DEMO, owner_id="o", sources=[], now=None
    )
    assert report["ran"] is False
    assert "no_clock_supplied" in report["blocked_reasons"]


def test_a_cycle_that_ran_contacted_nothing(connection):
    report = _cycle(connection, T_SLOT, "owner-a", tag="t159e")
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
        "emails_sent",
        "object_store_calls",
        "threads_started",
        "approved_source_count",
        "jobs_completed",
        "jobs_executable",
    ):
        assert report[counter] == 0, counter
    assert report["source_monitoring_live"] is False
    assert report["last_checked_at_advanced"] is False


def test_the_invariant_checker_catches_a_cycle_claiming_a_collector(connection):
    report = _cycle(connection, T_SLOT, "owner-a", tag="t159f")
    tampered = {**report, "collectors_invoked": 1}
    assert any(
        "cycle_counted:collectors_invoked" in f
        for f in orchestration_cycle_invariant_failures(tampered)
    )


def test_the_invariant_checker_catches_a_cycle_inventing_work(connection):
    report = _cycle(connection, T_SLOT, "owner-a", tag="t159g")
    tampered = {**report, "jobs_created": 99, "sources_seen": 3, "jobs_reused": 0}
    assert (
        "created_plus_reused_exceeds_the_sources_evaluated"
        in orchestration_cycle_invariant_failures(tampered)
    )


def test_the_invariant_checker_catches_recovering_more_than_was_detected():
    assert (
        "recovered_more_windows_than_were_detected"
        in orchestration_cycle_invariant_failures(
            {
                "mode": CYCLE_MODE_EVALUATE_AND_PERSIST,
                "ran": False,
                "blocked_reasons": ["x"],
                "missed_windows_detected": 1,
                "missed_windows_recovered": 5,
                "clock_is_injected": True,
            }
        )
    )


# ------------------------------------------------ 159F missed-window recovery


def test_a_missed_window_is_recovered_once(connection):
    _cycle(connection, T_SLOT, "owner-a", tag="t159h")
    gap = _cycle(connection, T_GAP, "owner-a", tag="t159h")
    assert gap["trigger_state"] == MISSED_WINDOW
    assert gap["missed_windows_detected"] > 1
    assert gap["missed_windows_recovered"] >= 1
    assert orchestration_cycle_invariant_failures(gap) == []


def test_recovering_the_same_outage_twice_recovers_nothing_new(connection):
    _cycle(connection, T_SLOT, "owner-a", tag="t159i")
    _cycle(connection, T_GAP, "owner-a", tag="t159i")
    again = _cycle(connection, T_GAP, "owner-b", tag="t159i")
    assert again["ran"] is False
    assert again["missed_windows_recovered"] == 0


def test_recovery_invents_no_work(connection):
    """Every recovered slot computes the same Gate 158 job ids."""
    _cycle(connection, T_SLOT, "owner-a", tag="t159j")
    before = list_jobs(connection=connection, organization_id=DEMO)["job_count"]
    _cycle(connection, T_GAP, "owner-a", tag="t159j")
    after = list_jobs(connection=connection, organization_id=DEMO)["job_count"]
    assert after == before


def test_recovery_without_a_connection_is_refused():
    recovery = recover_missed_windows(
        connection=None,
        organization_id=DEMO,
        owner_id="o",
        recoverable_slot_indexes=[1, 2],
        now=T_SLOT,
    )
    assert recovery["ran"] is False
    assert "no_connection_supplied" in recovery["blocked_reasons"]
    assert missed_window_invariant_failures(recovery) == []


def test_recovery_counts_add_up(connection):
    identity = build_orchestration_identity(now=T_SLOT)
    recovery = recover_missed_windows(
        connection=connection,
        organization_id=DEMO,
        owner_id="owner-a",
        recoverable_slot_indexes=[
            identity["slot_index"] - 2,
            identity["slot_index"] - 1,
        ],
        cadence="hourly",
        now=T_SLOT,
    )
    assert recovery["slots_offered"] == 2
    assert (
        recovery["slots_recovered"]
        + recovery["slots_already_served"]
        + recovery["slots_refused"]
        == 2
    )
    assert missed_window_invariant_failures(recovery) == []


def test_recovery_does_not_advance_last_checked_at(connection):
    recovery = recover_missed_windows(
        connection=connection,
        organization_id=DEMO,
        owner_id="owner-a",
        recoverable_slot_indexes=[compute_slot_index(now=T_SLOT) - 1],
        cadence="hourly",
        now=T_SLOT,
    )
    assert recovery["last_checked_at_advanced"] is False
    assert recovery["jobs_completed"] == 0


# ----------------------------------------------------------- 159I the health


def test_a_fully_evidenced_lane_goes_green():
    trigger = evaluate_trigger(now=T_SLOT, last_served_slot_index=None)
    health = build_orchestration_health(
        cycle={
            "ran": True,
            "mode": CYCLE_MODE_EVALUATE_AND_PERSIST,
            "orchestration_cycle_id": "abc",
            "slot_index": 1,
            "owner_id": "o",
            "blocked_reasons": [],
            "clock_is_injected": True,
            "missed_windows_detected": 2,
        },
        trigger=trigger,
        identity_is_deterministic=True,
        duplicate_trigger_result={
            "ran": False,
            "duplicate_triggers_suppressed": 1,
            "jobs_created": 0,
        },
        concurrent_owner_refused=True,
        expired_owner_reclaimed=True,
        missed_window_result={"slots_recovered": 1, "slots_offered": 1},
        restart_recovered_nothing=True,
        cycle_counts={
            "by_status": dict.fromkeys(CYCLE_STATUSES, 0),
            "total": 0,
            "rows_claiming_a_completion": 0,
            "rows_claiming_a_collector": 0,
            "rows_claiming_a_live_call": 0,
        },
        backlog={"completed_total": 0, "rows_with_execution_proof": 0},
    )
    assert health["orchestration_runtime_ready"] is True
    assert health["blockers"] == []
    assert orchestration_health_invariant_failures(health) == []


def test_a_lane_missing_the_three_process_conditions_is_red():
    trigger = evaluate_trigger(now=T_SLOT, last_served_slot_index=None)
    health = build_orchestration_health(
        cycle={
            "ran": True,
            "mode": CYCLE_MODE_EVALUATE_AND_PERSIST,
            "orchestration_cycle_id": "abc",
            "slot_index": 1,
            "owner_id": "o",
            "blocked_reasons": [],
            "clock_is_injected": True,
        },
        trigger=trigger,
        identity_is_deterministic=True,
        duplicate_trigger_result={
            "ran": False,
            "duplicate_triggers_suppressed": 1,
            "jobs_created": 0,
        },
        concurrent_owner_refused=True,
        cycle_counts={
            "by_status": dict.fromkeys(CYCLE_STATUSES, 0),
            "total": 0,
            "rows_claiming_a_completion": 0,
            "rows_claiming_a_collector": 0,
            "rows_claiming_a_live_call": 0,
        },
        backlog={"completed_total": 0, "rows_with_execution_proof": 0},
    )
    assert health["orchestration_runtime_ready"] is False
    assert sorted(health["conditions_not_met"]) == sorted(
        NOT_MEASURABLE_BY_A_REQUEST
    )


def test_a_duplicate_that_quietly_did_the_work_does_not_count_as_suppressed():
    """Both halves: refused AND created nothing."""
    health = build_orchestration_health(
        duplicate_trigger_result={
            "ran": False,
            "duplicate_triggers_suppressed": 1,
            "jobs_created": 7,
        }
    )
    assert health["conditions"]["duplicate_trigger_suppressed"] is False


@pytest.mark.parametrize(
    ("recoverable", "bound", "dropped", "bounded_flag", "expected"),
    [
        (4, 6, 0, False, True),
        (9, 6, 3, True, False),
        (6, 6, 7, False, False),
    ],
)
def test_catchup_is_bounded_is_falsifiable(
    recoverable, bound, dropped, bounded_flag, expected
):
    """The first version compared a count with itself, which is always true."""
    health = build_orchestration_health(
        trigger={
            "state": DUE,
            "max_catchup_slots": bound,
            "recoverable_slot_count": recoverable,
            "slots_dropped_by_the_bound": dropped,
            "catchup_was_bounded": bounded_flag,
        }
    )
    assert health["conditions"]["catchup_is_bounded"] is expected


def test_a_completed_job_anywhere_closes_the_lane():
    health = build_orchestration_health(
        backlog={"completed_total": 1, "rows_with_execution_proof": 0}
    )
    assert health["orchestration_runtime_ready"] is False
    assert any("holds_a_completed_job" in b for b in health["blockers"])


def test_a_cycle_row_claiming_a_collector_closes_the_lane():
    health = build_orchestration_health(
        cycle_counts={
            "by_status": {},
            "total": 0,
            "rows_claiming_a_completion": 0,
            "rows_claiming_a_collector": 2,
            "rows_claiming_a_live_call": 0,
        }
    )
    assert health["orchestration_runtime_ready"] is False
    assert any("claims_a_collector" in b for b in health["blockers"])


def test_ready_alongside_blockers_is_an_invariant_failure():
    assert "ready_alongside_blockers" in orchestration_health_invariant_failures(
        {
            "orchestration_runtime_ready": True,
            "blockers": ["something"],
            "conditions": {},
            "ready_does_not_mean": ["x"],
        }
    )
    assert (
        "not_ready_without_naming_a_blocker"
        in orchestration_health_invariant_failures(
            {
                "orchestration_runtime_ready": False,
                "blockers": [],
                "conditions": {},
            }
        )
    )


def test_every_condition_carries_evidence():
    health = build_orchestration_health()
    for condition in CONDITIONS:
        assert health["condition_evidence"].get(condition, "").strip()


def test_the_health_service_opens_no_connection():
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_collection_orchestration_health_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "sa.insert", "sa.update"):
        assert forbidden not in module


def test_the_lane_names_what_ready_does_not_mean():
    health = build_orchestration_health()
    assert "monitoring is live" in health["ready_does_not_mean"]
    assert "a schedule advanced" in health["ready_does_not_mean"]


# ----------------------------------------------------------- 159J the routes


@pytest.mark.parametrize("path", ["health", "trigger", "missed-windows"])
def test_every_read_route_answers(client, path):
    soh.ensure_org(DEMO, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/orchestration/{path}",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200


def test_the_routes_need_a_session(client):
    soh.ensure_org(DEMO, "demo")
    for path in ("health", "trigger", "missed-windows"):
        assert client.get(
            f"/v1/nf/demo/orgs/{DEMO}/orchestration/{path}"
        ).status_code in (401, 403)


def test_another_organization_gets_a_404_not_a_403(client):
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    response = client.get(
        f"/v1/nf/demo/orgs/{OTHER}/orchestration/health",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 404


def test_the_dry_run_does_not_consume_the_slot(client):
    """A committed dry run would suppress the next genuine cycle."""
    soh.ensure_org(DEMO, "demo")
    response = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/orchestration/dry-run",
        headers=soh.session_headers(DEMO),
        json={"limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["cycle_rows_after"] == body["cycle_rows_before"]
    assert body["nothing_persisted"] is True
    # And it was not a no-op: a dry run that could not write proves nothing.
    assert body["the_savepoint_actually_held_rows"] is True
    assert body["invariant_failures"] == []
    assert body["collectors_invoked"] == 0
    assert body["source_monitoring_live"] is False


def test_the_health_route_defers_the_three_it_cannot_measure(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/orchestration/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["measured_by_the_verifier"] == list(NOT_MEASURABLE_BY_A_REQUEST)
    assert "verify_nativeforge_source_orchestration_runtime.sh" in body["why"]
    # Every red condition is one a request genuinely cannot produce evidence
    # for - no condition is red for an unexplained reason.
    assert body["every_unmet_condition_is_explained"] is True
    assert body["invariant_failures"] == []


def test_the_health_route_leaves_no_cycle_row_behind(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/orchestration/health",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["health_probe_rolled_back"] is True
    assert body["health_probe_cycle_rows_left_behind"] == 0


def test_the_trigger_route_reports_the_next_wake(client):
    soh.ensure_org(DEMO, "demo")
    body = client.get(
        f"/v1/nf/demo/orgs/{DEMO}/orchestration/trigger",
        headers=soh.session_headers(DEMO),
    ).json()
    assert body["state"] in TRIGGER_STATES
    assert body["next_wake_at"]
    assert body["a_trigger_is_not_a_source_check"] is True
    assert body["invariant_failures"] == []


def test_every_write_in_the_routes_is_inside_a_savepoint():
    module = (
        REPO_ROOT / "src/nativeforge/api/source_collection_orchestration_routes.py"
    ).read_text()
    assert module.count("begin_nested()") == 2
    assert module.count("savepoint.rollback()") == 2


# --------------------------------------------------------- 159G the process


def test_the_script_exists_and_defaults_to_one_shot():
    body = SCRIPT.read_text()
    assert "--once" in body
    assert "run one cycle and exit (default)" in body


def test_the_script_has_no_unbounded_loop():
    """Parsed, not scanned: the docstring says `while True` to rule it out."""
    tree = ast.parse(SCRIPT.read_text())
    unbounded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.While)
        and isinstance(node.test, ast.Constant)
        and node.test.value is True
    ]
    assert unbounded == []
    # Falsifiable: there IS a while loop, and it has a real condition.
    whiles = [node for node in ast.walk(tree) if isinstance(node, ast.While)]
    assert len(whiles) == 1
    assert "_STOP_REQUESTED" in ast.unparse(whiles[0].test)


def test_the_script_handles_both_stop_signals():
    body = SCRIPT.read_text()
    assert "signal.SIGINT" in body
    assert "signal.SIGTERM" in body


def test_the_script_takes_no_secret_on_the_command_line():
    tree = ast.parse(SCRIPT.read_text())
    arguments = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and "add_argument" in ast.unparse(node.func)
        and node.args
        and isinstance(node.args[0], ast.Constant)
    ]
    for argument in arguments:
        lowered = str(argument).lower()
        for forbidden in ("secret", "token", "password", "api-key", "credential"):
            assert forbidden not in lowered, argument


def test_the_script_resolves_a_clock_so_its_default_invocation_works():
    """It did not, and printed a report of nulls instead."""
    body = SCRIPT.read_text()
    assert "_resolve_now" in body
    assert "clock_source" in body


def test_the_script_compiles():
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# ------------------------------------------------------------ 159H the unit


def test_the_unit_exists_and_is_not_enabled_by_anything_in_the_repo():
    body = UNIT.read_text()
    assert "NOT INSTALLED, NOT" in body
    # No script in the repository enables it.
    hits = subprocess.run(
        [
            "grep",
            "-rl",
            "systemctl --user enable nativeforge-source-orchestrator",
            str(REPO_ROOT / "scripts"),
        ],
        capture_output=True,
        text=True,
    )
    assert hits.stdout.strip() == ""


def test_the_unit_carries_no_credential():
    body = UNIT.read_text()
    for forbidden in ("GOCSPX-", "SECRET=", "TOKEN=", "PASSWORD=", "API_KEY="):
        assert forbidden not in body


def test_the_unit_restarts_on_failure_not_always():
    """It is supposed to exit zero after --max-cycles."""
    body = UNIT.read_text()
    assert "Restart=on-failure" in body
    assert "Restart=always" not in body


def test_the_unit_runs_the_orchestrator_bounded():
    body = UNIT.read_text()
    assert "run_source_collection_orchestrator.py" in body
    assert "--max-cycles" in body


# -------------------------------------------------------- 159M the artifacts


def test_every_declared_artifact_is_written(tmp_path):
    result = write_orchestration_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(ARTIFACT_FILES)
    assert orchestration_artifact_invariant_failures(result) == []


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    for name, body in build_orchestration_artifacts().items():
        on_disk = (REPO_ROOT / ARTIFACT_DIR / name).read_text()
        assert on_disk == body, f"{name} is stale; run .git/regen2.py"


def test_the_artifact_writer_opens_no_database():
    module = (
        REPO_ROOT
        / "src/nativeforge/services/source_orchestration_artifact_gate159_service.py"
    ).read_text()
    for forbidden in ("create_engine", "SessionLocal", "get_settings"):
        assert forbidden not in module


def test_the_monitoring_artifact_still_says_nothing_is_live():
    status = json.loads(
        build_orchestration_artifacts()["source_monitoring_status.json"]
    )
    assert status["source_monitoring_live"] is False
    assert status["approved_source_count"] == 0
    assert status["jobs_completed"] == 0
    assert status["orchestrator_unit_enabled_by_this_gate"] is False
    assert status["a_trigger_is_not_a_source_check"] is True


def test_the_artifacts_carry_no_secret_shape():
    for body in build_orchestration_artifacts().values():
        assert "GOCSPX-" not in body
        assert "nf_session=" not in body
        assert "BEGIN PRIVATE KEY" not in body


# ------------------------------------------------ 159K the verifier contract


def test_the_verifier_exists_and_is_executable():
    script = REPO_ROOT / "scripts/verify_nativeforge_source_orchestration_runtime.sh"
    assert script.exists()
    assert script.stat().st_mode & 0o111


def test_the_verifier_is_registered():
    from nativeforge.services.readiness_verifier_registry_service import (
        build_verifier_registry,
    )

    registry = build_verifier_registry()
    assert "source_orchestration_runtime" in registry["verifier_names"]
    entry = next(
        e
        for e in registry["verifiers"]
        if e["verifier"] == "source_orchestration_runtime"
    )
    assert entry["lane"] == "orchestration_runtime_ready"
    assert entry["gate"] == "159"


def test_the_verifier_runs_its_phases_in_separate_processes():
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_orchestration_runtime.sh"
    ).read_text()
    assert "scripts/_g159_phase_a.py" in body
    assert "scripts/_g159_phase_b.py" in body


def test_the_verifier_cleans_up_after_the_final_write():
    """Gate 157 cleaned up and then invoked a script that wrote 100 rows."""
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_orchestration_runtime.sh"
    ).read_text()
    cleanup = body.index("_g159_phase_cleanup.py")
    for phase in ("_g159_phase_a.py", "_g159_phase_b.py", "_g159_phase_c.py",
                  "_g159_phase_health.py"):
        assert body.index(phase) < cleanup, f"{phase} runs after cleanup"


def test_the_verifier_fails_a_cleanup_that_deleted_nothing():
    body = (
        REPO_ROOT / "scripts/verify_nativeforge_source_orchestration_runtime.sh"
    ).read_text()
    assert "cleanup_had_something_to_clean" in body
    assert "a cleanup that deletes nothing is untested" in body


@pytest.mark.parametrize(
    "phase",
    [
        "_g159_phase_a.py",
        "_g159_phase_b.py",
        "_g159_phase_c.py",
        "_g159_phase_health.py",
        "_g159_phase_cleanup.py",
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


@pytest.mark.parametrize("module", GATE_159_MODULES)
def test_no_gate_159_module_imports_an_http_client(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("import requests", "import httpx", "urllib.request", "aiohttp"):
        assert forbidden not in body, f"{module} reaches the network"


@pytest.mark.parametrize("module", GATE_159_MODULES)
def test_no_gate_159_module_starts_a_thread_or_a_process(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("threading.Thread", "subprocess.", "multiprocessing"):
        assert forbidden not in body, f"{module} starts something"


@pytest.mark.parametrize("module", GATE_159_MODULES)
def test_no_gate_159_module_sends_email_or_touches_an_object_store(module):
    body = (REPO_ROOT / module).read_text()
    for forbidden in ("smtplib", "sendgrid", "boto3", "s3_client", "send_email"):
        assert forbidden not in body, f"{module} mentions {forbidden}"


def test_no_gate_159_module_advances_last_checked_at():
    """Writing it would assert that a source check occurred."""
    for module in GATE_159_MODULES:
        body = (REPO_ROOT / module).read_text()
        tree = ast.parse(body)
        # Parsed: several of these modules discuss last_checked_at in prose to
        # explain why they must not write it.
        assigned = {
            keyword.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg
        }
        assert "last_checked_at" not in assigned, module


def test_the_orchestrator_does_not_build_a_second_job_store():
    """Gate 158 owns the job lifecycle; this gate composes it."""
    runtime = (
        REPO_ROOT
        / "src/nativeforge/services/source_collection_orchestration_runtime_service.py"
    ).read_text()
    assert "run_scheduler_cycle" in runtime
    assert "count_backlog" in runtime
    # No table of its own for jobs.
    assert "nf_source_collection_jobs" not in runtime
    assert "sa.Table(" not in runtime
