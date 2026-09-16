"""Gate 157D: what is worth trying again, and what is not.

## The distinction the whole policy rests on

```text
refused_by_activation      NOT a retry
terms_blocked              NOT a retry
human_review_blocked       NOT a retry
permanent_worker_failure   NOT a retry
transient_worker_failure   the ONLY class that retries
```

An activation refusal is not a hiccup. No approval exists, and none will appear
because a worker tried again in five minutes. Retrying it would produce a worker
that looks busy, burns its attempt budget on jobs that can never run, and never
surfaces that 171 sources are waiting on a person to read their terms.

With zero approved sources, **every one of the 177 registry jobs lands in a
non-retrying class today.** A retry queue that filled up here would be the
clearest possible sign the classification was wrong.

## Bounded, and bounded in the database

`max_attempts` lives on the lease row, not in this module's memory. A worker
that kept its budget in memory would reset it on every crash — precisely when a
bound matters most.

## Deterministic backoff

```text
attempt 1 -> 60s     attempt 2 -> 120s     attempt 3 -> 240s
```

Exponential from a base, capped, and computed from the attempt number rather
than from a random draw. No jitter: jitter buys herd-avoidance among many
workers, there is one worker, and a reproducible next-retry time is worth more
than a theoretical thundering herd this system cannot have.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

SCHEMA_VERSION = "nf_source_collection_retry_policy_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

NONE = "none"
REFUSED_BY_ACTIVATION = "refused_by_activation"
TERMS_BLOCKED = "terms_blocked"
HUMAN_REVIEW_BLOCKED = "human_review_blocked"
TRANSIENT_WORKER_FAILURE = "transient_worker_failure"
PERMANENT_WORKER_FAILURE = "permanent_worker_failure"
UNKNOWN = "unknown"

FAILURE_CLASSES: tuple[str, ...] = (
    NONE,
    REFUSED_BY_ACTIVATION,
    TERMS_BLOCKED,
    HUMAN_REVIEW_BLOCKED,
    TRANSIENT_WORKER_FAILURE,
    PERMANENT_WORKER_FAILURE,
    UNKNOWN,
)

#: The only class that retries. A frozenset of one, written as a set so the
#: rule is a lookup rather than an `if` somebody can extend by accident.
RETRYABLE_CLASSES: frozenset[str] = frozenset({TRANSIENT_WORKER_FAILURE})

#: Why each non-retrying class does not retry. An operator asking "why is this
#: not being retried" gets an answer rather than a policy name.
WHY_NOT_RETRIED: dict[str, str] = {
    REFUSED_BY_ACTIVATION: (
        "no activation approval exists. Trying again changes nothing, and a "
        "retry queue full of unapprovable jobs hides the real backlog."
    ),
    TERMS_BLOCKED: "a human must read this source's terms of use",
    HUMAN_REVIEW_BLOCKED: "a human must look at this source",
    PERMANENT_WORKER_FAILURE: (
        "the handler is wrong. Retrying a deterministic failure produces the "
        "same failure, more often."
    ),
    NONE: "nothing failed",
    UNKNOWN: (
        "the failure was not classified, and an unclassified failure is not "
        "assumed transient - assuming it would make UNKNOWN a retry loop"
    ),
}

#: Blocker strings the scheduler emits, mapped to the class they mean. Mapped
#: by exact value, not by substring: `source_terms_not_approved` and
#: `source_activation_not_approved` share most of their characters.
BLOCKER_TO_CLASS: dict[str, str] = {
    "source_activation_not_approved": REFUSED_BY_ACTIVATION,
    "source_terms_not_approved": TERMS_BLOCKED,
    "source_requires_human_review": HUMAN_REVIEW_BLOCKED,
    "source_is_disabled": REFUSED_BY_ACTIVATION,
    "source_is_not_in_the_registry": PERMANENT_WORKER_FAILURE,
    "no_collector_is_registered_for_this_source": REFUSED_BY_ACTIVATION,
    "no_check_interval_recorded": REFUSED_BY_ACTIVATION,
}

BASE_BACKOFF_SECONDS = 60
MAX_BACKOFF_SECONDS = 3600
DEFAULT_MAX_ATTEMPTS = 3


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def classify_blockers(blockers: list[str] | None) -> str:
    """Turn a scheduler's blocker list into one failure class.

    Ordered: a source that is both terms-blocked and unapproved is reported as
    terms-blocked, because the terms review is the thing a person does first
    and naming the later blocker would send them to the wrong queue.

    Matched by exact value. `source_terms_not_approved` and
    `source_activation_not_approved` differ by one word, and a substring match
    over either would catch the other.
    """
    found = {BLOCKER_TO_CLASS.get(str(b)) for b in (blockers or [])}
    for candidate in (
        TERMS_BLOCKED,
        HUMAN_REVIEW_BLOCKED,
        REFUSED_BY_ACTIVATION,
        PERMANENT_WORKER_FAILURE,
    ):
        if candidate in found:
            return candidate
    if blockers:
        # Blocked by something nobody mapped. Not assumed transient.
        return UNKNOWN
    return NONE


def compute_backoff_seconds(attempt_number: Any) -> int:
    """Deterministic exponential backoff, capped. No jitter."""
    try:
        attempt = max(1, int(attempt_number))
    except (TypeError, ValueError):
        attempt = 1
    return min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)


def evaluate_retry(
    *,
    failure_class: Any = None,
    attempt_count: Any = 0,
    max_attempts: Any = DEFAULT_MAX_ATTEMPTS,
    now: Any = None,
) -> dict[str, Any]:
    """Should this job be tried again, and when? Decides; runs nothing."""
    klass = str(failure_class or NONE)
    if klass not in FAILURE_CLASSES:
        klass = UNKNOWN

    try:
        attempts = max(0, int(attempt_count))
    except (TypeError, ValueError):
        attempts = 0
    try:
        budget = max(1, int(max_attempts))
    except (TypeError, ValueError):
        budget = DEFAULT_MAX_ATTEMPTS

    class_retries = klass in RETRYABLE_CLASSES
    budget_remains = attempts < budget
    should_retry = bool(class_retries and budget_remains)

    reasons: list[str] = []
    if not class_retries:
        reasons.append(f"failure_class_does_not_retry:{klass}")
    if not budget_remains:
        reasons.append("attempt_budget_exhausted")

    moment = _as_datetime(now)
    backoff = compute_backoff_seconds(attempts + 1) if should_retry else None
    next_retry = (
        (moment + timedelta(seconds=backoff)).isoformat()
        if should_retry and moment and backoff
        else None
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "failure_class": klass,
            "attempt_count": attempts,
            "max_attempts": budget,
            "attempts_remaining": max(0, budget - attempts),
            "class_retries": class_retries,
            "budget_remains": budget_remains,
            "should_retry": should_retry,
            "not_retried_because": sorted(reasons),
            "why_not_retried": WHY_NOT_RETRIED.get(klass)
            if not class_retries
            else None,
            "backoff_seconds": backoff,
            "next_retry_at": next_retry,
            "retryable_classes": sorted(RETRYABLE_CLASSES),
            "backoff_is_deterministic": True,
            "jitter": False,
            # Constants. A policy decides.
            "collector_invoked": False,
            "live_source_called": False,
            "rows_written": 0,
        }
    )


def retry_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a retry decision that would loop, or retry a human blocker."""
    fails: list[str] = []

    klass = decision.get("failure_class")
    if klass not in FAILURE_CLASSES:
        fails.append(f"failure_class_outside_vocabulary:{klass}")

    if decision.get("should_retry"):
        # The four that must never retry, each named so a failure says which.
        if klass not in RETRYABLE_CLASSES:
            fails.append(f"retried_a_non_transient_failure:{klass}")
        if not decision.get("budget_remains"):
            fails.append("retried_beyond_the_attempt_budget")
        if decision.get("not_retried_because"):
            fails.append("should_retry_alongside_a_reason_not_to")
        if not decision.get("backoff_seconds"):
            fails.append("retry_without_a_backoff")

    attempts = int(decision.get("attempt_count") or 0)
    budget = int(decision.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
    if attempts > budget:
        fails.append("attempt_count_exceeded_the_budget")
    if decision.get("attempts_remaining") != max(0, budget - attempts):
        fails.append("attempts_remaining_disagrees")

    backoff = decision.get("backoff_seconds")
    if backoff is not None and int(backoff) > MAX_BACKOFF_SECONDS:
        fails.append("backoff_exceeded_the_cap")

    if decision.get("jitter"):
        fails.append("backoff_is_not_deterministic")

    for flag in ("collector_invoked", "live_source_called"):
        if decision.get(flag):
            fails.append(f"retry_policy_claimed:{flag}")

    return sorted(set(fails))
