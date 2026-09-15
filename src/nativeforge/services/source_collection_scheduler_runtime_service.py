"""Gate 156B: the scheduler runtime — it computes time, and refuses everything.

## What was actually missing

Gates 98-100 built a schedule *decision* (`evaluate_schedule`), a job model, a
queue and a dry-run worker. None of them computes a next run time:
`evaluate_schedule` takes `next_check_due_at` as an argument and compares it to
a supplied `now`.

So this module does the one thing none of them do — turn an interval and a
last-checked timestamp into the next due time — and then evaluates a source
against a clock.

## The blocker it does not clear, and why that is correct

Gate 143 reports `scheduler_component_absent:scheduler_runtime`, which is
`find_spec` over eight third-party packages: apscheduler, dramatiq, arq, huey,
schedule, croniter, taskiq, procrastinate. None is installed and this gate
installs none.

`pip install apscheduler` would clear that blocker without computing a single
due date. A package provides a timing loop; it cannot know when a NativeForge
source is due. So `scheduler_package_installed` stays false after this gate and
the blocker stays listed, which is honest: the capability and the package are
different things and Gate 143 is measuring the package.

## Six states, and `due` is not `executable`

```text
scheduled   a cadence is known and the next run is in the future
due         the clock has come round
waiting     no cadence, or no last check; nobody has decided when
blocked     something says no, and it is named
disabled    the source is switched off
unknown     the inputs do not describe a state
```

A job may be `due` and still refuse to run. `due` is a fact about a clock;
`executable` is a fact about approvals. Collapsing them is how a scheduler that
exists becomes a scheduler that polls.

## `executable` requires every prerequisite affirmatively true

Not "no blockers found" — that reads absence of evidence as permission. Each of
activation, terms and human review must be explicitly the permitting value, and
a source whose terms nobody has read is `UNKNOWN`, which is blocking.

With zero sources approved today, `executable` is false for all 177 registry
rows, and there is no URL for a collector to fetch even if one existed.

## It computes and refuses. It does not run.

No socket, no subprocess, no collector, no database write. Every input arrives
as an argument, including the clock.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

SCHEMA_VERSION = "nf_source_collection_scheduler_runtime_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

SCHEDULED = "scheduled"
DUE = "due"
WAITING = "waiting"
BLOCKED = "blocked"
DISABLED = "disabled"
UNKNOWN = "unknown"

RUNTIME_STATES: tuple[str, ...] = (SCHEDULED, DUE, WAITING, BLOCKED, DISABLED, UNKNOWN)

#: The only values that permit execution. Anything else, including absence,
#: blocks. A source whose terms nobody has read is UNKNOWN, and UNKNOWN is not
#: permission.
ACTIVATION_PERMITS = "activation_approved"
TERMS_PERMITS = "terms_approved"
HUMAN_REVIEW_PERMITS = "human_review_cleared"

BLOCK_ACTIVATION = "source_activation_not_approved"
BLOCK_TERMS = "source_terms_not_approved"
BLOCK_HUMAN_REVIEW = "source_requires_human_review"
BLOCK_DISABLED = "source_is_disabled"
BLOCK_NO_CADENCE = "no_check_interval_recorded"
BLOCK_UNKNOWN_SOURCE = "source_is_not_in_the_registry"
BLOCK_NO_COLLECTOR = "no_collector_is_registered_for_this_source"

#: Constant. Gate 156 builds a runtime; it does not run collectors.
COLLECTOR_INVOCATION_IS_OUT_OF_SCOPE = (
    "Gate 156 evaluates schedules. Invoking a collector is Gate 161, and no "
    "code path here can reach one."
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_datetime(value: Any) -> datetime | None:
    """Parse a timestamp without raising. An unparseable time is unknown."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_interval_days(value: Any) -> int | None:
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None
    return days if days > 0 else None


def compute_next_run_at(
    *,
    last_checked_at: Any = None,
    check_interval_days: Any = None,
    recorded_next_check_due_at: Any = None,
) -> dict[str, Any]:
    """Turn an interval and a last check into the next due time.

    This is the function Gates 98-100 do not have. `evaluate_schedule` takes a
    due date; something has to produce one.

    A recorded `next_check_due_at` wins when present - the registry is the
    authority on a date somebody set deliberately - and is reported alongside
    the computed value so a disagreement is visible rather than silently
    resolved.

    No cadence means `None`, not "now". A source nobody has set an interval for
    is a source nobody has decided the cadence for, and reading that as "check
    it immediately" is exactly backwards.
    """
    recorded = _as_datetime(recorded_next_check_due_at)
    last = _as_datetime(last_checked_at)
    interval = _as_interval_days(check_interval_days)

    computed = last + timedelta(days=interval) if (last and interval) else None

    if recorded is not None:
        source_of_truth = "recorded"
        resolved = recorded
    elif computed is not None:
        source_of_truth = "computed"
        resolved = computed
    else:
        source_of_truth = "undetermined"
        resolved = None

    return _json_safe(
        {
            "next_run_at": resolved.isoformat() if resolved else None,
            "computed_next_run_at": computed.isoformat() if computed else None,
            "recorded_next_check_due_at": recorded.isoformat() if recorded else None,
            "source_of_truth": source_of_truth,
            "disagrees": bool(
                recorded is not None and computed is not None and recorded != computed
            ),
            "check_interval_days": interval,
            "last_checked_at": last.isoformat() if last else None,
            "no_cadence_means_never_due": interval is None,
        }
    )


def _permits(value: Any, permitting: str) -> bool:
    return str(value or "").strip().lower() == permitting


def evaluate_source_schedule(
    *,
    source_id: Any = None,
    now: Any = None,
    last_checked_at: Any = None,
    check_interval_days: Any = None,
    recorded_next_check_due_at: Any = None,
    activation_state: Any = None,
    terms_state: Any = None,
    human_review_state: Any = None,
    is_enabled: Any = None,
    collector_registered: Any = None,
    known_source: bool = True,
) -> dict[str, Any]:
    """Evaluate one source against the clock. Runs nothing."""
    moment = _as_datetime(now)
    timing = compute_next_run_at(
        last_checked_at=last_checked_at,
        check_interval_days=check_interval_days,
        recorded_next_check_due_at=recorded_next_check_due_at,
    )
    next_run = _as_datetime(timing["next_run_at"])

    blockers: list[str] = []
    if not known_source:
        blockers.append(BLOCK_UNKNOWN_SOURCE)
    if is_enabled is False:
        blockers.append(BLOCK_DISABLED)
    if not _permits(activation_state, ACTIVATION_PERMITS):
        blockers.append(BLOCK_ACTIVATION)
    if not _permits(terms_state, TERMS_PERMITS):
        blockers.append(BLOCK_TERMS)
    if not _permits(human_review_state, HUMAN_REVIEW_PERMITS):
        blockers.append(BLOCK_HUMAN_REVIEW)
    if not collector_registered:
        blockers.append(BLOCK_NO_COLLECTOR)
    if timing["check_interval_days"] is None:
        blockers.append(BLOCK_NO_CADENCE)

    # `due` is a fact about a clock. It is computed even for a blocked source,
    # because "it is overdue AND it is blocked" is the useful answer - hiding
    # the first behind the second is how a backlog becomes invisible.
    is_due = bool(moment and next_run and next_run <= moment)

    if not known_source:
        state = UNKNOWN
    elif is_enabled is False:
        state = DISABLED
    elif blockers:
        state = BLOCKED
    elif next_run is None or moment is None:
        state = WAITING
    elif is_due:
        state = DUE
    else:
        state = SCHEDULED

    # Affirmative, not "no blockers". Each prerequisite must be the permitting
    # value; absence is never permission.
    executable = bool(
        known_source
        and is_enabled is not False
        and _permits(activation_state, ACTIVATION_PERMITS)
        and _permits(terms_state, TERMS_PERMITS)
        and _permits(human_review_state, HUMAN_REVIEW_PERMITS)
        and collector_registered
        and is_due
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "source_id": str(source_id) if source_id is not None else None,
            "evaluated_at": moment.isoformat() if moment else None,
            "runtime_state": state,
            "due": is_due,
            "executable": executable,
            "blockers": sorted(set(blockers)),
            "blocker_count": len(set(blockers)),
            "activation_state": str(activation_state or "unknown"),
            "terms_state": str(terms_state or "unknown"),
            "human_review_state": str(human_review_state or "unknown"),
            "collector_registered": bool(collector_registered),
            "is_enabled": is_enabled is not False,
            **timing,
            # Constants. This module computes and refuses.
            "collector_invoked": False,
            "live_source_called": False,
            "network_calls": 0,
            "rows_written": 0,
            "source_monitoring_live": False,
            "api_key_required": False,
            "collector_invocation_scope": COLLECTOR_INVOCATION_IS_OUT_OF_SCOPE,
        }
    )


def schedule_evaluation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse an evaluation that permitted more than the inputs allow."""
    fails: list[str] = []

    if result.get("runtime_state") not in RUNTIME_STATES:
        fails.append(f"runtime_state_outside_vocabulary:{result.get('runtime_state')}")

    if result.get("executable"):
        if result.get("blockers"):
            fails.append("executable_alongside_blockers")
        if not result.get("due"):
            fails.append("executable_while_not_due")
        if result.get("runtime_state") != DUE:
            fails.append("executable_while_state_is_not_due")
        for field, permitting in (
            ("activation_state", ACTIVATION_PERMITS),
            ("terms_state", TERMS_PERMITS),
            ("human_review_state", HUMAN_REVIEW_PERMITS),
        ):
            if not _permits(result.get(field), permitting):
                fails.append(f"executable_without:{field}")
        if not result.get("collector_registered"):
            fails.append("executable_without_a_collector")

    if result.get("blocker_count") != len(result.get("blockers") or []):
        fails.append("blocker_count_disagrees")

    # The four this gate exists to hold.
    for flag in ("collector_invoked", "live_source_called", "source_monitoring_live"):
        if result.get(flag):
            fails.append(f"runtime_claimed:{flag}")
    for counter in ("network_calls", "rows_written"):
        if result.get(counter):
            fails.append(f"runtime_counted:{counter}")

    return sorted(set(fails))
