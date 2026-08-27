"""Source circuit breaker (Gate 98C).

Computes a source's circuit status from its recent check outcomes. It decides;
it never fetches, and it never performs a check.

## Why a state machine rather than a counter

Gate 98A found **four** places that count failures and **two** thresholds that
disagree:

```text
source_crawler_governance_service   threshold 5, consulted by the network guard
source_freshness_service:242        >= 3, derives source_health_status
discovery_source_quality_service    >= 3, written independently
polite_http_fetch_service           in-memory dict, lost on restart
```

None is a breaker. A counter tells you how many times something failed; a
breaker decides whether to try again, and that needs three states and a clock.

Gate 98 does not delete the other four - that is a refactor with its own
regression surface, recorded in doc 553 as a follow-up. It defines the one state
machine a scheduler consults.

## Five states

``closed``       normal. Checks may be scheduled.
``open``         threshold reached. Nothing is scheduled until cooldown elapses.
``half_open``    cooldown elapsed. **One** probe is permitted, not a resumption.
``manual_hold``  a person stopped this source. No automation lifts it.
``unknown``      the inputs do not describe a state. Blocks.

``half_open`` matters: an open breaker whose cooldown expires does not go back
to normal, it gets one attempt. Resuming at full rate into a host that was
failing is how a temporary block becomes a permanent one, and SAM.gov names that
consequence explicitly.

## manual_hold outranks everything

A person who stopped a source did so for a reason no counter knows. Cooldown
does not lift it, a success does not lift it, and an invariant fails any result
where automation reopened it.

## Unknown blocks

Gate 92's rule, applied here: an unrecognised state or a missing failure count
is not evidence that things are fine. ``breaker_status`` defaults to ``unknown``
and ``unknown`` never permits scheduling.

## It does not fetch, and it does not probe

``half_open`` reports that a probe *would* be permitted. Performing one is the
scheduler's business, and there is no scheduler. ``probe_performed`` is False on
every result.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_crawler_governance_service import (
    CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
)

SCHEMA_VERSION = "nf_source_circuit_breaker_v1"

CIRCUIT_STATUSES = frozenset(
    {"closed", "open", "half_open", "manual_hold", "unknown"}
)

# The states that permit a scheduler to act. `half_open` permits exactly one
# probe, which is why it is listed separately from "normal".
SCHEDULING_PERMITTED_STATUSES = frozenset({"closed", "half_open"})
SINGLE_PROBE_STATUSES = frozenset({"half_open"})

MANUAL_OVERRIDE_STATUSES = frozenset({"none", "hold", "force_closed", "unknown"})
# Only an explicit `hold` stops a source by hand. `force_closed` is an operator
# saying "I have fixed it" and is honoured, but recorded.
MANUAL_HOLDING = frozenset({"hold"})

# Bridged from Gate 92 rather than redeclared, so the two cannot drift.
DEFAULT_BREAKER_THRESHOLD = CIRCUIT_BREAKER_CONSECUTIVE_FAILURES

# Long enough that a struggling host gets real relief, short enough that a
# transient blip does not cost a day of coverage.
DEFAULT_COOLDOWN_SECONDS = 3600


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _elapsed_seconds(*, later: Any, earlier: Any) -> float | None:
    """Seconds between two ISO-8601 timestamps, or None if not derivable."""
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

    a, b = _parse(later), _parse(earlier)
    if a is None or b is None:
        return None
    try:
        return (a - b).total_seconds()
    except TypeError:
        # One is naive and the other is aware. Comparing them would invent a
        # timezone, so report that the elapsed time is not derivable.
        return None


def evaluate_circuit(
    *,
    source_id: Any,
    now: Any,
    consecutive_failure_count: Any = None,
    last_success_at: Any = None,
    last_failure_at: Any = None,
    last_failure_reason: Any = None,
    breaker_threshold: Any = None,
    cooldown_seconds: Any = None,
    manual_override_status: Any = None,
) -> dict[str, Any]:
    """One source's circuit status. Nothing is fetched or probed."""
    override = _norm(
        manual_override_status, MANUAL_OVERRIDE_STATUSES, fallback="unknown"
    )
    # An absent override is "none"; only an unrecognised value is unknown.
    if manual_override_status is None:
        override = "none"

    threshold = _as_int(breaker_threshold) or DEFAULT_BREAKER_THRESHOLD
    cooldown = _as_int(cooldown_seconds)
    if cooldown is None:
        cooldown = DEFAULT_COOLDOWN_SECONDS

    failures = _as_int(consecutive_failure_count)

    blocked: list[str] = []
    cooldown_elapsed: float | None = None
    cooldown_remaining: float | None = None

    # 1. A person holding the source outranks every counter.
    if override in MANUAL_HOLDING:
        status = "manual_hold"
        blocked.append("manual_hold")
    # 1b. An override value nobody recognises is not "no override". Somebody
    #     wrote something this code does not understand, and reading that as
    #     permission is the failure this whole campaign exists to remove.
    #     An *absent* override is different: it resolves to "none" above.
    elif override == "unknown":
        status = "unknown"
        blocked.append("manual_override_status_unrecognised")
    # 2. A failure count we cannot read is not a healthy one.
    elif failures is None:
        status = "unknown"
        blocked.append("consecutive_failure_count_unknown")
    elif failures < 0:
        status = "unknown"
        blocked.append("consecutive_failure_count_negative")
    elif failures < threshold:
        status = "closed"
    else:
        # 3. Threshold reached. Open unless the cooldown has elapsed.
        cooldown_elapsed = _elapsed_seconds(later=now, earlier=last_failure_at)
        if cooldown_elapsed is None:
            # We know it failed enough times but not when. Staying open is the
            # safe reading: a cooldown we cannot measure has not elapsed.
            status = "open"
            blocked.append("cooldown_not_derivable")
        elif cooldown_elapsed >= cooldown:
            status = "half_open"
            cooldown_remaining = 0.0
        else:
            status = "open"
            cooldown_remaining = float(cooldown) - cooldown_elapsed
            blocked.append(
                f"cooldown_not_elapsed:{int(cooldown_remaining)}s_remaining"
            )

    if status == "open" and "cooldown_not_elapsed" not in " ".join(blocked):
        if "cooldown_not_derivable" not in blocked:
            blocked.append("circuit_open")

    permits = status in SCHEDULING_PERMITTED_STATUSES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "circuit_status": status,
            "permits_scheduling": permits,
            # half_open permits ONE probe, not a resumption at full rate.
            "single_probe_only": status in SINGLE_PROBE_STATUSES,
            "consecutive_failure_count": failures,
            "breaker_threshold": threshold,
            "cooldown_seconds": cooldown,
            "cooldown_elapsed_seconds": cooldown_elapsed,
            "cooldown_remaining_seconds": cooldown_remaining,
            "manual_override_status": override,
            "last_success_at": last_success_at,
            "last_failure_at": last_failure_at,
            # Reasons are recorded; the reason text itself is the caller's, and
            # a check-run contract redacts it before it is ever stored.
            "last_failure_reason": last_failure_reason,
            "blocked_reasons": sorted(set(blocked)),
            # Constants: this service decides, it does not act.
            "probe_performed": False,
            "fetch_performed": False,
            "check_executed": False,
            "fabricated": False,
        }
    )


def apply_check_outcome(
    *,
    circuit: dict[str, Any],
    succeeded: bool,
    at: Any = None,
) -> dict[str, Any]:
    """The failure count after one outcome. A success resets it to zero."""
    current = _as_int(circuit.get("consecutive_failure_count")) or 0
    if succeeded:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "source_id": circuit.get("source_id"),
                "succeeded": True,
                "consecutive_failure_count_after": 0,
                "last_success_at": at,
                "last_failure_at": circuit.get("last_failure_at"),
                "resets_failures": True,
                "fabricated": False,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": circuit.get("source_id"),
            "succeeded": False,
            "consecutive_failure_count_after": current + 1,
            "last_success_at": circuit.get("last_success_at"),
            "last_failure_at": at,
            "resets_failures": False,
            "fabricated": False,
        }
    )


def circuit_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    if "circuit_status" in result:
        for constant in ("probe_performed", "fetch_performed", "check_executed"):
            if result.get(constant) is not False:
                fails.append(f"breaker_claimed:{constant}")

        status = result.get("circuit_status")
        if status not in CIRCUIT_STATUSES:
            fails.append("circuit_status_out_of_vocabulary")

        # permits_scheduling is derived from the permitting set, never set
        # beside it.
        if result.get("permits_scheduling") != (
            status in SCHEDULING_PERMITTED_STATUSES
        ):
            fails.append("permits_scheduling_disagrees_with_status")

        # A half-open circuit permits one probe, not normal operation.
        if result.get("single_probe_only") != (status in SINGLE_PROBE_STATUSES):
            fails.append("single_probe_flag_disagrees_with_status")
        if status == "half_open" and not result.get("single_probe_only"):
            fails.append("half_open_permitted_full_rate")

        # Automation may never lift a manual hold.
        if result.get("manual_override_status") in MANUAL_HOLDING:
            if status != "manual_hold":
                fails.append("manual_hold_overridden_by_automation")
            if result.get("permits_scheduling"):
                fails.append("manual_hold_permitted_scheduling")

        # Unknown never permits.
        if status == "unknown" and result.get("permits_scheduling"):
            fails.append("unknown_circuit_permitted_scheduling")

        # A closed circuit must actually be below threshold.
        failures = result.get("consecutive_failure_count")
        threshold = result.get("breaker_threshold")
        if (
            status == "closed"
            and isinstance(failures, int)
            and isinstance(threshold, int)
            and failures >= threshold
        ):
            fails.append("circuit_closed_at_or_above_threshold")

        # An open or half-open circuit reached the threshold by definition.
        if (
            status in {"open", "half_open"}
            and isinstance(failures, int)
            and isinstance(threshold, int)
            and failures < threshold
        ):
            fails.append("circuit_tripped_below_threshold")

        # The threshold must not drift below Gate 92's floor.
        if (
            isinstance(threshold, int)
            and threshold > CIRCUIT_BREAKER_CONSECUTIVE_FAILURES
        ):
            fails.append("breaker_threshold_above_the_governance_floor")

        if not result.get("permits_scheduling") and not result.get(
            "blocked_reasons"
        ):
            fails.append("refusal_without_a_reason")

    # Outcome records.
    if "consecutive_failure_count_after" in result:
        after = result.get("consecutive_failure_count_after")
        if result.get("succeeded"):
            if after != 0:
                fails.append("success_did_not_reset_failures")
            if result.get("resets_failures") is not True:
                fails.append("success_not_marked_as_resetting")
        else:
            if not isinstance(after, int) or after < 1:
                fails.append("failure_did_not_increment")

    return fails
