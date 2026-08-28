"""Gate 98 - scheduler decision layer, circuit breaker, and readiness.

Hermetic. Nothing here fetches, schedules, enqueues, or executes a check, and a
number of these tests exist specifically to prove that.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from nativeforge.services.source_check_run_contract_service import (
    CHECK_MODES,
    CHECK_RUN_STATUSES,
    CONTRACT_FIELDS,
    COUNT_FIELDS,
    PROHIBITED_FIELD_NAMES,
    build_check_run_record,
    check_run_invariant_failures,
    contract_shape,
    summarise_check_runs,
)
from nativeforge.services.source_circuit_breaker_service import (
    CIRCUIT_STATUSES,
    DEFAULT_BREAKER_THRESHOLD,
    DEFAULT_COOLDOWN_SECONDS,
    MANUAL_HOLDING,
    SCHEDULING_PERMITTED_STATUSES,
    SINGLE_PROBE_STATUSES,
    apply_check_outcome,
    circuit_invariant_failures,
    evaluate_circuit,
)
from nativeforge.services.source_crawler_governance_service import (
    CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
)
from nativeforge.services.source_schedule_decision_service import (
    ENQUEUE_PERMITTED_STATUSES,
    REQUIREMENT_KEYS,
    SCHEDULE_STATUSES,
    evaluate_schedule,
    schedule_invariant_failures,
    summarise_schedule,
)
from nativeforge.services.source_scheduler_readiness_artifact_service import (
    ARTIFACT_DIR,
    ARTIFACT_NAMES,
    DECLARATION_KEYS,
    FALSE_DECLARATION_KEYS,
    SchedulerReadinessArtifactError,
    artifact_claim_failures,
    build_readiness_bundle,
    render_readiness_summary,
    write_scheduler_readiness_artifacts,
)
from nativeforge.services.source_scheduler_readiness_service import (
    COMPONENT_KEYS,
    RUNTIME_COMPONENT_KEYS,
    SCHEDULER_RUNTIME_PACKAGES,
    build_scheduler_readiness,
    detect_background_worker,
    detect_periodic_trigger,
    detect_scheduler_runtime,
    scheduler_readiness_invariant_failures,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

NOW = "2026-01-01T12:00:00+00:00"
PAST = "2026-01-01T09:00:00+00:00"
FUTURE = "2026-06-01T09:00:00+00:00"
RECENT_FAILURE = "2026-01-01T11:45:00+00:00"
OLD_FAILURE = "2026-01-01T10:00:00+00:00"

GATE98_SERVICES = (
    "source_schedule_decision_service",
    "source_circuit_breaker_service",
    "source_check_run_contract_service",
    "source_scheduler_readiness_service",
    "source_scheduler_readiness_artifact_service",
)

CLEARED_SCHEDULE = dict(
    next_check_due_at=PAST,
    collector_status="active",
    activation_status="activation_allowed",
    monitoring_status="enabled",
    terms_status="NO_REVIEW_REQUIRED",
    human_review_status="not_required",
    circuit_status="closed",
    production_raw_payload_store_available=True,
)

PAYLOAD_ID_A = hashlib.sha256(b"payload-a").hexdigest()
PAYLOAD_ID_B = hashlib.sha256(b"payload-b").hexdigest()


def _schedule(**overrides):
    return evaluate_schedule(
        source_id="s", now=NOW, **{**CLEARED_SCHEDULE, **overrides}
    )


# --------------------------------------------------------------------------
# 98B - schedule decision
# --------------------------------------------------------------------------


def test_schedule_defaults_to_unknown_and_blocks() -> None:
    decision = evaluate_schedule(source_id="s", now=NOW)
    assert decision["schedule_status"] == "unknown"
    assert decision["safe_to_enqueue"] is False
    assert decision["blocked_reasons"]
    assert not schedule_invariant_failures(decision)


def test_a_fully_cleared_due_source_may_be_enqueued() -> None:
    decision = _schedule()
    assert decision["schedule_status"] == "due_and_safe_to_enqueue"
    assert decision["safe_to_enqueue"] is True
    assert decision["requirements_missing"] == []
    assert not schedule_invariant_failures(decision)


def test_the_cleared_case_is_not_vacuous() -> None:
    """If nothing could ever be enqueued, every block test below proves nothing."""
    assert _schedule()["safe_to_enqueue"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collector_status", "not_active"),
        ("collector_status", "halted"),
        ("collector_status", "activating"),
        ("activation_status", "activation_blocked"),
        ("activation_status", "activation_requires_human_review"),
        ("activation_status", "activation_unknown"),
        ("monitoring_status", "not_started"),
        ("monitoring_status", "unknown"),
        ("terms_status", "TERMS_REVIEW_REQUIRED"),
        ("terms_status", "HUMAN_REVIEW_ONLY"),
        ("terms_status", "UNKNOWN"),
        ("human_review_status", "pending"),
        ("human_review_status", "rejected"),
        ("human_review_status", "unknown"),
        ("circuit_status", "open"),
        ("circuit_status", "manual_hold"),
        ("circuit_status", "unknown"),
        ("production_raw_payload_store_available", False),
    ],
)
def test_each_blocking_input_prevents_enqueue(field: str, value: object) -> None:
    decision = _schedule(**{field: value})
    assert decision["safe_to_enqueue"] is False
    assert decision["blocked_reasons"]
    assert not schedule_invariant_failures(decision)


def test_an_unrecognised_status_blocks_rather_than_permits() -> None:
    for field in (
        "collector_status",
        "activation_status",
        "monitoring_status",
        "terms_status",
        "human_review_status",
        "circuit_status",
    ):
        decision = _schedule(**{field: "something_nobody_defined"})
        assert decision["safe_to_enqueue"] is False, field


def test_a_future_due_date_is_not_due() -> None:
    decision = _schedule(next_check_due_at=FUTURE)
    assert decision["schedule_status"] == "not_due"
    assert decision["due_for_check"] is False
    assert decision["safe_to_enqueue"] is False


@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_missing_due_date_is_unknown_not_immediate(value: object) -> None:
    """The tempting reading - never checked, so check now - is backwards."""
    decision = _schedule(next_check_due_at=value)
    assert decision["schedule_status"] == "unknown"
    assert decision["due_for_check"] is False
    assert decision["safe_to_enqueue"] is False
    assert decision["human_review_required"] is True
    assert "next_check_due_at_absent" in decision["blocked_reasons"]


def test_a_naive_due_date_against_an_aware_now_is_not_derivable() -> None:
    decision = _schedule(next_check_due_at="2026-01-01T09:00:00")
    assert decision["due_derivable"] is False
    assert decision["schedule_status"] == "unknown"
    assert decision["safe_to_enqueue"] is False


@pytest.mark.parametrize("value", ["disabled", "paused"])
def test_disabled_monitoring_reports_disabled(value: str) -> None:
    decision = _schedule(monitoring_status=value)
    assert decision["schedule_status"] == "disabled"
    assert decision["safe_to_enqueue"] is False


def test_due_never_implies_safe_to_execute_now() -> None:
    decision = _schedule()
    assert decision["due_for_check"] is True
    assert decision["safe_to_enqueue"] is True
    assert decision["safe_to_execute_now"] is False


def test_no_decision_ever_reports_safe_to_execute_now() -> None:
    for value in ("not_active", "active", "halted"):
        assert _schedule(collector_status=value)["safe_to_execute_now"] is False


def test_schedule_status_vocabulary_is_closed() -> None:
    for value in (None, "active", "x"):
        assert _schedule(collector_status=value)["schedule_status"] in SCHEDULE_STATUSES


def test_every_requirement_is_accounted_for_exactly_once() -> None:
    decision = evaluate_schedule(source_id="s", now=NOW)
    satisfied = set(decision["requirements_satisfied"])
    missing = set(decision["requirements_missing"])
    assert not satisfied & missing
    assert satisfied | missing == set(REQUIREMENT_KEYS)


def test_schedule_invariants_reject_a_forged_enqueue() -> None:
    blocked = _schedule(circuit_status="open")
    forged = dict(
        blocked, schedule_status="due_and_safe_to_enqueue", safe_to_enqueue=True
    )
    fails = schedule_invariant_failures(forged)
    assert "enqueue_permitted_with_a_blocking_circuit" in fails


def test_schedule_invariants_reject_a_forged_execution_claim() -> None:
    forged = dict(_schedule(), safe_to_execute_now=True)
    assert "decision_claimed_safe_to_execute_now" in schedule_invariant_failures(forged)


def test_schedule_invariants_reject_an_undeterminable_schedule_reported_due() -> None:
    forged = dict(_schedule(next_check_due_at=None), due_for_check=True)
    assert "undeterminable_schedule_reported_due" in schedule_invariant_failures(forged)


def test_enqueue_permission_follows_the_single_permitting_status() -> None:
    forged = dict(_schedule(), safe_to_enqueue=False)
    fails = schedule_invariant_failures(forged)
    assert "safe_to_enqueue_disagrees_with_status" in fails
    assert ENQUEUE_PERMITTED_STATUSES == frozenset({"due_and_safe_to_enqueue"})


def test_schedule_summary_never_counts_an_execution() -> None:
    decisions = [_schedule(), _schedule(circuit_status="open"), _schedule()]
    summary = summarise_schedule(decisions)
    assert summary["safe_to_enqueue_count"] == 2
    assert summary["safe_to_execute_now_count"] == 0
    assert summary["enqueued_count"] == 0
    assert summary["checks_executed"] == 0


# --------------------------------------------------------------------------
# 98C - circuit breaker
# --------------------------------------------------------------------------


def test_breaker_threshold_is_bridged_from_gate_92() -> None:
    assert DEFAULT_BREAKER_THRESHOLD == CIRCUIT_BREAKER_CONSECUTIVE_FAILURES


def test_a_healthy_source_is_closed() -> None:
    result = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=0)
    assert result["circuit_status"] == "closed"
    assert result["permits_scheduling"] is True
    assert not circuit_invariant_failures(result)


def test_reaching_the_threshold_opens_the_circuit() -> None:
    result = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD,
        last_failure_at=RECENT_FAILURE,
    )
    assert result["circuit_status"] == "open"
    assert result["permits_scheduling"] is False
    assert result["cooldown_remaining_seconds"] > 0


def test_an_elapsed_cooldown_gives_one_probe_not_a_resumption() -> None:
    result = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD,
        last_failure_at=OLD_FAILURE,
    )
    assert result["circuit_status"] == "half_open"
    assert result["permits_scheduling"] is True
    assert result["single_probe_only"] is True


def test_half_open_is_the_only_single_probe_state() -> None:
    assert SINGLE_PROBE_STATUSES == frozenset({"half_open"})
    closed = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=0)
    assert closed["single_probe_only"] is False


def test_a_cooldown_that_cannot_be_measured_has_not_elapsed() -> None:
    result = evaluate_circuit(
        source_id="s", now=NOW, consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD
    )
    assert result["circuit_status"] == "open"
    assert "cooldown_not_derivable" in result["blocked_reasons"]


def test_naive_and_aware_timestamps_do_not_invent_a_timezone() -> None:
    result = evaluate_circuit(
        source_id="s",
        now="2026-01-01T12:00:00",
        consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD,
        last_failure_at=OLD_FAILURE,
    )
    assert result["circuit_status"] == "open"
    assert "cooldown_not_derivable" in result["blocked_reasons"]


def test_a_manual_hold_outranks_a_healthy_counter() -> None:
    result = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=0,
        manual_override_status="hold",
    )
    assert result["circuit_status"] == "manual_hold"
    assert result["permits_scheduling"] is False


def test_a_manual_hold_is_not_lifted_by_an_elapsed_cooldown() -> None:
    result = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD,
        last_failure_at=OLD_FAILURE,
        manual_override_status="hold",
    )
    assert result["circuit_status"] == "manual_hold"


def test_an_unrecognised_override_blocks_rather_than_reads_as_no_override() -> None:
    """A value nobody defined is somebody's intent this code cannot read."""
    result = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=0,
        manual_override_status="something_nobody_defined",
    )
    assert result["circuit_status"] == "unknown"
    assert result["permits_scheduling"] is False


def test_an_absent_override_is_not_an_unrecognised_one() -> None:
    result = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=0)
    assert result["manual_override_status"] == "none"
    assert result["circuit_status"] == "closed"


@pytest.mark.parametrize("value", [None, -1, "many", object()])
def test_an_unreadable_failure_count_is_unknown_not_healthy(value: object) -> None:
    result = evaluate_circuit(
        source_id="s", now=NOW, consecutive_failure_count=value
    )
    assert result["circuit_status"] == "unknown"
    assert result["permits_scheduling"] is False


def test_unknown_never_permits_scheduling() -> None:
    assert "unknown" not in SCHEDULING_PERMITTED_STATUSES


def test_a_success_resets_the_failure_count() -> None:
    circuit = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=4)
    outcome = apply_check_outcome(circuit=circuit, succeeded=True, at=NOW)
    assert outcome["consecutive_failure_count_after"] == 0
    assert outcome["resets_failures"] is True
    assert not circuit_invariant_failures(outcome)


def test_a_failure_increments_the_failure_count() -> None:
    circuit = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=4)
    outcome = apply_check_outcome(circuit=circuit, succeeded=False, at=NOW)
    assert outcome["consecutive_failure_count_after"] == 5
    assert not circuit_invariant_failures(outcome)


def test_no_breaker_result_reports_a_probe_or_a_fetch() -> None:
    for count in (0, 3, DEFAULT_BREAKER_THRESHOLD, None):
        result = evaluate_circuit(
            source_id="s", now=NOW, consecutive_failure_count=count
        )
        assert result["probe_performed"] is False
        assert result["fetch_performed"] is False
        assert result["check_executed"] is False


def test_breaker_invariants_reject_a_lifted_manual_hold() -> None:
    hold = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=0,
        manual_override_status="hold",
    )
    forged = dict(hold, circuit_status="closed", permits_scheduling=True)
    fails = circuit_invariant_failures(forged)
    assert "manual_hold_overridden_by_automation" in fails
    assert "manual_hold_permitted_scheduling" in fails


def test_breaker_invariants_reject_half_open_at_full_rate() -> None:
    half = evaluate_circuit(
        source_id="s",
        now=NOW,
        consecutive_failure_count=DEFAULT_BREAKER_THRESHOLD,
        last_failure_at=OLD_FAILURE,
    )
    fails = circuit_invariant_failures(dict(half, single_probe_only=False))
    assert "half_open_permitted_full_rate" in fails


def test_breaker_invariants_reject_a_threshold_above_the_governance_floor() -> None:
    closed = evaluate_circuit(source_id="s", now=NOW, consecutive_failure_count=0)
    fails = circuit_invariant_failures(dict(closed, breaker_threshold=999))
    assert "breaker_threshold_above_the_governance_floor" in fails


def test_circuit_status_vocabulary_is_closed() -> None:
    assert MANUAL_HOLDING <= frozenset({"hold"})
    for value in (None, 0, 99, "x"):
        result = evaluate_circuit(
            source_id="s", now=NOW, consecutive_failure_count=value
        )
        assert result["circuit_status"] in CIRCUIT_STATUSES


def test_cooldown_default_is_a_real_duration() -> None:
    assert DEFAULT_COOLDOWN_SECONDS > 0


# --------------------------------------------------------------------------
# 98D - check-run contract
# --------------------------------------------------------------------------


def test_the_contract_declares_its_fields_and_prohibitions() -> None:
    shape = contract_shape()
    assert shape["table"] == "nf_source_check_runs"
    assert shape["payload_reference_style"] == "id_only"
    assert shape["response_body_stored"] is False
    assert set(shape["check_statuses"]) == set(CHECK_RUN_STATUSES)
    assert set(shape["check_modes"]) == set(CHECK_MODES)


def test_no_contract_field_is_a_prohibited_name() -> None:
    assert not set(CONTRACT_FIELDS) & PROHIBITED_FIELD_NAMES


def test_a_record_carries_payload_ids_not_bodies() -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        check_status="succeeded",
        counts={"opportunities_seen_count": 4},
        raw_payload_ids=[PAYLOAD_ID_A, PAYLOAD_ID_B],
    )
    assert record["raw_payload_ids"] == sorted([PAYLOAD_ID_A, PAYLOAD_ID_B])
    assert record["raw_payload_count"] == 2
    assert record["counts_evidence_backed"] is True
    assert not check_run_invariant_failures(record)


def test_anything_that_is_not_a_payload_id_is_dropped() -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        raw_payload_ids=[PAYLOAD_ID_A, "not-an-id", "", None, "<html>body</html>"],
    )
    assert record["raw_payload_ids"] == [PAYLOAD_ID_A]
    assert "raw_payload_ids_rejected:4" in record["warnings"]


def test_a_success_reporting_counts_with_no_evidence_is_warned() -> None:
    """The 185/18 shape: a number with nothing retrievable behind it."""
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        check_status="succeeded",
        counts={"opportunities_seen_count": 42},
    )
    assert record["counts_evidence_backed"] is False
    assert "counts_reported_without_payload_evidence" in record["warnings"]


def test_an_error_message_is_redacted_on_the_way_in() -> None:
    dirty = (
        "GET https://api.example.gov/v1/x?api_key=AKIA1234567890ABCDEF failed; "
        "sent Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345"
    )
    record = build_check_run_record(
        run_id="r", source_id="s", check_status="failed", error_message=dirty
    )
    message = record["error_message_redacted"]
    assert "AKIA1234567890ABCDEF" not in message
    assert "abcdefghijklmnopqrstuvwxyz012345" not in message
    assert record["redaction_applied"] is True


def test_redaction_is_not_trusted_from_the_caller() -> None:
    """There is no parameter saying the message was already redacted."""
    import inspect

    params = inspect.signature(build_check_run_record).parameters
    assert "error_message_redacted" not in params
    assert "already_redacted" not in params
    assert "skip_redaction" not in params


def test_a_clean_message_survives_redaction_unchanged() -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        check_status="failed",
        error_message="connection reset by peer",
    )
    assert record["error_message_redacted"] == "connection reset by peer"
    assert record["redaction_applied"] is False


@pytest.mark.parametrize("value", ["many", -4, None, object()])
def test_an_unreadable_count_is_unknown_not_zero(value: object) -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        counts={"opportunities_seen_count": value},
    )
    assert record["opportunities_seen_count"] is None


def test_no_record_claims_execution_or_persistence() -> None:
    record = build_check_run_record(run_id="r", source_id="s")
    assert record["check_executed"] is False
    assert record["fetch_performed"] is False
    assert record["persisted"] is False
    assert record["response_body_included"] is False
    assert record["secret_values_included"] is False


def test_an_unrecognised_status_falls_back_to_failed_not_succeeded() -> None:
    record = build_check_run_record(
        run_id="r", source_id="s", check_status="finished_probably"
    )
    assert record["check_status"] == "failed"


@pytest.mark.parametrize("name", sorted(PROHIBITED_FIELD_NAMES))
def test_invariants_reject_any_prohibited_field(name: str) -> None:
    record = build_check_run_record(run_id="r", source_id="s")
    fails = check_run_invariant_failures({**record, name: "anything"})
    assert f"prohibited_field_present:{name}" in fails


def test_invariants_reject_accepted_exceeding_seen() -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        check_status="succeeded",
        counts={"opportunities_seen_count": 3, "accepted_count": 3},
        raw_payload_ids=[PAYLOAD_ID_A],
    )
    fails = check_run_invariant_failures(dict(record, accepted_count=99))
    assert "accepted_exceeds_opportunities_seen" in fails


def test_invariants_reject_a_stripped_evidence_warning() -> None:
    record = build_check_run_record(
        run_id="r",
        source_id="s",
        check_status="succeeded",
        counts={"opportunities_seen_count": 42},
    )
    fails = check_run_invariant_failures(dict(record, warnings=[]))
    assert "unevidenced_counts_not_warned" in fails


def test_check_run_summary_never_counts_an_execution() -> None:
    records = [
        build_check_run_record(run_id="r", source_id="s", check_status="succeeded"),
        build_check_run_record(run_id="r2", source_id="s", check_status="failed"),
    ]
    summary = summarise_check_runs(records)
    assert summary["checks_executed"] == 0
    assert summary["records_persisted"] == 0


def test_every_count_field_appears_in_the_contract() -> None:
    assert set(COUNT_FIELDS) <= set(CONTRACT_FIELDS)


# --------------------------------------------------------------------------
# 98E - scheduler readiness
# --------------------------------------------------------------------------


def test_the_three_facts_that_must_stay_false_are_false() -> None:
    """Gate 99D changed the fourth.

    `scheduler_runtime_available` was False here and meant "no scheduler
    package is installed". Gate 99 built an in-process dry-run queue, so the
    honest answer became neither plain yes nor plain no; `runtime_mode` carries
    it, and Gate 99's own tests hold that. These three are the ones a dry-run
    runtime must never move, and they are asserted here as well as there
    because this file is what a reader comes to for the Gate 98 boundary.
    """
    readiness = build_scheduler_readiness()
    assert readiness["background_worker_available"] is False
    assert readiness["source_monitoring_live"] is False
    assert readiness["ready_to_start_monitoring"] is False
    assert not scheduler_readiness_invariant_failures(readiness)


def test_no_scheduler_package_is_installed_which_was_gate_98s_question() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["scheduler_package_installed"] is False
    assert readiness["runtime_mode"] == "dry_run_in_process"


def test_no_scheduler_runtime_is_installed() -> None:
    detected = detect_scheduler_runtime()
    assert detected["available"] is False
    assert detected["packages_found"] == []
    assert set(detected["packages_considered"]) == set(SCHEDULER_RUNTIME_PACKAGES)


def test_no_background_worker_exists() -> None:
    detected = detect_background_worker()
    assert detected["available"] is False
    assert detected["worker_modules"] == []
    assert detected["worker_entry_points"] == []


def test_no_periodic_trigger_is_checked_into_the_repo() -> None:
    detected = detect_periodic_trigger(repo_root=REPO_ROOT)
    assert detected["available"] is False
    assert detected["trigger_files"] == []
    assert detected["host_schedulers_inspected"] is False


def test_readiness_is_detected_rather_than_declared() -> None:
    """No *claim* can turn a missing component into a present one.

    Gate 98 asserted the signature took only `repo_root`. Gate 102B had to add
    `process_proof`, and the reason is worth stating rather than papering over:
    whether a process is *running* cannot be detected without I/O that would
    make this answer differ per machine and per minute, which would break the
    determinism the committed artifacts depend on.

    So liveness is the one component established by evidence passed in. The
    guarantee is preserved by validating that evidence rather than trusting it -
    a bare truthy value, a partial observation, or one that says it saw nothing
    all leave the answer false. Only a complete observation flips it.
    """
    import inspect

    params = set(inspect.signature(build_scheduler_readiness).parameters)
    assert params == {"repo_root", "process_proof"}

    # A claim is not evidence.
    for not_evidence in (
        {"lol": 1},
        {"observed": True},
        {"observed": True, "pid": 5},
        {"observed": False, "pid": 5, "observed_at": "2026-01-01T00:00:00+00:00"},
    ):
        readiness = build_scheduler_readiness(process_proof=not_evidence)
        assert readiness["persistent_backend_live"] is False, not_evidence

    # And a complete observation does, so the check is not vacuous.
    complete = build_scheduler_readiness(
        process_proof={
            "observed": True,
            "pid": 5,
            "observed_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert complete["persistent_backend_live"] is True


def test_the_runtime_detection_is_live_not_a_hardcoded_false(monkeypatch) -> None:
    """A constant False would keep reading False after a worker was deployed."""
    import nativeforge.services.source_scheduler_readiness_service as mod

    real = mod._module_importable
    monkeypatch.setattr(
        mod,
        "_module_importable",
        lambda name: True if name in mod.SCHEDULER_RUNTIME_PACKAGES else real(name),
    )
    readiness = mod.build_scheduler_readiness()
    assert readiness["scheduler_runtime_available"] is True
    assert readiness["components"]["scheduler_runtime"]["packages_found"]
    # And it is still not ready, because the other components remain missing.
    assert readiness["ready_to_start_monitoring"] is False
    assert not scheduler_readiness_invariant_failures(readiness)


def test_the_decision_layer_is_present_and_is_not_a_scheduler() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["decision_layer_available"] is True
    # Gate 99 added a dry-run runtime, which still is not a worker and still
    # cannot monitor anything.
    assert readiness["background_worker_available"] is False
    assert readiness["ready_to_start_monitoring"] is False


def test_every_component_reports_how_it_was_detected() -> None:
    readiness = build_scheduler_readiness()
    for key in COMPONENT_KEYS:
        assert readiness["components"][key]["detection_method"]


def test_every_component_is_accounted_for_exactly_once() -> None:
    readiness = build_scheduler_readiness()
    present = set(readiness["components_present"])
    missing = set(readiness["components_missing"])
    assert not present & missing
    assert present | missing == set(COMPONENT_KEYS)


def test_remaining_work_is_the_missing_runtime_components() -> None:
    readiness = build_scheduler_readiness()
    assert set(readiness["remaining_work"]) == set(
        readiness["components_missing"]
    ) & set(RUNTIME_COMPONENT_KEYS)


def test_readiness_invariants_reject_a_forged_ready_flag() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, ready_to_start_monitoring=True)
    )
    assert "ready_with_missing_components" in fails


def test_readiness_invariants_reject_forged_live_monitoring() -> None:
    readiness = build_scheduler_readiness()
    fails = scheduler_readiness_invariant_failures(
        dict(readiness, source_monitoring_live=True)
    )
    assert "monitoring_live_disagrees_with_the_runtime_components" in fails


def test_readiness_reports_no_jobs_and_no_checks() -> None:
    readiness = build_scheduler_readiness()
    assert readiness["scheduled_jobs_started"] == 0
    assert readiness["checks_executed"] == 0
    assert readiness["live_fetch_performed"] is False
    assert readiness["collectors_active"] is False
    assert readiness["live_source_coverage"] is False


# --------------------------------------------------------------------------
# 98F - activation is not scheduler readiness
# --------------------------------------------------------------------------


def _cleared_preflight(**overrides):
    from nativeforge.services.source_activation_preflight_service import (
        build_activation_preflight,
    )

    kwargs = dict(
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
    kwargs.update(overrides)
    return build_activation_preflight(**kwargs)


def test_a_cleared_source_may_activate_but_may_not_be_scheduled() -> None:
    """A declared scheduler policy is a cadence decision, not a process."""
    result = _cleared_preflight()
    assert result["activation_allowed"] is True
    assert result["scheduler_policy_declared"] is True
    assert result["scheduler_runtime_available"] is False
    assert result["safe_to_schedule"] is False
    assert "scheduler_runtime_unavailable" in result["scheduling_blocked_reasons"]


def test_scheduling_blockers_do_not_block_activation() -> None:
    result = _cleared_preflight()
    assert result["blocked_reasons"] == []
    assert result["scheduling_blocked_reasons"]


def test_scheduling_becomes_possible_when_a_runtime_exists(monkeypatch) -> None:
    import nativeforge.services.source_activation_preflight_service as mod

    # Gate 100D: both halves must be simulated. `_scheduler_runtime_available`
    # is itself `runtime and worker`, so a world where it returns True is a
    # world with a worker in it - and the result now records that fact
    # separately, which makes an inconsistent simulation fail an invariant
    # rather than pass quietly.
    # Gate 101E adds a third: a scheduler needs a process to live in, so a
    # world with a running scheduler is a world with a backend in it.
    monkeypatch.setattr(mod, "_scheduler_runtime_available", lambda: True)
    monkeypatch.setattr(mod, "_background_worker_present", lambda: True)
    monkeypatch.setattr(mod, "_persistent_backend_live", lambda: True)
    result = _cleared_preflight()
    assert result["safe_to_schedule"] is True
    assert not mod.preflight_invariant_failures(result)


def test_preflight_invariants_reject_scheduling_without_a_runtime() -> None:
    from nativeforge.services.source_activation_preflight_service import (
        preflight_invariant_failures,
    )

    forged = dict(_cleared_preflight(), safe_to_schedule=True)
    fails = preflight_invariant_failures(forged)
    assert "safe_to_schedule_without_a_scheduler_runtime" in fails


def test_phase1_matrix_derives_schedulability_rather_than_asserting_it() -> None:
    from nativeforge.services.phase1_collector_activation_policy_service import (
        build_phase1_activation_matrix,
        default_phase1_preflights,
        policy_invariant_failures,
    )

    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["scheduler_runtime_available"] is False
    assert matrix["source_monitoring_live"] is False
    assert matrix["monitors_active"] == 0
    assert matrix["sources_may_schedule_monitor"] == 0
    assert not policy_invariant_failures(matrix)


def test_phase1_schedulability_is_live_not_a_constant(monkeypatch) -> None:
    """Gate 97's lesson: a constant true of one moment is not a law."""
    import nativeforge.services.phase1_collector_activation_policy_service as mod

    monkeypatch.setattr(mod, "_scheduler_runtime_available", lambda: True)
    monkeypatch.setattr(mod, "_monitoring_live", lambda: True)
    # Gate 101E: a scheduler that is running is running somewhere.
    monkeypatch.setattr(mod, "_persistent_backend_live", lambda: True)
    matrix = mod.build_phase1_activation_matrix(
        preflight_by_source={
            sid: {"activation_allowed": True} for sid in mod.PHASE1_SOURCE_IDS
        }
    )
    assert matrix["sources_may_schedule_monitor"] == len(mod.PHASE1_SOURCE_IDS)
    assert not mod.policy_invariant_failures(matrix)


def test_phase1_invariants_reject_a_count_that_disagrees_with_its_rows() -> None:
    from nativeforge.services.phase1_collector_activation_policy_service import (
        build_phase1_activation_matrix,
        default_phase1_preflights,
        policy_invariant_failures,
    )

    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    fails = policy_invariant_failures(dict(matrix, sources_may_schedule_monitor=5))
    assert "schedulable_count_disagrees_with_the_rows" in fails


# --------------------------------------------------------------------------
# 98G - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_scheduler_readiness_artifacts(repo_root=first)
    write_scheduler_readiness_artifacts(repo_root=second)
    for name in ARTIFACT_NAMES:
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(tmp_path: Path) -> None:
    committed = REPO_ROOT / ARTIFACT_DIR
    if not (committed / ARTIFACT_NAMES[0]).exists():
        pytest.skip("scheduler readiness artifacts not generated in this tree")
    write_scheduler_readiness_artifacts(repo_root=tmp_path)
    for name in ARTIFACT_NAMES:
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        on_disk = (committed / name).read_bytes()
        assert (
            hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(fresh).hexdigest()
        ), name


def test_all_five_artifacts_are_written(tmp_path: Path) -> None:
    result = write_scheduler_readiness_artifacts(repo_root=tmp_path)
    assert len(ARTIFACT_NAMES) == 5
    for name in ARTIFACT_NAMES:
        assert (tmp_path / ARTIFACT_DIR / name).exists(), name
    assert result["files"] == list(ARTIFACT_NAMES)


@pytest.mark.parametrize("name", ARTIFACT_NAMES)
def test_every_artifact_states_the_four_declarations(name: str) -> None:
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("scheduler readiness artifacts not generated in this tree")
    text = path.read_text(encoding="utf-8")
    for key in DECLARATION_KEYS:
        assert key in text, f"{name} omits {key}"


def test_the_csv_stamps_declarations_on_every_row() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "scheduler_readiness_components.csv"
    if not path.exists():
        pytest.skip("scheduler readiness artifacts not generated in this tree")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(COMPONENT_KEYS) + 1
    for line in lines[1:]:
        # runtime_mode, then the four booleans. Gate 99D made the first boolean
        # True and put the mode in front of it, because `True` on its own in a
        # copied row would be read as a production scheduler.
        assert line.endswith("dry_run_in_process,True,False,False,False"), line


def test_the_writer_refuses_a_bundle_whose_declarations_are_wrong(
    tmp_path: Path, monkeypatch
) -> None:
    import nativeforge.services.source_scheduler_readiness_artifact_service as mod

    real = mod.build_readiness_bundle

    def liar(*, repo_root=None):
        bundle = real(repo_root=repo_root)
        bundle["declarations"]["ready_to_start_monitoring"] = True
        return bundle

    monkeypatch.setattr(mod, "build_readiness_bundle", liar)
    with pytest.raises(SchedulerReadinessArtifactError):
        mod.write_scheduler_readiness_artifacts(repo_root=tmp_path)
    assert not (tmp_path / ARTIFACT_DIR).exists()


def test_a_clean_bundle_has_no_claim_failures() -> None:
    bundle = build_readiness_bundle(repo_root=REPO_ROOT)
    summary = render_readiness_summary(bundle)
    assert artifact_claim_failures(bundle, summary) == []


def test_the_readiness_json_is_parseable_and_declares_the_facts() -> None:
    path = REPO_ROOT / ARTIFACT_DIR / "scheduler_readiness.json"
    if not path.exists():
        pytest.skip("scheduler readiness artifacts not generated in this tree")
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Gate 99D: `runtime_mode` is a string and `scheduler_runtime_available` is
    # legitimately true. These three are the ones that must stay false.
    for key in FALSE_DECLARATION_KEYS:
        assert payload[key] is False
    assert payload["runtime_mode"] == "dry_run_in_process"
    assert set(FALSE_DECLARATION_KEYS) <= set(DECLARATION_KEYS)


def test_no_artifact_contains_a_response_body_or_a_secret() -> None:
    directory = REPO_ROOT / ARTIFACT_DIR
    if not directory.exists():
        pytest.skip("scheduler readiness artifacts not generated in this tree")
    for path in sorted(directory.glob("*")):
        text = path.read_text(encoding="utf-8")
        assert "-----BEGIN" not in text
        assert "eyJ" not in text
        for marker in ("Bearer ", "api_key="):
            assert marker not in text, f"{path.name} contains {marker!r}"


# --------------------------------------------------------------------------
# 98 - cross-cutting: nothing in this gate acts
# --------------------------------------------------------------------------


def _service_source(name: str) -> str:
    return (
        REPO_ROOT / "src" / "nativeforge" / "services" / f"{name}.py"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", GATE98_SERVICES)
def test_no_gate98_service_imports_an_http_client(name: str) -> None:
    """Deciding whether to fetch must not be able to fetch."""
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


@pytest.mark.parametrize("name", GATE98_SERVICES)
def test_no_gate98_service_writes_to_the_database(name: str) -> None:
    banned = {"sqlalchemy", "psycopg", "psycopg2", "asyncpg"}
    tree = ast.parse(_service_source(name))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & banned, f"{name} imports {imported & banned}"


@pytest.mark.parametrize("name", GATE98_SERVICES)
def test_every_gate98_service_declares_a_schema_version(name: str) -> None:
    module = __import__(
        f"nativeforge.services.{name}", fromlist=["SCHEMA_VERSION"]
    )
    assert module.SCHEMA_VERSION.startswith("nf_")


def test_the_gate_starts_no_scheduled_jobs() -> None:
    readiness = build_scheduler_readiness()
    decisions = [_schedule(), _schedule(circuit_status="open")]
    records = [build_check_run_record(run_id="r", source_id="s")]
    assert readiness["scheduled_jobs_started"] == 0
    assert summarise_schedule(decisions)["enqueued_count"] == 0
    assert summarise_check_runs(records)["checks_executed"] == 0
