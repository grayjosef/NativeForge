"""The periodic trigger (Gate 159C).

## What this decides, and what it refuses to decide

It answers one question: *should a cycle run for the slot containing `now`, and
if not, why not.* It opens no connection, runs no cycle and contacts nothing.

The caller supplies what has already happened — `last_served_slot_index` — and
this module compares. It does not read that from a database, because a decision
function that fetches its own evidence cannot be tested against a history it did
not choose.

## The states

```text
not_due            the last served slot IS the current slot boundary and the
                   window has not turned over
due                this slot has not been served and should be
already_triggered  this exact slot has been served
missed_window      slots between the last served one and now went unserved
recovered          reported by the recovery pass, not decided here
blocked            a prerequisite for triggering at all is absent
unknown            the inputs do not support a decision
```

`already_triggered` and `not_due` are deliberately different. "Not due" is a
statement about the clock; "already triggered" is a statement about history.
Collapsing them would make a duplicate trigger attempt indistinguishable from a
poll that arrived early, and duplicate suppression is exactly the thing this
gate has to prove.

## Repeated polling must not create repeated effects

The slot is a floor over an injected clock, so every instant inside one window
resolves to one slot index and one cycle id. Poll a hundred times inside an
hour at hourly cadence and the decision is `due` once and `already_triggered`
ninety-nine times — provided the caller records what it served, which is what
159E's ownership record is for.

The clock is injected. A trigger that read `datetime.now()` could not be tested
against a missed window without waiting for one.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from nativeforge.services.source_collection_orchestration_identity_service import (
    DEFAULT_CADENCE,
    build_orchestration_identity,
    cadence_seconds,
    compute_slot_index,
    normalize_cadence,
    slot_started_at,
)

SCHEMA_VERSION = "nf_source_collection_periodic_trigger_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

NOT_DUE = "not_due"
DUE = "due"
ALREADY_TRIGGERED = "already_triggered"
MISSED_WINDOW = "missed_window"
RECOVERED = "recovered"
BLOCKED = "blocked"
UNKNOWN = "unknown"

TRIGGER_STATES: tuple[str, ...] = (
    NOT_DUE,
    DUE,
    ALREADY_TRIGGERED,
    MISSED_WINDOW,
    RECOVERED,
    BLOCKED,
    UNKNOWN,
)

#: States in which a cycle may proceed. Membership, not a negation of the
#: refusing set - the Gate 156 discipline: a new state is refused by default
#: rather than permitted by having been forgotten.
TRIGGER_PERMITS_A_CYCLE: frozenset[str] = frozenset({DUE, MISSED_WINDOW})

BLOCK_NO_CLOCK = "no_clock_supplied"
BLOCK_TRIGGER_DISABLED = "periodic_trigger_is_not_enabled"
BLOCK_SLOT_IN_THE_FUTURE = "last_served_slot_is_in_the_future"

#: How many missed slots the trigger will report as recoverable. The bound
#: belongs here rather than in the recovery pass, so a caller cannot ask for an
#: unbounded catch-up by calling recovery directly.
DEFAULT_MAX_CATCHUP_SLOTS = 6


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compute_next_wake_at(
    *, now: Any, cadence: Any = DEFAULT_CADENCE
) -> datetime | None:
    """The instant the next slot opens.

    Derived from the slot boundary, not from `now + interval`. A process that
    slept for `interval` from an arbitrary wake time would drift off the
    boundary and eventually serve two slots in one window, or none.
    """
    index = compute_slot_index(now=now, cadence=cadence)
    if index is None:
        return None
    return slot_started_at(slot_index=index + 1, cadence=cadence)


def evaluate_trigger(
    *,
    now: Any,
    last_served_slot_index: Any = None,
    cadence: Any = DEFAULT_CADENCE,
    trigger_enabled: bool = True,
    max_catchup_slots: int = DEFAULT_MAX_CATCHUP_SLOTS,
) -> dict[str, Any]:
    """Should a cycle run for the slot containing `now`?

    `last_served_slot_index` is what the caller knows has already happened.
    None means nothing has ever been served, which is `due` rather than a
    hundred missed windows back to the epoch.
    """
    resolved_cadence = normalize_cadence(cadence)
    identity = build_orchestration_identity(now=now, cadence=resolved_cadence)
    current = identity.get("slot_index")
    last = _as_int(last_served_slot_index)
    bound = max(1, int(max_catchup_slots))

    blocked: list[str] = []
    if current is None:
        blocked.append(BLOCK_NO_CLOCK)
    if not trigger_enabled:
        blocked.append(BLOCK_TRIGGER_DISABLED)
    if current is not None and last is not None and last > current:
        # A clock that moved backwards, or a record from another cadence.
        # Refused rather than reinterpreted: serving a slot we already passed
        # would re-run history.
        blocked.append(BLOCK_SLOT_IN_THE_FUTURE)

    missed_slots: list[int] = []
    if current is not None and last is not None and last < current:
        # Every slot strictly between the last served one and the current one,
        # plus the current one itself - the current slot is unserved too.
        missed_slots = list(range(last + 1, current + 1))

    if blocked:
        state = BLOCKED if current is not None else UNKNOWN
    elif last is None:
        # Nothing has ever been served. One slot is due; the whole history
        # before it is NOT a backlog of missed windows, because there was no
        # orchestrator to miss them.
        state = DUE
    elif last == current:
        state = ALREADY_TRIGGERED
    elif len(missed_slots) > 1:
        state = MISSED_WINDOW
    else:
        state = DUE

    recoverable = missed_slots[-bound:] if missed_slots else []
    dropped = max(0, len(missed_slots) - len(recoverable))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "state": state,
            "states": list(TRIGGER_STATES),
            "should_run_a_cycle": state in TRIGGER_PERMITS_A_CYCLE,
            "blocked_reasons": sorted(set(blocked)),
            # ---- the clock, and where in it we are ----------------------
            "evaluated_at": None if now is None else str(now),
            "cadence": resolved_cadence,
            "cadence_seconds": cadence_seconds(resolved_cadence),
            "current_slot_index": current,
            "current_slot_key": identity.get("slot_key"),
            "slot_started_at": identity.get("slot_started_at"),
            "slot_ends_at": identity.get("slot_ends_at"),
            "next_wake_at": compute_next_wake_at(now=now, cadence=resolved_cadence),
            "cycle_id": identity.get("cycle_id"),
            # ---- history, as the caller reported it ---------------------
            "last_served_slot_index": last,
            "slots_behind": (
                None if current is None or last is None else current - last
            ),
            # ---- the missed window, bounded -----------------------------
            "missed_slot_indexes": missed_slots,
            "missed_slot_count": len(missed_slots),
            "recoverable_slot_indexes": recoverable,
            "recoverable_slot_count": len(recoverable),
            "max_catchup_slots": bound,
            "catchup_was_bounded": dropped > 0,
            # Named rather than discarded silently. An operator who lost a week
            # of slots should be told how many were not replayed.
            "slots_dropped_by_the_bound": dropped,
            "oldest_recoverable_slot_key": (
                slot_started_at(
                    slot_index=recoverable[0], cadence=resolved_cadence
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                if recoverable
                else None
            ),
            # ---- what a trigger is not ----------------------------------
            "trigger_enabled": bool(trigger_enabled),
            "clock_is_injected": True,
            "a_trigger_is_not_a_source_check": True,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def trigger_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a decision that contradicts itself or exceeds its bound."""
    fails: list[str] = []

    state = decision.get("state")
    if state not in TRIGGER_STATES:
        fails.append(f"state_outside_vocabulary:{state}")

    # `should_run_a_cycle` must agree with the permitting set, in both
    # directions. A state added later that nobody wired in must refuse.
    expected = state in TRIGGER_PERMITS_A_CYCLE
    if bool(decision.get("should_run_a_cycle")) is not expected:
        fails.append(f"should_run_a_cycle_disagrees_with_state:{state}")

    if state == BLOCKED and not decision.get("blocked_reasons"):
        fails.append("blocked_without_naming_a_reason")
    if decision.get("blocked_reasons") and decision.get("should_run_a_cycle"):
        fails.append("would_run_a_cycle_alongside_blocked_reasons")

    # The bound is a bound.
    recoverable = decision.get("recoverable_slot_indexes") or []
    if len(recoverable) > int(decision.get("max_catchup_slots") or 0):
        fails.append("recoverable_slots_exceed_the_catchup_bound")
    if int(decision.get("recoverable_slot_count") or 0) != len(recoverable):
        fails.append("recoverable_slot_count_disagrees_with_the_list")

    missed = decision.get("missed_slot_indexes") or []
    if int(decision.get("missed_slot_count") or 0) != len(missed):
        fails.append("missed_slot_count_disagrees_with_the_list")
    if len(missed) < len(recoverable):
        fails.append("more_recoverable_slots_than_missed_ones")
    dropped = int(decision.get("slots_dropped_by_the_bound") or 0)
    if dropped != max(0, len(missed) - len(recoverable)):
        fails.append("dropped_slot_count_does_not_account_for_the_difference")
    if bool(decision.get("catchup_was_bounded")) is not (dropped > 0):
        fails.append("catchup_was_bounded_disagrees_with_the_dropped_count")

    # A slot already served must never be re-served.
    if state == ALREADY_TRIGGERED and decision.get("should_run_a_cycle"):
        fails.append("an_already_triggered_slot_would_run_again")

    # Recovery is reported by the recovery pass, never decided here.
    if state == RECOVERED:
        fails.append("the_trigger_reported_a_state_only_recovery_may_report")

    if not decision.get("clock_is_injected"):
        fails.append("trigger_read_the_wall_clock")

    for counter in ("collectors_invoked", "live_source_calls", "network_calls"):
        if int(decision.get(counter) or 0) != 0:
            fails.append(f"trigger_counted:{counter}")
    if decision.get("source_monitoring_live"):
        fails.append("trigger_claimed:source_monitoring_live")

    return sorted(set(fails))


def build_trigger_schedule(
    *, now: Any, cadence: Any = DEFAULT_CADENCE, count: int = 5
) -> dict[str, Any]:
    """The next few wake instants. Reported, never slept on by this module."""
    resolved = normalize_cadence(cadence)
    index = compute_slot_index(now=now, cadence=resolved)
    if index is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "cadence": resolved,
                "wakes": [],
                "blocked_reasons": [BLOCK_NO_CLOCK],
            }
        )
    width = cadence_seconds(resolved)
    start = slot_started_at(slot_index=index + 1, cadence=resolved)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "cadence": resolved,
            "cadence_seconds": width,
            "wakes": [
                (start + timedelta(seconds=width * offset)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
                for offset in range(max(0, int(count)))
            ],
            "blocked_reasons": [],
            "boundaries_not_intervals": (
                "each wake is a slot boundary, so a process that oversleeps "
                "rejoins the schedule instead of drifting off it"
            ),
        }
    )


#: Re-exported so callers do not import two modules to use one clock.
__all__ = [
    "ALREADY_TRIGGERED",
    "BLOCKED",
    "DEFAULT_MAX_CATCHUP_SLOTS",
    "DUE",
    "MISSED_WINDOW",
    "NOT_DUE",
    "RECOVERED",
    "SCHEMA_VERSION",
    "TRIGGER_PERMITS_A_CYCLE",
    "TRIGGER_STATES",
    "UNKNOWN",
    "build_trigger_schedule",
    "compute_next_wake_at",
    "evaluate_trigger",
    "trigger_invariant_failures",
]
