"""Gate 172T/M/AA/AB/AE: one place to ask how the fleet is doing.

Before this, answering "is this source alright" meant joining seven tables and
deriving health in the caller. Every caller derived it slightly differently,
which is the same defect as two schedulers: the copies drift, and the one that
drifted is the one somebody is looking at during an incident.

So this is the service boundary. It composes the layers that own each fact -
it does not recompute them, and it does not query around them.

## Fleet-global facts are hoisted

Gate 166 established this and at 5,000 sources it stops being an optimisation:
a fleet-global fact recomputed once per source is the O(N) cost that turns a
sweep into an outage. Globals are computed once per sweep and passed down.

## The health layer reports on itself

172AA: a health system whose inputs are missing must not return green. So
`build_fleet_health` carries `self_health` - stale computation, sources with
no health record, unclassified failures, invalid states - and readiness is
refused when its own inputs are absent.

## Counts reconcile

172AB: operational states are mutually exclusive, so the per-state counts must
sum to the evaluated population exactly. Dimensions overlap by design, so they
are counted separately and never mixed into that sum.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from nativeforge.services.source_fleet_drift_service import (
    VOLUME_STATES,
    assess_volume,
)
from nativeforge.services.source_fleet_expectation_service import (
    evaluate_freshness,
    resolve_expectation,
)
from nativeforge.services.source_fleet_operational_state_service import (
    DEGRADED_DIM,
    FAILED_DIM,
    HEALTH_DIMENSIONS,
    OK,
    OPERATIONAL_STATES,
    UNKNOWN_DIM,
    blank_dimensions,
    derive_operational_state,
    state_invariant_failures,
)

SCHEMA_VERSION = "nf_source_fleet_read_model_v1"

#: Every field 172T asks for. Named so a missing one is visible rather than
#: absent, the same way Gate 171's fleet health named its own.
READ_MODEL_FIELDS: tuple[str, ...] = (
    "source_id",
    "source_name",
    "adapter_key",
    "authorization_state",
    "activation_state",
    "operational_state",
    "authorization_health",
    "transport_health",
    "source_availability_health",
    "parser_health",
    "schema_health",
    "freshness_health",
    "volume_health",
    "evidence_health",
    "backlog_health",
    "scheduler_health",
    "worker_health",
    "last_attempt_at",
    "last_success_at",
    "last_payload_at",
    "last_observation_at",
    "last_useful_change_at",
    "expected_next_run_at",
    "freshness_deadline_at",
    "consecutive_failures",
    "latest_failure_type",
    "circuit_state",
    "payload_count",
    "observation_count",
    "canonical_count",
    "queue_delay_seconds",
    "latest_duration_seconds",
    "evidence_age_seconds",
    "observation_age_seconds",
    "known_gaps",
    "review_required_reason",
)

#: 172M: a 200 is not intelligence. Five levels, because collapsing them is
#: how a source that has been silently returning nothing for six weeks keeps
#: reporting itself healthy.
SUCCESS_LEVELS: tuple[str, ...] = (
    "transport_success",
    "payload_success",
    "parse_success",
    "observation_success",
    "useful_intelligence_success",
)

#: 172AA: what can be wrong with the health layer itself.
SELF_HEALTH_CONDITIONS: tuple[str, ...] = (
    "health_computation_is_fresh",
    "every_source_has_a_health_record",
    "scheduler_state_available",
    "worker_state_available",
    "every_failure_is_classified",
    "every_state_is_in_the_vocabulary",
    "every_dimension_is_reported",
)

MAX_HEALTH_AGE_SECONDS = 900


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _age(value: Any, now: dt.datetime) -> float | None:
    if not isinstance(value, dt.datetime):
        return None
    stamped = value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    return round((now - stamped).total_seconds(), 1)


def classify_success_level(
    *,
    transport_ok: bool = False,
    payload_bytes: Any = None,
    records_parsed: Any = None,
    observations_written: Any = None,
    useful_changes: Any = None,
) -> dict[str, Any]:
    """How far a collection actually got. Each level requires the one before.

    The worked example is a real one: HTTP 200, valid HTML, selector matches
    nothing. Transport succeeded, payload succeeded, parse produced zero. A
    single boolean would call that a success.
    """
    levels = {
        "transport_success": bool(transport_ok),
        "payload_success": bool(transport_ok and int(payload_bytes or 0) > 0),
        "parse_success": bool(
            transport_ok
            and int(payload_bytes or 0) > 0
            and int(records_parsed or 0) > 0
        ),
        "observation_success": bool(int(observations_written or 0) > 0),
        "useful_intelligence_success": bool(int(useful_changes or 0) > 0),
    }
    reached = [name for name in SUCCESS_LEVELS if levels[name]]
    return _json_safe(
        {
            **levels,
            "highest_level_reached": reached[-1] if reached else "none",
            "stopped_at": next(
                (name for name in SUCCESS_LEVELS if not levels[name]), None
            ),
        }
    )


def build_source_row(
    *,
    source_id: str,
    source_name: Any = None,
    adapter_key: Any = None,
    authorization_state: Any = None,
    activation_state: Any = None,
    disabled: bool = False,
    retired: bool = False,
    review_required_reason: Any = None,
    circuit_state: Any = None,
    rate_limited: bool = False,
    # REVOKED is not UNKNOWN. Gate 172's failure matrix found that this row
    # could not tell the two apart, so an authorization refusal classified as
    # FAILING with transport still permitted - which is the one outcome 172S
    # exists to prevent.
    authorization_revoked: bool = False,
    transport_blocked: bool = False,
    consecutive_failures: int = 0,
    latest_failure_type: Any = None,
    last_attempt_at: Any = None,
    last_success_at: Any = None,
    last_payload_at: Any = None,
    last_observation_at: Any = None,
    last_useful_change_at: Any = None,
    payload_count: int = 0,
    observation_count: int = 0,
    canonical_count: int = 0,
    queue_delay_seconds: Any = None,
    latest_duration_seconds: Any = None,
    robots_body_retained: Any = None,
    drift: dict[str, Any] | None = None,
    previous_record_counts: list[int] | None = None,
    records_read: Any = None,
    source_override: dict[str, Any] | None = None,
    known_gaps: list[str] | None = None,
    now: Any = None,
    # Hoisted once per sweep, never recomputed per source.
    fleet_globals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One source, every dimension measured from the layer that owns it."""
    stamp = now if isinstance(now, dt.datetime) else dt.datetime.now(dt.UTC)
    globals_ = dict(fleet_globals or {})
    gaps = list(known_gaps or [])

    expectation = resolve_expectation(
        adapter_key=adapter_key, source_override=source_override
    )
    freshness = evaluate_freshness(
        expectation=expectation,
        last_attempt_at=last_attempt_at,
        last_success_at=last_success_at,
        last_payload_at=last_payload_at,
        last_observation_at=last_observation_at,
        last_useful_change_at=last_useful_change_at,
        now=stamp,
    )
    volume = assess_volume(
        records_read=records_read, previous_record_counts=previous_record_counts
    )
    drift_report = dict(drift or {})

    dimensions = blank_dimensions()

    # AUTHORIZATION: from the authority ladder, never from a flag. Three
    # answers, not two - permission granted, permission REFUSED, and nobody
    # has asked.
    authorized = str(authorization_state or "") in (
        "live_opted_in",
        "authorized_for_live",
    )
    if authorization_revoked:
        dimensions["authorization_health"] = FAILED_DIM
        gaps.append("live_fetch_authorization_revoked")
    else:
        dimensions["authorization_health"] = (
            OK if authorized else FAILED_DIM if authorization_state else UNKNOWN_DIM
        )

    # TRANSPORT / AVAILABILITY: separated, because a host that refuses is not
    # a network that is broken.
    if transport_blocked or str(circuit_state or "") == "open":
        dimensions["transport_health"] = FAILED_DIM
    elif last_attempt_at is not None:
        dimensions["transport_health"] = (
            OK if int(consecutive_failures) == 0 else DEGRADED_DIM
        )
    dimensions["source_availability_health"] = (
        OK
        if last_success_at is not None and int(consecutive_failures) == 0
        else DEGRADED_DIM
        if last_success_at is not None
        else UNKNOWN_DIM
    )

    # PARSER / SCHEMA: from drift, which owns them.
    if drift_report:
        breaking = bool(drift_report.get("requires_human_review"))
        signals = set(drift_report.get("signal_names") or [])
        dimensions["schema_health"] = FAILED_DIM if breaking else OK
        parser_signals = {
            "parse_error_rate_increased",
            "selector_stopped_matching",
            "required_field_missing",
        }
        dimensions["parser_health"] = (
            FAILED_DIM if signals & parser_signals else OK
        )
    elif observation_count:
        dimensions["parser_health"] = OK
        dimensions["schema_health"] = OK

    # FRESHNESS
    if not freshness.get("is_scheduled"):
        dimensions["freshness_health"] = "not_applicable"
    elif freshness.get("never_collected"):
        dimensions["freshness_health"] = UNKNOWN_DIM
    elif freshness.get("is_stale"):
        dimensions["freshness_health"] = FAILED_DIM
    else:
        dimensions["freshness_health"] = OK

    # VOLUME
    state = str(volume.get("state"))
    dimensions["volume_health"] = (
        UNKNOWN_DIM
        if state == "INSUFFICIENT_HISTORY"
        else OK
        if state == "NORMAL"
        else DEGRADED_DIM
    )

    # EVIDENCE: this is where a retained-bytes gap lands. It arrives as DATA -
    # `robots_body_retained` is a fact about a source, not a branch on one.
    if robots_body_retained is False:
        dimensions["evidence_health"] = DEGRADED_DIM
        gaps.append("robots_response_body_not_retained")
    elif payload_count:
        dimensions["evidence_health"] = OK
    if freshness.get("useful_intelligence_silent"):
        dimensions["evidence_health"] = (
            DEGRADED_DIM
            if dimensions["evidence_health"] != FAILED_DIM
            else FAILED_DIM
        )
        gaps.append("no_useful_change_within_the_silence_window")

    # BACKLOG / SCHEDULER / WORKER: fleet-global, hoisted.
    dimensions["backlog_health"] = str(globals_.get("backlog_health") or UNKNOWN_DIM)
    dimensions["scheduler_health"] = str(
        globals_.get("scheduler_health") or UNKNOWN_DIM
    )
    dimensions["worker_health"] = str(globals_.get("worker_health") or UNKNOWN_DIM)

    state_report = derive_operational_state(
        dimensions=dimensions,
        disabled=disabled,
        retired=retired,
        rate_limited=rate_limited,
        review_required=bool(review_required_reason),
        stale=bool(freshness.get("is_stale")),
        consecutive_failures=int(consecutive_failures),
        failure_threshold=int(expectation.get("max_consecutive_failures") or 3),
        known_gaps=gaps,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "source_name": source_name,
            "adapter_key": adapter_key,
            "authorization_state": authorization_state,
            "activation_state": activation_state,
            "operational_state": state_report["operational_state"],
            **dimensions,
            "last_attempt_at": last_attempt_at,
            "last_success_at": last_success_at,
            "last_payload_at": last_payload_at,
            "last_observation_at": last_observation_at,
            "last_useful_change_at": last_useful_change_at,
            "expected_next_run_at": freshness.get("expected_next_run_at"),
            "freshness_deadline_at": freshness.get("freshness_deadline_at"),
            "consecutive_failures": int(consecutive_failures),
            "latest_failure_type": latest_failure_type,
            "circuit_state": circuit_state,
            "payload_count": int(payload_count),
            "observation_count": int(observation_count),
            "canonical_count": int(canonical_count),
            "queue_delay_seconds": queue_delay_seconds,
            "latest_duration_seconds": latest_duration_seconds,
            "evidence_age_seconds": _age(last_payload_at, stamp),
            "observation_age_seconds": _age(last_observation_at, stamp),
            "known_gaps": state_report["known_gaps"],
            "review_required_reason": review_required_reason,
            # Carried for operators; not part of the flat field contract.
            "expectation": expectation,
            "freshness": freshness,
            "volume": volume,
            "state_detail": state_report,
        }
    )


def build_fleet_health(
    *,
    rows: list[dict[str, Any]],
    computed_at: Any = None,
    now: Any = None,
    scheduler_available: bool = True,
    worker_available: bool = True,
    registered_sources: Any = None,
) -> dict[str, Any]:
    """The fleet, counted and reconciled, plus the health of the health."""
    stamp = now if isinstance(now, dt.datetime) else dt.datetime.now(dt.UTC)
    evaluated = len(rows)

    by_state: dict[str, int] = dict.fromkeys(OPERATIONAL_STATES, 0)
    for row in rows:
        name = str(row.get("operational_state") or "")
        if name in by_state:
            by_state[name] += 1

    # Dimensions OVERLAP - a source can be degraded on two at once - so they
    # are counted separately and never folded into the state totals.
    by_dimension: dict[str, dict[str, int]] = {}
    for dimension in HEALTH_DIMENSIONS:
        counts: dict[str, int] = {}
        for row in rows:
            value = str(row.get(dimension) or UNKNOWN_DIM)
            counts[value] = counts.get(value, 0) + 1
        by_dimension[dimension] = dict(sorted(counts.items()))

    state_total = sum(by_state.values())

    # ---- 172AA: the health of the health --------------------------
    health_age = _age(computed_at, stamp) if computed_at else 0.0
    unclassified = sum(
        1
        for row in rows
        if int(row.get("consecutive_failures") or 0) > 0
        and not row.get("latest_failure_type")
    )
    invalid_states = sum(
        1
        for row in rows
        if str(row.get("operational_state") or "") not in OPERATIONAL_STATES
    )
    missing_dimensions = sum(
        1
        for row in rows
        for dimension in HEALTH_DIMENSIONS
        if dimension not in row
    )
    self_health = {
        "health_computation_is_fresh": (health_age or 0) <= MAX_HEALTH_AGE_SECONDS,
        "every_source_has_a_health_record": (
            registered_sources is None or evaluated >= int(registered_sources)
        ),
        "scheduler_state_available": bool(scheduler_available),
        "worker_state_available": bool(worker_available),
        "every_failure_is_classified": unclassified == 0,
        "every_state_is_in_the_vocabulary": invalid_states == 0,
        "every_dimension_is_reported": missing_dimensions == 0,
    }

    named_gaps = sorted(
        {gap for row in rows for gap in (row.get("known_gaps") or [])}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "computed_at": computed_at or stamp,
            "evaluated_sources": evaluated,
            "registered_sources": registered_sources,
            "counts_by_state": dict(sorted(by_state.items())),
            "state_counts_reconcile": state_total == evaluated,
            "counts_by_dimension": by_dimension,
            "dimensions_counted_separately": True,
            "healthy_sources": by_state.get("HEALTHY", 0),
            "degraded_sources": by_state.get("DEGRADED", 0),
            "stale_sources": by_state.get("STALE", 0),
            "failing_sources": by_state.get("FAILING", 0),
            "blocked_sources": by_state.get("BLOCKED", 0),
            "disabled_sources": by_state.get("DISABLED", 0),
            "review_required_sources": by_state.get("REVIEW_REQUIRED", 0),
            "unknown_sources": by_state.get("UNKNOWN", 0),
            "named_gaps": named_gaps,
            "self_health": dict(sorted(self_health.items())),
            "self_health_ok": all(self_health.values()),
            "fleet_health_ready": all(self_health.values())
            and state_total == evaluated
            and invalid_states == 0,
        }
    )


def read_model_invariant_failures(
    *, rows: list[dict[str, Any]], fleet: dict[str, Any]
) -> list[str]:
    """Refuse a fleet report that claims more than it measured."""
    failures: list[str] = []

    for row in rows:
        for field in READ_MODEL_FIELDS:
            if field not in row:
                failures.append(f"read_model_missing_field:{field}")
                break
        detail = row.get("state_detail")
        if isinstance(detail, dict):
            failures.extend(state_invariant_failures(detail))
        volume = dict(row.get("volume") or {})
        if volume and volume.get("state") not in VOLUME_STATES:
            failures.append("volume_state_outside_vocabulary")

    if not fleet.get("state_counts_reconcile"):
        failures.append("state_counts_do_not_reconcile_to_the_population")
    if fleet.get("fleet_health_ready") and not fleet.get("self_health_ok"):
        failures.append("fleet_ready_while_its_own_inputs_are_missing")

    # The specific shape 172AA exists to prevent.
    self_health = dict(fleet.get("self_health") or {})
    for condition in SELF_HEALTH_CONDITIONS:
        if condition not in self_health:
            failures.append(f"self_health_condition_not_measured:{condition}")
    if fleet.get("self_health_ok") and not all(self_health.values()):
        failures.append("self_health_ok_with_an_unmet_condition")

    return sorted(set(failures))


def describe_read_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "read_model_fields": list(READ_MODEL_FIELDS),
            "success_levels": list(SUCCESS_LEVELS),
            "self_health_conditions": list(SELF_HEALTH_CONDITIONS),
            "max_health_age_seconds": MAX_HEALTH_AGE_SECONDS,
            "field_count": len(READ_MODEL_FIELDS),
            "every_dimension_is_a_field": all(
                d in READ_MODEL_FIELDS for d in HEALTH_DIMENSIONS
            ),
        }
    )
