"""What a transport outcome means for a retry (Gate 161J).

Gate 157 classifies a SCHEDULER's blockers. This classifies an EXECUTION's
outcome, and hands the result to the same `evaluate_retry` rather than growing a
second backoff schedule beside it.

```text
timeout                     transient   the source may answer next time
connection_failed           transient   likewise
429 rate limited            transient   and the source SAID when: Retry-After
5xx                         transient   the source is unwell, not wrong
404 / 410                   permanent   the URL is wrong; waiting will not fix it
401 / 403                   permanent   credentials, and a retry is a second
                                        unauthorized request
400 / 422                   permanent   we built the request wrong
malformed body              NOT a failure - the bytes are persisted
refused before dispatch     not retryable - a refusal is a decision
activation / terms / human  not retryable - a human decides, not a timer
```

## The 429 case is the one with a right answer

A source that returns `Retry-After: 120` has told us when to come back.
Recomputing our own backoff would be choosing to ignore it, and ignoring a rate
limit is how polite collection becomes impolite collection. So when the header
is present and sane, it WINS over the computed schedule, and the decision says
which of the two it used.

The header is still bounded: a source claiming `Retry-After: 999999` does not
get to park a job for eleven days. `MAX_RETRY_AFTER_SECONDS` caps it, and the
cap is reported rather than applied silently.

## Malformed is not a failure

A 200 whose body no parser accepts still transported, still hashed, still
persisted. Retrying it would re-fetch bytes we already hold, and would do it on
a schedule meant for sources that did not answer. The parse is a later gate's
problem; this one records that the response arrived.

## A refusal is not a failure either

`refused_before_dispatch` means the policy, the boundary or the request builder
said no. Nothing failed, so nothing is retried - a timer cannot turn a refusal
into an approval, and a retry loop around one is how a refusal quietly becomes
a poll.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_retry_policy_service import (
    HUMAN_REVIEW_BLOCKED,
    NONE,
    PERMANENT_WORKER_FAILURE,
    REFUSED_BY_ACTIVATION,
    TERMS_BLOCKED,
    TRANSIENT_WORKER_FAILURE,
    evaluate_retry,
    retry_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    OUTCOME_CONNECTION_FAILED,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_REFUSED,
    OUTCOME_TIMEOUT,
)

SCHEMA_VERSION = "nf_source_collection_execution_retry_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: A source's own Retry-After is honoured up to here. Past it, the cap applies
#: and the decision says so rather than quietly shortening the wait.
MAX_RETRY_AFTER_SECONDS = 3600

#: Transport outcome -> failure class, for outcomes that carry no status code.
OUTCOME_TO_CLASS: dict[str, str] = {
    OUTCOME_TIMEOUT: TRANSIENT_WORKER_FAILURE,
    OUTCOME_CONNECTION_FAILED: TRANSIENT_WORKER_FAILURE,
    # A refusal is a decision. Nothing failed, so nothing is retried.
    OUTCOME_REFUSED: NONE,
    # The bytes arrived and are stored. Parsing is a later gate's problem.
    OUTCOME_MALFORMED: NONE,
    OUTCOME_OK: NONE,
}

#: HTTP status -> failure class. Anything not named here falls to the ranges.
STATUS_TO_CLASS: dict[int, str] = {
    401: PERMANENT_WORKER_FAILURE,
    403: PERMANENT_WORKER_FAILURE,
    404: PERMANENT_WORKER_FAILURE,
    410: PERMANENT_WORKER_FAILURE,
    400: PERMANENT_WORKER_FAILURE,
    422: PERMANENT_WORKER_FAILURE,
    408: TRANSIENT_WORKER_FAILURE,
    429: TRANSIENT_WORKER_FAILURE,
}

#: Reasons a human decides, never a timer. Matched exactly.
HUMAN_DECIDES: dict[str, str] = {
    "refused_by_activation": REFUSED_BY_ACTIVATION,
    "terms_blocked": TERMS_BLOCKED,
    "human_review_blocked": HUMAN_REVIEW_BLOCKED,
    "the_live_network_guard_refused": REFUSED_BY_ACTIVATION,
    "hermetic_execution_requires_a_synthetic_fixture_source": (
        REFUSED_BY_ACTIVATION
    ),
}

WHY: dict[str, str] = {
    OUTCOME_TIMEOUT: "the source did not answer in time, and may next time",
    OUTCOME_CONNECTION_FAILED: "the connection did not open, and may next time",
    OUTCOME_REFUSED: (
        "nothing was dispatched. A refusal is a decision, and a timer cannot "
        "turn one into an approval"
    ),
    OUTCOME_MALFORMED: (
        "the bytes arrived and are persisted. Retrying would re-fetch what we "
        "already hold, on a schedule meant for sources that did not answer"
    ),
    OUTCOME_OK: "the response arrived",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _retry_after_seconds(headers: Any) -> tuple[int | None, list[str]]:
    """Read `Retry-After`, in seconds, or say why it was not usable.

    Only the delta-seconds form. The HTTP-date form is valid and is NOT parsed
    here: parsing it needs a clock, this module has none by design, and a
    misparsed date silently becomes either a hammer or an eleven-day pause.
    Saying "unparsed" and falling back to the computed schedule is the
    conservative half of that trade.
    """
    notes: list[str] = []
    if not isinstance(headers, dict):
        return None, notes
    raw = None
    for name, value in headers.items():
        if str(name).strip().lower() == "retry-after":
            raw = value
            break
    if raw is None:
        return None, notes

    text = str(raw).strip()
    try:
        seconds = int(text)
    except ValueError:
        notes.append("retry_after_was_not_delta_seconds_so_it_was_not_used")
        return None, notes

    if seconds < 0:
        notes.append("retry_after_was_negative_so_it_was_not_used")
        return None, notes
    if seconds > MAX_RETRY_AFTER_SECONDS:
        notes.append(
            f"retry_after_{seconds}s_exceeded_the_cap_and_was_capped_to_"
            f"{MAX_RETRY_AFTER_SECONDS}s"
        )
        return MAX_RETRY_AFTER_SECONDS, notes
    return seconds, notes


def classify_execution_outcome(
    *,
    outcome: Any = None,
    http_status: Any = None,
    refusal_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """One failure class for one execution, and the reason it was chosen."""
    reasons = list(refusal_reasons or [])
    text = str(outcome or "").strip()

    # A human blocker outranks everything. It is matched by exact reason, never
    # by substring: `terms_blocked` and "why terms_blocked must not appear" are
    # the same string to a substring test.
    for reason in reasons:
        if reason in HUMAN_DECIDES:
            return _json_safe(
                {
                    "schema_version": SCHEMA_VERSION,
                    "scope": CONTROLLED_SCOPE,
                    "failure_class": HUMAN_DECIDES[reason],
                    "decided_by": "a_human_blocker",
                    "decided_from": reason,
                    "outcome": text or None,
                    "http_status": None,
                    "why": "a human decides this, not a timer",
                }
            )

    # A response with a status is classified by the status, because `429` and
    # `404` are the same transport outcome and opposite retry decisions.
    status = None
    try:
        status = int(http_status) if http_status is not None else None
    except (TypeError, ValueError):
        status = None

    if text.startswith("response_received") and status is not None:
        if status in STATUS_TO_CLASS:
            failure = STATUS_TO_CLASS[status]
            source = f"status:{status}"
        elif 500 <= status <= 599:
            failure = TRANSIENT_WORKER_FAILURE
            source = "status:5xx"
        elif 400 <= status <= 499:
            failure = PERMANENT_WORKER_FAILURE
            source = "status:4xx"
        else:
            # 2xx and 3xx. The response arrived; nothing is being retried.
            failure = NONE
            source = "status:not_an_error"
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "failure_class": failure,
                "decided_by": "the_http_status",
                "decided_from": source,
                "outcome": text,
                "http_status": status,
                "why": (
                    WHY.get(text)
                    if failure == NONE
                    else (
                        "the source is unwell rather than wrong"
                        if failure == TRANSIENT_WORKER_FAILURE
                        else "waiting will not change this answer"
                    )
                ),
            }
        )

    failure = OUTCOME_TO_CLASS.get(text)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "failure_class": failure if failure is not None else "unknown",
            "decided_by": (
                "the_transport_outcome" if failure is not None else "nothing"
            ),
            "decided_from": text or None,
            "outcome": text or None,
            "http_status": status,
            "why": WHY.get(text, "the outcome is not one this gate recognises"),
        }
    )


def evaluate_execution_retry(
    *,
    outcome: Any = None,
    http_status: Any = None,
    response_headers: Any = None,
    refusal_reasons: list[str] | None = None,
    attempt_count: Any = 0,
    max_attempts: Any = 3,
    now: Any = None,
) -> dict[str, Any]:
    """Classify the outcome, then ask Gate 157's retry policy what to do.

    Composes `evaluate_retry` rather than reimplementing backoff. One schedule
    or two is the difference between a policy and a coincidence.
    """
    classification = classify_execution_outcome(
        outcome=outcome, http_status=http_status, refusal_reasons=refusal_reasons
    )
    failure_class = classification["failure_class"]

    decision = evaluate_retry(
        failure_class=failure_class,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        now=now,
    )
    failures = list(retry_invariant_failures(decision))

    # ---- the source's own instruction ------------------------------------
    retry_after, notes = _retry_after_seconds(response_headers)
    honoured = False
    next_retry_at = decision["next_retry_at"]
    backoff = decision.get("backoff_seconds")

    if retry_after is not None and decision["should_retry"]:
        # The source said when. Recomputing our own delay would be choosing to
        # ignore it, and ignoring a rate limit is how polite collection stops
        # being polite.
        honoured = True
        backoff = retry_after
        next_retry_at = _shift(now, retry_after)
        if next_retry_at is None:
            honoured = False
            backoff = decision.get("backoff_seconds")
            next_retry_at = decision["next_retry_at"]
            notes.append("no_clock_supplied_so_retry_after_could_not_be_applied")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "failure_class": failure_class,
            "classification": classification,
            "should_retry": decision["should_retry"],
            "why_not_retried": decision["why_not_retried"],
            # `why_not_retried` is None when the CLASS retries but the
            # budget is spent, so the list is carried too. Checking only
            # the prose would report a silent refusal for the one case
            # that has the clearest reason of all.
            "not_retried_because": decision.get("not_retried_because") or [],
            "attempt_count": decision.get("attempt_count"),
            "max_attempts": decision.get("max_attempts"),
            "backoff_seconds": backoff,
            "computed_backoff_seconds": decision.get("backoff_seconds"),
            "next_retry_at": next_retry_at,
            "retry_after_seconds": retry_after,
            "retry_after_was_honoured": honoured,
            "retry_after_notes": sorted(set(notes)),
            "schedule_source": (
                "the_sources_retry_after" if honoured else "the_computed_backoff"
            ),
            "max_retry_after_seconds": MAX_RETRY_AFTER_SECONDS,
            "invariant_failures": sorted(set(failures)),
            # A retry decision contacts nothing.
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def _shift(now: Any, seconds: int) -> Any:
    """`now + seconds`, or None when there is no clock to shift."""
    try:
        from datetime import UTC, datetime, timedelta
    except ImportError:  # pragma: no cover - stdlib
        return None
    if isinstance(now, datetime):
        moment = now if now.tzinfo else now.replace(tzinfo=UTC)
        return (moment + timedelta(seconds=int(seconds))).isoformat()
    text = str(now or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    moment = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return (moment + timedelta(seconds=int(seconds))).isoformat()


def execution_retry_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a retry decision that would retry something a timer cannot fix."""
    fails: list[str] = list(decision.get("invariant_failures") or [])

    failure_class = decision.get("failure_class")
    should = bool(decision.get("should_retry"))

    # THE invariant: only a transient failure is retryable. A refusal, a human
    # blocker and a permanent error are all decisions, and a retry loop around
    # a decision is how a refusal quietly becomes a poll.
    if should and failure_class != TRANSIENT_WORKER_FAILURE:
        fails.append(f"retried_a_non_transient_class:{failure_class}")

    if should and not decision.get("next_retry_at"):
        fails.append("a_retry_without_a_time_to_retry_at")
    if not should and decision.get("next_retry_at"):
        fails.append("a_time_to_retry_at_without_a_retry")
    said_why = str(decision.get("why_not_retried") or "").strip() or (
        decision.get("not_retried_because") or []
    )
    if not should and not said_why:
        fails.append("a_refusal_to_retry_that_does_not_say_why")

    # The honoured flag and the schedule it names must agree, both directions.
    honoured = bool(decision.get("retry_after_was_honoured"))
    named = decision.get("schedule_source")
    if honoured and named != "the_sources_retry_after":
        fails.append("honoured_retry_after_but_named_the_computed_schedule")
    if not honoured and named == "the_sources_retry_after":
        fails.append("named_the_sources_schedule_without_honouring_it")
    if honoured and not should:
        fails.append("honoured_a_retry_after_for_something_not_being_retried")

    after = decision.get("retry_after_seconds")
    if after is not None and int(after) > MAX_RETRY_AFTER_SECONDS:
        fails.append(f"retry_after_exceeded_the_cap:{after}")
    if honoured and decision.get("backoff_seconds") != after:
        fails.append("honoured_retry_after_but_used_a_different_delay")

    for flag in ("live_source_call", "source_monitoring_live"):
        if decision.get(flag):
            fails.append(f"retry_decision_claimed:{flag}")
    if int(decision.get("network_calls") or 0):
        fails.append("retry_decision_counted_a_network_call")

    return sorted(set(fails))
