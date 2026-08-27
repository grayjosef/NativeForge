"""Source schedule decision (Gate 98B).

Decides whether a source is *due* for a check, and separately whether it is
*safe* to act on that. It never performs a check and never enqueues one.

## Due is not safe, and safe to enqueue is not safe to execute

Three separate answers, and they fail independently:

``due_for_check``        the clock says it is time
``safe_to_enqueue``      it may be put on a queue
``safe_to_execute_now``  a request may go out immediately

A source can be overdue by a week and still be unsafe to touch: its terms may
need review, its circuit may be open, or the production payload store may not
exist to hold what comes back. Collapsing the three is how a scheduler ends up
hammering a host it was never allowed to contact.

``safe_to_execute_now`` is a constant ``False`` in this gate. Nothing executes,
so a decision that could return True would be describing a capability that does
not exist, and an invariant enforces it.

## Five statuses

``not_due``                  the clock has not come round
``due_but_blocked``          it is time, and something says no
``due_and_safe_to_enqueue``  it is time and every precondition holds
``disabled``                 monitoring is off for this source
``unknown``                  the inputs do not describe a state

## A missing due date is a question, not a licence

``next_check_due_at`` absent produces ``unknown`` and requires human review. The
tempting reading - "never checked, so check it now" - is exactly backwards: a
source with no schedule is a source nobody has decided the cadence for, and
picking one automatically is picking it arbitrarily.

## Everything defaults to blocked

Every status input resolves to its blocking member when absent or unrecognised.
A typo blocks. A vocabulary this code has not been taught blocks.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_circuit_breaker_service import (
    CIRCUIT_STATUSES,
    SCHEDULING_PERMITTED_STATUSES,
)

SCHEMA_VERSION = "nf_source_schedule_decision_v1"

SCHEDULE_STATUSES = frozenset(
    {
        "not_due",
        "due_but_blocked",
        "due_and_safe_to_enqueue",
        "disabled",
        "unknown",
    }
)

# The one status that permits a scheduler to act.
ENQUEUE_PERMITTED_STATUSES = frozenset({"due_and_safe_to_enqueue"})

COLLECTOR_STATUSES = frozenset({"not_active", "activating", "active", "halted"})
COLLECTOR_SATISFYING = frozenset({"active"})

ACTIVATION_STATUSES = frozenset(
    {
        "activation_allowed",
        "activation_blocked",
        "activation_requires_human_review",
        "activation_unknown",
    }
)
ACTIVATION_SATISFYING = frozenset({"activation_allowed"})

# Gate 93's monitoring vocabulary, extended with the two states a scheduler
# needs to tell apart: never started, and deliberately switched off.
MONITORING_STATUSES = frozenset(
    {"not_started", "enabled", "active", "paused", "disabled", "unknown"}
)
MONITORING_SATISFYING = frozenset({"enabled", "active"})
MONITORING_DISABLED = frozenset({"disabled", "paused"})

TERMS_BLOCKING = frozenset({"TERMS_REVIEW_REQUIRED", "UNKNOWN"})
TERMS_HUMAN_ONLY = frozenset({"HUMAN_REVIEW_ONLY"})
TERMS_NON_BLOCKING = frozenset({"NO_REVIEW_REQUIRED", "ATTRIBUTION_REQUIRED"})
ALL_TERMS_STATUSES = TERMS_BLOCKING | TERMS_HUMAN_ONLY | TERMS_NON_BLOCKING

HUMAN_REVIEW_STATUSES = frozenset(
    {"not_required", "pending", "approved", "rejected", "unknown"}
)
HUMAN_REVIEW_SATISFYING = frozenset({"not_required", "approved"})

# Every requirement, in reporting order.
REQUIREMENT_KEYS: tuple[str, ...] = (
    "collector_active",
    "activation_allowed",
    "monitoring_enabled",
    "terms_cleared",
    "human_review_cleared",
    "circuit_permits",
    "production_payload_store",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _due_comparison(*, now: Any, next_check_due_at: Any) -> bool | None:
    """True when due, False when not, None when not derivable."""
    from datetime import datetime

    def _parse(value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "timestamp"):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    current, due = _parse(now), _parse(next_check_due_at)
    if current is None or due is None:
        return None
    try:
        return current >= due
    except TypeError:
        # Naive vs aware. Comparing them would invent a timezone.
        return None


def evaluate_schedule(
    *,
    source_id: Any,
    now: Any,
    next_check_due_at: Any = None,
    check_interval_seconds: Any = None,
    collector_status: Any = None,
    activation_status: Any = None,
    monitoring_status: Any = None,
    terms_status: Any = None,
    human_review_status: Any = None,
    circuit_status: Any = None,
    production_raw_payload_store_available: bool = False,
) -> dict[str, Any]:
    """Is this source due, and may anything be done about it?"""
    collector = _norm(collector_status, COLLECTOR_STATUSES, fallback="not_active")
    activation = _norm(
        activation_status, ACTIVATION_STATUSES, fallback="activation_unknown"
    )
    monitoring = _norm(monitoring_status, MONITORING_STATUSES, fallback="unknown")
    terms = _norm(terms_status, ALL_TERMS_STATUSES, fallback="UNKNOWN")
    human_review = _norm(
        human_review_status, HUMAN_REVIEW_STATUSES, fallback="unknown"
    )
    circuit = _norm(circuit_status, CIRCUIT_STATUSES, fallback="unknown")

    satisfied: list[str] = []
    missing: list[str] = []
    blocked: list[str] = []

    def record(key: str, ok: bool, reason: str) -> None:
        if ok:
            satisfied.append(key)
        else:
            missing.append(key)
            blocked.append(reason)

    record(
        "collector_active",
        collector in COLLECTOR_SATISFYING,
        f"collector_not_active:{collector}",
    )
    record(
        "activation_allowed",
        activation in ACTIVATION_SATISFYING,
        f"activation_not_allowed:{activation}",
    )
    record(
        "monitoring_enabled",
        monitoring in MONITORING_SATISFYING,
        f"monitoring_not_enabled:{monitoring}",
    )
    record(
        "terms_cleared",
        terms in TERMS_NON_BLOCKING,
        f"terms_status_blocks:{terms}",
    )
    human_review_required = terms in TERMS_HUMAN_ONLY
    record(
        "human_review_cleared",
        human_review in HUMAN_REVIEW_SATISFYING and not human_review_required,
        f"human_review_not_cleared:{human_review}",
    )
    record(
        "circuit_permits",
        circuit in SCHEDULING_PERMITTED_STATUSES,
        f"circuit_does_not_permit:{circuit}",
    )
    # A check whose bytes have nowhere durable to land is a check that produces
    # a record nobody can later verify - the 185/18 corpus split, repeated.
    record(
        "production_payload_store",
        bool(production_raw_payload_store_available),
        "production_raw_payload_store_unavailable",
    )

    # The clock, evaluated separately from permission.
    due = _due_comparison(now=now, next_check_due_at=next_check_due_at)
    schedule_unknown = due is None
    if schedule_unknown:
        if next_check_due_at is None or not str(next_check_due_at).strip():
            blocked.append("next_check_due_at_absent")
        else:
            blocked.append("next_check_due_at_not_comparable_to_now")

    monitoring_off = monitoring in MONITORING_DISABLED

    if monitoring_off:
        status = "disabled"
    elif schedule_unknown:
        # No schedule is a question for a person, not a licence to run now.
        status = "unknown"
    elif not due:
        status = "not_due"
    elif missing:
        status = "due_but_blocked"
    else:
        status = "due_and_safe_to_enqueue"

    safe_to_enqueue = status in ENQUEUE_PERMITTED_STATUSES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "schedule_status": status,
            "due_for_check": bool(due) if due is not None else False,
            "due_derivable": not schedule_unknown,
            "next_check_due_at": next_check_due_at,
            "check_interval_seconds": check_interval_seconds,
            "safe_to_enqueue": safe_to_enqueue,
            # Constant for this gate. Nothing executes.
            "safe_to_execute_now": False,
            "human_review_required": human_review_required
            or (status == "unknown" and not monitoring_off),
            "requirements_satisfied": sorted(satisfied),
            "requirements_missing": sorted(missing),
            "blocked_reasons": sorted(set(blocked)),
            "resolved_inputs": {
                "collector_status": collector,
                "activation_status": activation,
                "monitoring_status": monitoring,
                "terms_status": terms,
                "human_review_status": human_review,
                "circuit_status": circuit,
                "production_raw_payload_store_available": bool(
                    production_raw_payload_store_available
                ),
            },
            # This service decides. It never queues and never fetches.
            "enqueued": False,
            "check_executed": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def summarise_schedule(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(SCHEDULE_STATUSES)}
    for decision in decisions:
        status = decision.get("schedule_status")
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evaluated_count": len(decisions),
            "by_schedule_status": by_status,
            "due_count": sum(1 for d in decisions if d.get("due_for_check")),
            "safe_to_enqueue_count": sum(
                1 for d in decisions if d.get("safe_to_enqueue")
            ),
            "safe_to_execute_now_count": 0,
            "enqueued_count": 0,
            "checks_executed": 0,
            "fabricated": False,
        }
    )


def schedule_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("enqueued", "check_executed", "fetch_performed"):
        if decision.get(constant) is not False:
            fails.append(f"decision_claimed:{constant}")

    # Gate 98 constant.
    if decision.get("safe_to_execute_now") is not False:
        fails.append("decision_claimed_safe_to_execute_now")

    status = decision.get("schedule_status")
    if status not in SCHEDULE_STATUSES:
        fails.append("schedule_status_out_of_vocabulary")

    # safe_to_enqueue is derived from the single permitting status.
    if decision.get("safe_to_enqueue") != (status in ENQUEUE_PERMITTED_STATUSES):
        fails.append("safe_to_enqueue_disagrees_with_status")

    if decision.get("safe_to_enqueue"):
        if decision.get("requirements_missing"):
            fails.append("enqueue_permitted_with_missing_requirements")
        if decision.get("blocked_reasons"):
            fails.append("enqueue_permitted_with_blocked_reasons")
        if not decision.get("due_for_check"):
            fails.append("enqueue_permitted_while_not_due")
        if decision.get("human_review_required"):
            fails.append("enqueue_permitted_while_requiring_human_review")

    # Being due never implies permission.
    resolved = decision.get("resolved_inputs") or {}
    if decision.get("safe_to_enqueue"):
        if resolved.get("collector_status") not in COLLECTOR_SATISFYING:
            fails.append("enqueue_permitted_with_an_inactive_collector")
        if resolved.get("activation_status") not in ACTIVATION_SATISFYING:
            fails.append("enqueue_permitted_without_activation")
        if resolved.get("circuit_status") not in SCHEDULING_PERMITTED_STATUSES:
            fails.append("enqueue_permitted_with_a_blocking_circuit")
        if resolved.get("terms_status") in TERMS_BLOCKING | TERMS_HUMAN_ONLY:
            fails.append("enqueue_permitted_with_blocking_terms")
        if not resolved.get("production_raw_payload_store_available"):
            fails.append("enqueue_permitted_without_a_production_payload_store")

    # A missing schedule must not read as due.
    if not decision.get("due_derivable"):
        if decision.get("due_for_check"):
            fails.append("undeterminable_schedule_reported_due")
        if status not in {"unknown", "disabled"}:
            fails.append("undeterminable_schedule_not_reported_unknown")

    # Every requirement accounted for exactly once.
    satisfied = set(decision.get("requirements_satisfied") or [])
    missing = set(decision.get("requirements_missing") or [])
    if satisfied & missing:
        fails.append("requirement_both_satisfied_and_missing")
    if satisfied | missing != set(REQUIREMENT_KEYS):
        fails.append("requirement_dropped_from_the_checklist")

    if not decision.get("safe_to_enqueue") and not decision.get("blocked_reasons"):
        if status not in {"not_due"}:
            fails.append("refusal_without_a_reason")

    return fails
