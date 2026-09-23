"""Gate 172F/G/I: what went wrong, machine-readably, and what to do next.

Downstream code must never parse an exception string to decide whether to
retry. A free-text message is a human artefact: it changes when somebody
improves the wording, and the retry policy silently changes with it.

So a failure carries a TYPE from a closed vocabulary, plus safe detail. The
detail is for a human reading an incident; the type is what the machine acts
on.

## The distinction that matters most

```text
transport failure       retry may help
authorization failure   retry cannot help, and retrying looks like abuse
```

Gate 172I is explicit that these must not be conflated, and the existing
`source_collection_retry_policy_service` already drew that line for its own
classes. This module maps into that rather than around it: its classes stay
authoritative for the scheduler, and these types describe the world in more
detail than the scheduler needs.

## Recovery keeps the history

A source that fails twice and then succeeds is healthy NOW and had an outage.
Both facts survive: the streak resets, the history does not. Deleting the
evidence that an outage happened is how a fleet forgets it has a flaky source.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_failure_taxonomy_v1"

# ---- 172F: the closed vocabulary ---------------------------------

DNS_FAILURE = "DNS_FAILURE"
CONNECT_TIMEOUT = "CONNECT_TIMEOUT"
READ_TIMEOUT = "READ_TIMEOUT"
HTTP_4XX = "HTTP_4XX"
HTTP_5XX = "HTTP_5XX"
RATE_LIMIT = "RATE_LIMIT"
ROBOTS_RESTRICTED = "ROBOTS_RESTRICTED"
AUTHORIZATION_REFUSED = "AUTHORIZATION_REFUSED"
CONTENT_TYPE_CHANGED = "CONTENT_TYPE_CHANGED"
SCHEMA_CHANGED = "SCHEMA_CHANGED"
PARSER_EXCEPTION = "PARSER_EXCEPTION"
EMPTY_UNEXPECTED = "EMPTY_UNEXPECTED"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
REPEATED_PAGE = "REPEATED_PAGE"
CURSOR_LOOP = "CURSOR_LOOP"
NORMALIZATION_FAILURE = "NORMALIZATION_FAILURE"
CANONICAL_WRITE_FAILURE = "CANONICAL_WRITE_FAILURE"
IDENTITY_FAILURE = "IDENTITY_FAILURE"
CHANGE_PIPELINE_FAILURE = "CHANGE_PIPELINE_FAILURE"
UNKNOWN_FAILURE = "UNKNOWN_FAILURE"

FAILURE_TYPES: tuple[str, ...] = (
    DNS_FAILURE,
    CONNECT_TIMEOUT,
    READ_TIMEOUT,
    HTTP_4XX,
    HTTP_5XX,
    RATE_LIMIT,
    ROBOTS_RESTRICTED,
    AUTHORIZATION_REFUSED,
    CONTENT_TYPE_CHANGED,
    SCHEMA_CHANGED,
    PARSER_EXCEPTION,
    EMPTY_UNEXPECTED,
    PAYLOAD_TOO_LARGE,
    REPEATED_PAGE,
    CURSOR_LOOP,
    NORMALIZATION_FAILURE,
    CANONICAL_WRITE_FAILURE,
    IDENTITY_FAILURE,
    CHANGE_PIPELINE_FAILURE,
    UNKNOWN_FAILURE,
)

#: Which health dimension each failure damages. One failure, one dimension -
#: so a parser exception does not mark the transport unhealthy, and a 5xx
#: does not mark the parser unhealthy.
FAILURE_DIMENSION: dict[str, str] = {
    DNS_FAILURE: "transport_health",
    CONNECT_TIMEOUT: "transport_health",
    READ_TIMEOUT: "transport_health",
    HTTP_4XX: "source_availability_health",
    HTTP_5XX: "source_availability_health",
    RATE_LIMIT: "transport_health",
    ROBOTS_RESTRICTED: "transport_health",
    AUTHORIZATION_REFUSED: "authorization_health",
    CONTENT_TYPE_CHANGED: "schema_health",
    SCHEMA_CHANGED: "schema_health",
    PARSER_EXCEPTION: "parser_health",
    EMPTY_UNEXPECTED: "volume_health",
    PAYLOAD_TOO_LARGE: "evidence_health",
    REPEATED_PAGE: "parser_health",
    CURSOR_LOOP: "parser_health",
    NORMALIZATION_FAILURE: "parser_health",
    CANONICAL_WRITE_FAILURE: "evidence_health",
    IDENTITY_FAILURE: "evidence_health",
    CHANGE_PIPELINE_FAILURE: "evidence_health",
    UNKNOWN_FAILURE: "transport_health",
}

# ---- 172I: retry semantics, per TYPE not per guess ---------------

NO_RETRY = "NO_RETRY"
FIXED = "FIXED"
EXPONENTIAL = "EXPONENTIAL"
RETRY_AFTER = "RETRY_AFTER"

RETRY_STRATEGIES: tuple[str, ...] = (NO_RETRY, FIXED, EXPONENTIAL, RETRY_AFTER)

#: A retry strategy per failure type, with the reason. `NO_RETRY` on the
#: authorization and policy types is the load-bearing entry: retrying a
#: refusal is not persistence, it is repeating a request somebody already
#: said no to.
RETRY_BY_TYPE: dict[str, tuple[str, str]] = {
    DNS_FAILURE: (EXPONENTIAL, "a name may resolve later"),
    CONNECT_TIMEOUT: (EXPONENTIAL, "the host may be briefly unreachable"),
    READ_TIMEOUT: (EXPONENTIAL, "the response may be slow, not absent"),
    HTTP_4XX: (NO_RETRY, "the request was wrong; repeating it stays wrong"),
    HTTP_5XX: (EXPONENTIAL, "the server may recover"),
    RATE_LIMIT: (RETRY_AFTER, "the source told us when to come back"),
    ROBOTS_RESTRICTED: (NO_RETRY, "a policy refusal is not a transient error"),
    AUTHORIZATION_REFUSED: (
        NO_RETRY,
        "permission is missing; retrying is repeating a request already refused",
    ),
    CONTENT_TYPE_CHANGED: (NO_RETRY, "the adapter needs a human, not another attempt"),
    SCHEMA_CHANGED: (NO_RETRY, "the adapter needs a human, not another attempt"),
    PARSER_EXCEPTION: (NO_RETRY, "the same bytes will fail the same way"),
    EMPTY_UNEXPECTED: (FIXED, "the source may have been mid-publish"),
    PAYLOAD_TOO_LARGE: (NO_RETRY, "the same response will be the same size"),
    REPEATED_PAGE: (NO_RETRY, "the cursor is wrong, not the connection"),
    CURSOR_LOOP: (NO_RETRY, "the cursor is wrong, not the connection"),
    NORMALIZATION_FAILURE: (NO_RETRY, "deterministic over the same payload"),
    CANONICAL_WRITE_FAILURE: (FIXED, "a write may succeed on a second attempt"),
    IDENTITY_FAILURE: (NO_RETRY, "deterministic over the same record"),
    CHANGE_PIPELINE_FAILURE: (FIXED, "a write may succeed on a second attempt"),
    UNKNOWN_FAILURE: (FIXED, "unclassified: one cautious retry, then stop"),
}

#: Bounded, always. An unbounded retry is a retry storm with better manners.
MAX_ATTEMPTS_BY_STRATEGY: dict[str, int] = {
    NO_RETRY: 1,
    FIXED: 3,
    EXPONENTIAL: 5,
    RETRY_AFTER: 3,
}
MAX_BACKOFF_SECONDS = 3600

#: Types that mean "stop and get a person", not "try again later".
REVIEW_REQUIRED_TYPES: frozenset[str] = frozenset(
    {CONTENT_TYPE_CHANGED, SCHEMA_CHANGED}
)

#: Types that are the source declining, not the source being broken.
POLICY_TYPES: frozenset[str] = frozenset(
    {ROBOTS_RESTRICTED, AUTHORIZATION_REFUSED}
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def classify_failure(
    *,
    http_status: Any = None,
    transport_outcome: Any = None,
    exception_type: Any = None,
    stage: Any = None,
    content_type_changed: bool = False,
    schema_changed: bool = False,
    records_read: Any = None,
    expected_records: Any = None,
    bytes_received: Any = None,
    max_bytes: Any = None,
    repeated_page: bool = False,
    cursor_loop: bool = False,
    authorization_refused: bool = False,
    robots_restricted: bool = False,
) -> dict[str, Any]:
    """One failure, one type. Never parses a message to decide."""
    reasons: list[str] = []

    def result(failure_type: str) -> dict[str, Any]:
        strategy, why = RETRY_BY_TYPE[failure_type]
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "failure_type": failure_type,
                "damaged_dimension": FAILURE_DIMENSION[failure_type],
                "retry_strategy": strategy,
                "max_attempts": MAX_ATTEMPTS_BY_STRATEGY[strategy],
                "why_this_strategy": why,
                "requires_human_review": failure_type in REVIEW_REQUIRED_TYPES,
                "is_policy_refusal": failure_type in POLICY_TYPES,
                "reasons": sorted(set(reasons)),
                # Deliberately NOT the exception message: a type name is safe,
                # a message can carry a URL, a token or customer data.
                "exception_type": str(exception_type) if exception_type else None,
                "stage": str(stage) if stage else None,
            }
        )

    # Permission and policy first: they outrank anything the transport says,
    # and misreading them as transport failures produces retries.
    if authorization_refused:
        reasons.append("authorization_refused")
        return result(AUTHORIZATION_REFUSED)
    if robots_restricted:
        reasons.append("robots_restricted")
        return result(ROBOTS_RESTRICTED)

    if content_type_changed:
        reasons.append("content_type_changed")
        return result(CONTENT_TYPE_CHANGED)
    if schema_changed:
        reasons.append("schema_changed")
        return result(SCHEMA_CHANGED)
    if repeated_page:
        reasons.append("repeated_page")
        return result(REPEATED_PAGE)
    if cursor_loop:
        reasons.append("cursor_loop")
        return result(CURSOR_LOOP)

    outcome = str(transport_outcome or "").lower()
    if "dns" in outcome or "name" in outcome and "resolve" in outcome:
        reasons.append(f"transport_outcome:{outcome}")
        return result(DNS_FAILURE)
    if "connect" in outcome and "timeout" in outcome:
        reasons.append(f"transport_outcome:{outcome}")
        return result(CONNECT_TIMEOUT)
    if "timeout" in outcome or "timed_out" in outcome:
        reasons.append(f"transport_outcome:{outcome}")
        return result(READ_TIMEOUT)

    if http_status is not None:
        code = int(http_status)
        if code == 429:
            reasons.append("http_429")
            return result(RATE_LIMIT)
        if 400 <= code < 500:
            reasons.append(f"http_{code}")
            return result(HTTP_4XX)
        if code >= 500:
            reasons.append(f"http_{code}")
            return result(HTTP_5XX)

    if max_bytes and bytes_received and int(bytes_received) > int(max_bytes):
        reasons.append(f"bytes_{bytes_received}_over_{max_bytes}")
        return result(PAYLOAD_TOO_LARGE)

    stage_name = str(stage or "").lower()
    if exception_type and stage_name in ("parse", "read_records"):
        reasons.append(f"exception_in_{stage_name}")
        return result(PARSER_EXCEPTION)
    if exception_type and stage_name == "normalize":
        reasons.append("exception_in_normalize")
        return result(NORMALIZATION_FAILURE)
    if exception_type and stage_name == "identity":
        reasons.append("exception_in_identity")
        return result(IDENTITY_FAILURE)
    if exception_type and stage_name in ("canonical_write", "persist"):
        reasons.append(f"exception_in_{stage_name}")
        return result(CANONICAL_WRITE_FAILURE)
    if exception_type and stage_name in ("change", "change_pipeline"):
        reasons.append("exception_in_change_pipeline")
        return result(CHANGE_PIPELINE_FAILURE)

    if (
        records_read is not None
        and int(records_read) == 0
        and expected_records
        and int(expected_records) > 0
    ):
        reasons.append("zero_records_where_some_were_expected")
        return result(EMPTY_UNEXPECTED)

    reasons.append("no_rule_matched")
    return result(UNKNOWN_FAILURE)


def next_backoff_seconds(
    *, strategy: str, attempt: int, retry_after: Any = None, base: int = 30
) -> int | None:
    """Bounded, always. None means do not retry.

    `attempt` is 1-based. The cap is not decoration: an exponential backoff
    without one reaches days, and a source that recovers in an hour would not
    be retried until the following week.
    """
    if strategy == NO_RETRY:
        return None
    if int(attempt) >= MAX_ATTEMPTS_BY_STRATEGY.get(strategy, 1):
        return None
    if strategy == RETRY_AFTER:
        if retry_after is None:
            return min(base, MAX_BACKOFF_SECONDS)
        return min(max(int(retry_after), 0), MAX_BACKOFF_SECONDS)
    if strategy == FIXED:
        return min(base, MAX_BACKOFF_SECONDS)
    return min(base * (2 ** max(int(attempt) - 1, 0)), MAX_BACKOFF_SECONDS)


def apply_outcome(
    *,
    previous: dict[str, Any] | None,
    succeeded: bool,
    failure_type: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """The failure streak after one more outcome. History is never dropped.

    172G: a success resets the ACTIVE streak and records that a recovery
    happened. It does not erase the outage - `total_failures` and
    `first_failure_at` survive, because "this source has failed 40 times this
    month" is the fact that decides whether to keep it.
    """
    state = dict(previous or {})
    stamp = now or dt.datetime.now(dt.UTC)

    consecutive = int(state.get("consecutive_failures") or 0)
    total = int(state.get("total_failures") or 0)

    if succeeded:
        recovered = consecutive > 0
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "consecutive_failures": 0,
                "total_failures": total,
                "first_failure_at": state.get("first_failure_at"),
                "latest_failure_at": state.get("latest_failure_at"),
                "latest_failure_type": state.get("latest_failure_type"),
                "last_success_before_failure": state.get(
                    "last_success_before_failure"
                ),
                "last_success_at": stamp,
                "recovered_at": stamp if recovered else state.get("recovered_at"),
                "recovered_now": recovered,
                "failures_in_the_streak_that_just_ended": consecutive,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "consecutive_failures": consecutive + 1,
            "total_failures": total + 1,
            "first_failure_at": state.get("first_failure_at") or stamp,
            "latest_failure_at": stamp,
            "latest_failure_type": str(failure_type or UNKNOWN_FAILURE),
            "last_success_before_failure": (
                state.get("last_success_at")
                if consecutive == 0
                else state.get("last_success_before_failure")
            ),
            "last_success_at": state.get("last_success_at"),
            "recovered_at": state.get("recovered_at"),
            "recovered_now": False,
        }
    )


def taxonomy_invariant_failures(classified: dict[str, Any]) -> list[str]:
    """Refuse a classification that would produce the wrong next action."""
    failures: list[str] = []

    failure_type = str(classified.get("failure_type") or "")
    if failure_type not in FAILURE_TYPES:
        failures.append(f"failure_type_outside_vocabulary:{failure_type or 'missing'}")
        return sorted(failures)

    if classified.get("retry_strategy") not in RETRY_STRATEGIES:
        failures.append("retry_strategy_outside_vocabulary")
    if classified.get("damaged_dimension") != FAILURE_DIMENSION[failure_type]:
        failures.append("failure_mapped_to_the_wrong_dimension")

    # The one that matters: a refusal must never be retried.
    if failure_type in POLICY_TYPES and classified.get("retry_strategy") != NO_RETRY:
        failures.append("a_policy_refusal_was_given_a_retry_strategy")
    if failure_type == AUTHORIZATION_REFUSED and classified.get("retry_strategy") != (
        NO_RETRY
    ):
        failures.append("an_authorization_refusal_was_treated_as_transient")
    if int(classified.get("max_attempts") or 0) < 1:
        failures.append("max_attempts_below_one")
    if int(classified.get("max_attempts") or 0) > 5:
        failures.append("unbounded_retry")

    return sorted(set(failures))


def describe_taxonomy() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "failure_types": list(FAILURE_TYPES),
            "retry_strategies": list(RETRY_STRATEGIES),
            "failure_dimension": dict(FAILURE_DIMENSION),
            "retry_by_type": {k: list(v) for k, v in RETRY_BY_TYPE.items()},
            "max_backoff_seconds": MAX_BACKOFF_SECONDS,
            "every_type_has_a_dimension": all(
                t in FAILURE_DIMENSION for t in FAILURE_TYPES
            ),
            "every_type_has_a_retry_rule": all(
                t in RETRY_BY_TYPE for t in FAILURE_TYPES
            ),
            "no_policy_refusal_is_retried": all(
                RETRY_BY_TYPE[t][0] == NO_RETRY for t in POLICY_TYPES
            ),
            "every_retry_is_bounded": all(
                MAX_ATTEMPTS_BY_STRATEGY[s] <= 5 for s in RETRY_STRATEGIES
            ),
        }
    )
