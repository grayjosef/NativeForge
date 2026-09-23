"""Gate 172: the source fleet's operating system.

Hermetic. Nothing here opens a socket and nothing writes to the real database;
every test runs on in-process fixtures against the services themselves.

These are the permanent regressions for a fleet that has to reach thousands of
heterogeneous sources without a human watching each one. Two kinds live here:

1.  Product invariants - a revoked authorization stops collection BEFORE
    transport, an unmeasured dimension is not healthy, a breaking schema
    change asks for a human instead of being adapted to.

2.  Instrument invariants - Gate 172 found four separate cases where the
    measurement was wrong while the system was right, so the fixtures that
    classify a condition are checked for actually FEEDING that condition into
    the model. A green matrix is meaningless if the fixture does not reach the
    code it claims to exercise.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

import pytest

from nativeforge.services.source_fleet_drift_service import (
    BREAKING_DRIFT,
    INSUFFICIENT_HISTORY,
    LOW,
    NORMAL,
    REVIEW_REQUIRED_CLASSES,
    SIGNAL_CLASS,
    assess_volume,
    describe_drift_model,
    detect_drift,
)
from nativeforge.services.source_fleet_expectation_service import (
    CADENCES,
    UNSCHEDULED,
    evaluate_freshness,
    resolve_expectation,
)
from nativeforge.services.source_fleet_failure_taxonomy_service import (
    AUTHORIZATION_REFUSED,
    FAILURE_DIMENSION,
    FAILURE_TYPES,
    MAX_BACKOFF_SECONDS,
    NO_RETRY,
    POLICY_TYPES,
    RATE_LIMIT,
    RETRY_BY_TYPE,
    ROBOTS_RESTRICTED,
    SCHEMA_CHANGED,
    apply_outcome,
    classify_failure,
    next_backoff_seconds,
    taxonomy_invariant_failures,
)
from nativeforge.services.source_fleet_operational_state_service import (
    AUTHORIZATION_REQUIRED,
    BLOCKED,
    DEGRADED,
    DEGRADED_DIM,
    DISABLED,
    FAILED_DIM,
    FAILING,
    HEALTH_DIMENSIONS,
    HEALTHY,
    OK,
    OPERATIONAL_STATES,
    RATE_LIMITED,
    RETIRED,
    STATE_MEANINGS,
    UNKNOWN,
    UNKNOWN_DIM,
    blank_dimensions,
    derive_operational_state,
    state_invariant_failures,
)
from nativeforge.services.source_fleet_operations_event_service import (
    ALERT_CONTRACT,
    EVENT_SEVERITY,
    EVENT_TYPES,
    NO_ALERT_STATES,
    STATE_TO_EVENT,
    build_event_id,
    plan_alert,
    plan_transition,
)
from nativeforge.services.source_fleet_read_model_service import (
    build_fleet_health,
    build_source_row,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
NOW = dt.datetime(2026, 9, 23, 12, 0, tzinfo=dt.UTC)


def _row(**overrides: object) -> dict:
    """A healthy source, so each test changes exactly one thing."""
    base = dict(
        source_id="nf172.test",
        adapter_key="federal_register_documents_json",
        authorization_state="live_opted_in",
        activation_state="activated",
        last_attempt_at=NOW - dt.timedelta(minutes=30),
        last_success_at=NOW - dt.timedelta(minutes=30),
        last_payload_at=NOW - dt.timedelta(minutes=30),
        last_observation_at=NOW - dt.timedelta(minutes=30),
        last_useful_change_at=NOW - dt.timedelta(hours=2),
        payload_count=1,
        observation_count=20,
        canonical_count=20,
        robots_body_retained=True,
        records_read=20,
        previous_record_counts=[20, 21, 19, 20],
        now=NOW,
        fleet_globals={
            "backlog_health": OK,
            "scheduler_health": OK,
            "worker_health": OK,
        },
    )
    base.update(overrides)
    return build_source_row(**base)  # type: ignore[arg-type]


# ===================== the state model ==============================


def test_the_baseline_fixture_is_actually_healthy():
    """If this drifts, every test below is asserting against the wrong thing."""
    row = _row()
    assert row["operational_state"] == HEALTHY, row["state_detail"]["reasons"]
    fleet = build_fleet_health(
        rows=[row], computed_at=NOW, now=NOW, registered_sources=1
    )
    assert read_model_invariant_failures(rows=[row], fleet=fleet) == []


def test_an_unmeasured_dimension_is_not_healthy():
    """UNKNOWN is the honest answer. Defaulting it to OK is how a fleet of

    5,000 sources reports itself green while collecting nothing.
    """
    blank = blank_dimensions()
    assert set(blank) == set(HEALTH_DIMENSIONS)
    assert set(blank.values()) == {UNKNOWN_DIM}
    assert derive_operational_state(dimensions=blank)["operational_state"] == UNKNOWN


def test_every_state_has_a_distinct_documented_meaning():
    assert len(set(OPERATIONAL_STATES)) == len(OPERATIONAL_STATES)
    assert set(STATE_MEANINGS) == set(OPERATIONAL_STATES)
    assert len(set(STATE_MEANINGS.values())) == len(OPERATIONAL_STATES)


def test_operator_intent_outranks_measurement():
    """A disabled source is not failing - nobody is trying."""
    broken = dict.fromkeys(HEALTH_DIMENSIONS, FAILED_DIM)
    assert (
        derive_operational_state(dimensions=broken, disabled=True)["operational_state"]
        == DISABLED
    )
    assert (
        derive_operational_state(dimensions=broken, retired=True)["operational_state"]
        == RETIRED
    )


def test_rate_limiting_is_not_failure():
    """Treating a slow-down request as failure is how a fleet earns a block."""
    dimensions = dict.fromkeys(HEALTH_DIMENSIONS, OK)
    state = derive_operational_state(
        dimensions=dimensions, rate_limited=True, consecutive_failures=9
    )
    assert state["operational_state"] == RATE_LIMITED


def test_health_dimensions_are_independent():
    """One broken dimension must not erase the other ten.

    The fleet read model exists to tell an operator WHICH part of a source is
    broken. A model that collapses to a single verdict cannot.
    """
    for dimension in HEALTH_DIMENSIONS:
        dimensions = dict.fromkeys(HEALTH_DIMENSIONS, OK)
        dimensions[dimension] = DEGRADED_DIM
        state = derive_operational_state(dimensions=dimensions)
        others = {
            name: value
            for name, value in state["dimensions"].items()
            if name != dimension
        }
        assert set(others.values()) == {OK}, f"{dimension} contaminated {others}"
        assert state["operational_state"] == DEGRADED


def test_a_named_gap_degrades_the_source_rather_than_being_swallowed():
    """The BIA robots gap. A known unknown is DEGRADED, never a quiet HEALTHY."""
    dimensions = dict.fromkeys(HEALTH_DIMENSIONS, OK)
    state = derive_operational_state(
        dimensions=dimensions, known_gaps=["robots_response_body_not_retained"]
    )
    assert state["operational_state"] == DEGRADED
    assert state["known_gaps"] == ["robots_response_body_not_retained"]
    assert state_invariant_failures(state) == []


# ============== authorization: the 172S boundary ====================


def test_a_revoked_authorization_blocks_transport():
    """The defect this gate found.

    The read model could not distinguish "authorization refused" from
    "authorization not yet measured", so a refusal classified as FAILING with
    transport still permitted - which is the single outcome that must never
    happen. Revoked means AUTHORIZATION_REQUIRED and transport blocked.
    """
    row = _row(authorization_revoked=True, transport_blocked=True)
    assert row["operational_state"] == AUTHORIZATION_REQUIRED
    assert row["authorization_health"] == FAILED_DIM
    assert row["state_detail"]["is_collecting"] is False


def test_revoked_is_not_the_same_as_unmeasured():
    """Three answers, not two: granted, REFUSED, and nobody has asked."""
    revoked = _row(authorization_revoked=True, transport_blocked=True)
    unmeasured = _row(authorization_state=None, activation_state=None)
    assert revoked["authorization_health"] == FAILED_DIM
    assert unmeasured["authorization_health"] == UNKNOWN_DIM
    assert revoked["operational_state"] != unmeasured["operational_state"]


def test_a_robots_restriction_is_blocked_not_failing():
    """A publisher restriction is a policy answer, not a broken source."""
    row = _row(transport_blocked=True)
    assert row["operational_state"] == BLOCKED
    assert row["state_detail"]["is_collecting"] is False


# ================ the failure taxonomy ==============================


def test_every_failure_type_has_one_dimension_and_one_retry_rule():
    assert set(FAILURE_DIMENSION) == set(FAILURE_TYPES)
    assert set(RETRY_BY_TYPE) == set(FAILURE_TYPES)
    assert set(FAILURE_DIMENSION.values()) <= set(HEALTH_DIMENSIONS)


@pytest.mark.parametrize("failure_type", sorted(POLICY_TYPES))
def test_a_policy_refusal_is_never_retried(failure_type):
    """Retrying a refusal is how an access restriction becomes a ban."""
    strategy, _ = RETRY_BY_TYPE[failure_type]
    assert strategy == NO_RETRY
    assert next_backoff_seconds(strategy=strategy, attempt=1) is None


@pytest.mark.parametrize("failure_type", sorted(FAILURE_TYPES))
def test_every_retry_is_bounded(failure_type):
    """An uncapped exponential backoff reaches days; a source that recovers in

    an hour would not be retried until the following week.
    """
    strategy, _ = RETRY_BY_TYPE[failure_type]
    for attempt in range(1, 20):
        delay = next_backoff_seconds(
            strategy=strategy, attempt=attempt, retry_after=10**9
        )
        assert delay is None or 0 <= delay <= MAX_BACKOFF_SECONDS


def test_classification_never_reads_a_message():
    """One failure, one type, decided from structured facts."""
    refused = classify_failure(authorization_refused=True)
    assert refused["failure_type"] == AUTHORIZATION_REFUSED
    assert taxonomy_invariant_failures(refused) == []

    restricted = classify_failure(robots_restricted=True)
    assert restricted["failure_type"] == ROBOTS_RESTRICTED

    limited = classify_failure(http_status=429)
    assert limited["failure_type"] == RATE_LIMIT


def test_a_recovery_resets_the_streak_but_never_erases_the_history():
    """ "This source has failed 40 times this month" is the fact that decides

    whether to keep it, so a success must not delete it.
    """
    state = None
    for _ in range(3):
        state = apply_outcome(
            previous=state, succeeded=False, failure_type=SCHEMA_CHANGED, now=NOW
        )
    assert state["consecutive_failures"] == 3
    assert state["total_failures"] == 3

    recovered = apply_outcome(previous=state, succeeded=True, now=NOW)
    assert recovered["consecutive_failures"] == 0
    assert recovered["total_failures"] == 3
    assert recovered["recovered_now"] is True
    assert recovered["first_failure_at"] == state["first_failure_at"]


def test_consecutive_failures_become_failing_only_at_the_threshold():
    dimensions = dict.fromkeys(HEALTH_DIMENSIONS, OK)
    below = derive_operational_state(dimensions=dimensions, consecutive_failures=2)
    at = derive_operational_state(dimensions=dimensions, consecutive_failures=3)
    assert below["operational_state"] != FAILING
    assert at["operational_state"] == FAILING


# ==================== freshness and the SLA =========================


def test_a_source_that_has_never_run_is_not_stale():
    """It is unmeasured. A source with no history has no freshness to lose."""
    expectation = resolve_expectation(adapter_key="bia_program_page_html")
    freshness = evaluate_freshness(expectation=expectation, now=NOW)
    assert freshness["never_collected"] is True
    assert freshness["is_stale"] is False


def test_an_unscheduled_cadence_carries_no_freshness_sla():
    """Otherwise every manual source is permanently overdue."""
    for cadence in sorted(UNSCHEDULED):
        expectation = resolve_expectation(
            source_override={"collection_cadence": cadence}
        )
        assert expectation["freshness_sla_seconds"] is None
        assert expectation["is_scheduled"] is False
        freshness = evaluate_freshness(
            expectation=expectation,
            last_success_at=NOW - dt.timedelta(days=400),
            now=NOW,
        )
        assert freshness["is_stale"] is False


def test_the_expectation_resolves_through_three_layers_in_order():
    fleet = resolve_expectation()
    adapter = resolve_expectation(adapter_key="bia_program_page_html")
    override = resolve_expectation(
        adapter_key="bia_program_page_html",
        source_override={"collection_cadence": "hourly"},
    )
    assert fleet["resolved_from"] == ["fleet_default"]
    assert "adapter_default:bia_program_page_html" in adapter["resolved_from"]
    assert override["resolved_from"][-1] == "source_override"
    assert override["collection_cadence"] == "hourly"
    assert adapter["collection_cadence"] in CADENCES


def test_succeeding_and_useless_is_distinguishable_from_succeeding():
    """A source that returns 200 forever and never changes is a real failure

    mode, and it is invisible to every transport-level check.
    """
    expectation = resolve_expectation(
        source_override={"max_payload_silence_seconds": 3600}
    )
    silent = evaluate_freshness(
        expectation=expectation,
        last_success_at=NOW - dt.timedelta(minutes=5),
        last_useful_change_at=NOW - dt.timedelta(days=30),
        now=NOW,
    )
    assert silent["is_stale"] is False
    assert silent["useful_intelligence_silent"] is True


def test_freshness_is_not_derived_from_scheduler_lag():
    """A punctual source can still be stale: it ran on time and returned

    nothing new. Deriving one from the other hides that entirely.
    """
    row = _row(
        queue_delay_seconds=0,
        last_attempt_at=NOW - dt.timedelta(minutes=1),
        last_success_at=NOW - dt.timedelta(days=90),
        adapter_key="grants_gov_search2_json",
    )
    assert row["scheduler_health"] in {OK, UNKNOWN_DIM}
    assert row["freshness"]["is_stale"] is True


# ========================= drift ====================================


def test_a_breaking_schema_change_asks_for_a_human():
    """An adapter is never rewritten automatically. The alternative is a

    parser that silently adapts to a change nobody reviewed and writes
    plausible wrong records into the canonical store.
    """
    assert describe_drift_model()["adapters_are_never_auto_rewritten"] is True
    assert BREAKING_DRIFT in REVIEW_REQUIRED_CLASSES
    breaking = [s for s, c in SIGNAL_CLASS.items() if c == BREAKING_DRIFT]
    assert breaking, "no signal can ever be breaking"

    dimensions = dict.fromkeys(HEALTH_DIMENSIONS, OK)
    state = derive_operational_state(dimensions=dimensions, review_required=True)
    assert state["operational_state"] == "REVIEW_REQUIRED"


def test_a_changed_content_type_is_detected_against_the_contract():
    contract = {"expected_content_types": ["application/json"]}
    drift = detect_drift(contract=contract, observed_content_type="text/html")
    fired = {signal["signal"] for signal in drift["signals"]}
    assert "content_type_changed" in fired
    assert drift["drift_class"] != "NO_DRIFT"


def test_the_first_run_is_never_a_volume_anomaly():
    """One observation is not a baseline."""
    assert assess_volume(records_read=0, previous_record_counts=[])["state"] == (
        INSUFFICIENT_HISTORY
    )
    assert assess_volume(records_read=999, previous_record_counts=[10])["state"] == (
        INSUFFICIENT_HISTORY
    )


def test_volume_baselines_are_per_source_not_fleet_wide():
    """A source that publishes three records a week is not anomalous because

    another source publishes three thousand a day.
    """
    small = assess_volume(records_read=3, previous_record_counts=[3, 3, 4, 3])
    large = assess_volume(records_read=3, previous_record_counts=[3000, 2900, 3100])
    assert small["state"] == NORMAL
    assert large["state"] == LOW
    assert describe_drift_model()["baselines_are_per_source"] is True


# =============== events and the operator contract ===================


def test_an_event_that_is_not_a_transition_is_not_an_event():
    """Returning None for "no change" is the design. A caller that has to

    filter afterwards will eventually forget to, and the events table becomes
    a poll log nobody can read.
    """
    assert (
        plan_transition(source_id="s", previous_state=HEALTHY, current_state=HEALTHY)
        is None
    )
    changed = plan_transition(
        source_id="s", previous_state=HEALTHY, current_state=FAILING
    )
    assert changed is not None
    assert changed["from_state"] != changed["to_state"]


def test_a_first_sighting_is_not_a_recovery():
    """Without this, every source in the fleet emits SOURCE_RECOVERED the

    first time health is ever computed.
    """
    assert (
        plan_transition(source_id="s", previous_state=None, current_state=HEALTHY)
        is None
    )


def test_the_event_id_is_deterministic_for_the_same_transition():
    """Idempotence is a property of the identity, not of the write path."""
    args = dict(
        source_id="s",
        event_type="SOURCE_BECAME_FAILING",
        from_state=HEALTHY,
        to_state=FAILING,
    )
    assert build_event_id(**args) == build_event_id(**args)
    assert build_event_id(**args) != build_event_id(**{**args, "to_state": BLOCKED})


def test_the_event_vocabulary_matches_the_migrations_check_constraint():
    """A value the service emits and the CHECK rejects is an IntegrityError at

    the exact moment an operator most needs the event written. The two lists
    live in different files, so nothing but this keeps them equal.
    """
    text = (
        REPO / "alembic" / "versions" / "0058_source_operations_events.py"
    ).read_text(encoding="utf-8")
    block = text.split("EVENT_TYPES = (")[1].split(")")[0]
    in_migration = set(re.findall(r'"([A-Z_]+)"', block))

    assert in_migration == set(EVENT_TYPES)
    assert set(STATE_TO_EVENT.values()) <= set(EVENT_TYPES)


def test_every_event_type_and_alert_condition_carries_a_contract():
    assert set(EVENT_SEVERITY) == set(EVENT_TYPES)
    for condition, (severity, action) in ALERT_CONTRACT.items():
        assert severity in {"INFO", "WARNING", "CRITICAL"}, condition
        assert action and action.strip(), condition


def test_a_degraded_or_unmeasured_source_does_not_page_an_operator():
    """Alert fatigue is the failure mode that makes an operations layer

    useless. DEGRADED is a dashboard row, not a page.
    """
    assert NO_ALERT_STATES == frozenset({DEGRADED, UNKNOWN, RETIRED})
    for state in sorted(NO_ALERT_STATES):
        assert plan_alert(source_id="s", operational_state=state) is None
    assert plan_alert(source_id="s", operational_state=AUTHORIZATION_REQUIRED)


# ============= the health of the health system ======================


def test_the_fleet_reconciles_registered_against_evaluated():
    rows = [_row(source_id=f"nf172.test.{n}") for n in range(3)]
    fleet = build_fleet_health(
        rows=rows, computed_at=NOW, now=NOW, registered_sources=3
    )
    assert sum(fleet["counts_by_state"].values()) == 3
    assert fleet["self_health_ok"] is True


def test_an_unreconciled_fleet_reports_itself_unhealthy():
    """A health system that cannot notice it skipped 2,000 sources is worse

    than none, because it is trusted.
    """
    rows = [_row(source_id="nf172.test.only")]
    fleet = build_fleet_health(
        rows=rows, computed_at=NOW, now=NOW, registered_sources=5000
    )
    assert fleet["self_health_ok"] is False


def test_an_unclassified_failure_is_caught_by_self_health():
    """A source with failures and no failure type means the taxonomy was

    bypassed somewhere. This is how that gets noticed.
    """
    row = _row(consecutive_failures=2, latest_failure_type=None)
    fleet = build_fleet_health(
        rows=[row], computed_at=NOW, now=NOW, registered_sources=1
    )
    assert fleet["self_health_ok"] is False


def test_stale_health_is_not_current_health():
    rows = [_row()]
    fleet = build_fleet_health(
        rows=rows,
        computed_at=NOW - dt.timedelta(hours=6),
        now=NOW,
        registered_sources=1,
    )
    assert fleet["self_health_ok"] is False


# ================= the instruments themselves =======================
#
# Gate 172's own lesson: a green matrix is meaningless if the fixture does not
# feed the classified condition into the actual model. These four tests exist
# because four fixtures in this gate did exactly that.


def test_the_failure_matrix_feeds_its_classification_into_the_model():
    """The matrix first passed `live_opted_in` for a ROBOTS_RESTRICTED row, so

    every classification produced the same authorization dimension and the
    matrix went green without exercising a single branch. The fixture must
    DERIVE the model's inputs from the classification.
    """
    text = (REPO / "scripts" / "_g172_phase_fleet_operations.py").read_text(
        encoding="utf-8"
    )
    assert "authorization_revoked=" in text
    assert "transport_blocked=" in text

    # And the model must actually respond to them: same source, two
    # classifications, two different states.
    refused = _row(authorization_revoked=True, transport_blocked=True)
    restricted = _row(transport_blocked=True)
    healthy = _row()
    states = {
        refused["operational_state"],
        restricted["operational_state"],
        healthy["operational_state"],
    }
    assert len(states) == 3, states


def test_the_starvation_detector_is_falsifiable():
    """A fairness fixture that cannot show starvation proves nothing.

    The first version of this simulation produced identical output for strict
    priority and for aging, because it had no continuous arrivals - the one
    condition under which starvation appears. Running the real phase: the
    aging scheduler must be clean AND the strict-priority scheduler must
    starve, or the detector is not measuring anything.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g172_phase_scheduler_safety.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["healthy_schedule_has_no_starvation"] is True
    assert report["broken_schedule_detects_starvation"] is True
    assert report["broken_schedule_starved_classes"]
    assert report["network_attempts_during_this_phase"] == 0


def test_the_access_path_audit_scopes_its_queries_the_way_the_service_does():
    """Every operational index on these tables is prefixed by organization_id.

    The first audit left that column out, so the planner could not use any of
    them and reported five scans - a finding about the audit, not the schema.
    It also compared `str(UUID)` against a column SQLAlchemy stores as 32 hex
    characters without dashes, which returned zero rows while still printing
    query plans.
    """
    text = (REPO / "scripts" / "_g172_phase_fleet_scale.py").read_text(encoding="utf-8")
    assert "organization_id = ?" in text
    assert "ORG.hex" in text, "the audit must bind the value the column stores"
    assert "selectivity" in text, "the index rule must be selectivity-aware"


def test_the_sequential_isolation_phase_uses_two_different_fixtures():
    """Proving "B after A equals B alone" is vacuous if A and B are the same

    fixture. The phase asserts they differ; this asserts the phase asserts it.
    """
    text = (REPO / "scripts" / "_g172_phase_sequential_isolation.py").read_text(
        encoding="utf-8"
    )
    assert "a_and_b_are_different_fixtures" in text
    assert "subprocess.run" in text, "each run must be its own process"


def test_the_gate172_verifier_reports_every_required_fact():
    """The closeout contract. If a fact stops being emitted, this fails rather

    than the fact quietly disappearing from a green run.
    """
    text = (
        REPO / "scripts" / "verify_nativeforge_source_fleet_health_gate172.sh"
    ).read_text(encoding="utf-8")
    for fact in (
        "source_operational_state_model_ready=true",
        "health_dimensions_independent=true",
        "authorization_revocation_blocks_transport=true",
        "critical_queries_indexed=true",
        "source_health_sequential_isolation=true",
        "sequential_lineage_isolation=true",
        "generic_layer_source_leaks=0",
        "network_requests=0",
        "fixture_residue=0",
        "gate172_ready=true",
    ):
        assert fact in text, fact
