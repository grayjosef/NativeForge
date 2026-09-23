"""Gate 172D/E: what a source is expected to do, as data.

Freshness is not one number. A source checked monthly is not stale after a
day, and a source checked hourly is stale after two - so "stale" is measured
against that source's own cadence, never against a fleet-wide threshold.

## Three layers, most specific wins

```text
fleet default    a floor, so an unconfigured source still has an answer
adapter default  what this KIND of source can reasonably promise
source override  what an operator decided about this one
```

All three are data. None is a source id in code: the override arrives keyed by
source, the adapter default keyed by adapter, and Gate 172AI scans this module
to prove it.

## The timestamps are not interchangeable

172D is explicit about this and it is the part most worth getting right:

```text
last_attempt_at        we tried
last_success_at        the transport worked
last_payload_at        bytes landed
last_observation_at    bytes became records
last_useful_change_at  records said something new
```

A source can be succeeding and useless - HTTP 200, valid bytes, nothing new
for six weeks. One timestamp for all five would hide exactly that.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_expectation_v1"

# ---- 172E: the contract fields -----------------------------------

SLA_FIELDS: tuple[str, ...] = (
    "collection_cadence",
    "freshness_sla_seconds",
    "max_consecutive_failures",
    "max_payload_silence_seconds",
    "expected_min_records",
    "expected_max_records",
    "max_duration_seconds",
    "max_payload_bytes",
    "retry_policy",
    "backoff_policy",
    "rate_limit_policy",
    "enabled",
    "priority",
)

HOURLY = "hourly"
DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"
EVENT_DRIVEN = "event_driven"
MANUAL = "manual"

CADENCES: tuple[str, ...] = (HOURLY, DAILY, WEEKLY, MONTHLY, EVENT_DRIVEN, MANUAL)

CADENCE_SECONDS: dict[str, int | None] = {
    HOURLY: 3600,
    DAILY: 86400,
    WEEKLY: 604800,
    MONTHLY: 2592000,
    # Neither has a schedule, so neither can be "late". Reporting them as
    # fresh would be as wrong as reporting them stale.
    EVENT_DRIVEN: None,
    MANUAL: None,
}

#: Cadences where "overdue" is not a meaningful question.
UNSCHEDULED: frozenset[str] = frozenset({EVENT_DRIVEN, MANUAL})

PRIORITIES: tuple[str, ...] = ("critical", "high", "normal", "low")

#: The fleet floor. Deliberately generous: a default that marks unconfigured
#: sources stale would fill an operator's screen with noise about sources
#: nobody promised anything about.
FLEET_DEFAULT: dict[str, Any] = {
    "collection_cadence": DAILY,
    "freshness_sla_seconds": 172800,
    "max_consecutive_failures": 3,
    "max_payload_silence_seconds": 604800,
    "expected_min_records": 0,
    "expected_max_records": None,
    "max_duration_seconds": 300,
    "max_payload_bytes": 10 * 1024 * 1024,
    "retry_policy": "EXPONENTIAL",
    "backoff_policy": "capped",
    "rate_limit_policy": "honor_retry_after",
    "enabled": True,
    "priority": "normal",
}

#: Per-ADAPTER defaults. Keyed by adapter_key, which is how Gate 166's
#: attribution table and Gate 171's adapters are already keyed, so adding a
#: source family is a row here rather than a branch anywhere.
ADAPTER_DEFAULTS: dict[str, dict[str, Any]] = {
    "grants_gov_search2": {
        "collection_cadence": DAILY,
        "expected_min_records": 1,
        "priority": "high",
    },
    "federal_register_documents_json": {
        "collection_cadence": DAILY,
        "expected_min_records": 1,
        "max_payload_bytes": 5 * 1024 * 1024,
        "priority": "high",
    },
    "bia_program_page_html": {
        # A program page changes rarely, and polling it daily would be
        # pressure on a publisher for no intelligence.
        "collection_cadence": WEEKLY,
        "freshness_sla_seconds": 1209600,
        "expected_min_records": 1,
        "expected_max_records": 1,
        "max_payload_bytes": 2 * 1024 * 1024,
        "priority": "normal",
    },
}


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def resolve_expectation(
    *,
    adapter_key: Any = None,
    source_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fleet default, then adapter default, then the operator's override."""
    resolved = dict(FLEET_DEFAULT)
    layers = ["fleet_default"]

    adapter = ADAPTER_DEFAULTS.get(str(adapter_key or ""))
    if adapter:
        resolved.update(adapter)
        layers.append(f"adapter_default:{adapter_key}")

    override = {
        key: value
        for key, value in (source_override or {}).items()
        if key in SLA_FIELDS and value is not None
    }
    if override:
        resolved.update(override)
        layers.append("source_override")

    cadence = str(resolved.get("collection_cadence") or DAILY)
    if cadence not in CADENCES:
        cadence = DAILY
        resolved["collection_cadence"] = cadence

    # A cadence with no schedule cannot carry a freshness SLA, and pretending
    # otherwise would make every manual source permanently overdue.
    if cadence in UNSCHEDULED:
        resolved["freshness_sla_seconds"] = None

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **resolved,
            "cadence_seconds": CADENCE_SECONDS.get(cadence),
            "is_scheduled": cadence not in UNSCHEDULED,
            "resolved_from": layers,
            "adapter_key": str(adapter_key) if adapter_key else None,
        }
    )


def _as_datetime(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)
    return None


def evaluate_freshness(
    *,
    expectation: dict[str, Any],
    last_attempt_at: Any = None,
    last_success_at: Any = None,
    last_payload_at: Any = None,
    last_observation_at: Any = None,
    last_useful_change_at: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Five ages, one verdict, measured against THIS source's cadence."""
    stamp = _as_datetime(now) or dt.datetime.now(dt.UTC)

    stamps = {
        "last_attempt_at": _as_datetime(last_attempt_at),
        "last_success_at": _as_datetime(last_success_at),
        "last_payload_at": _as_datetime(last_payload_at),
        "last_observation_at": _as_datetime(last_observation_at),
        "last_useful_change_at": _as_datetime(last_useful_change_at),
    }
    ages = {
        name.replace("last_", "").replace("_at", "") + "_age_seconds": (
            round((stamp - value).total_seconds(), 1) if value else None
        )
        for name, value in stamps.items()
    }

    cadence_seconds = expectation.get("cadence_seconds")
    sla = expectation.get("freshness_sla_seconds")
    scheduled = bool(expectation.get("is_scheduled"))

    expected_next = None
    deadline = None
    overdue_by = None
    if scheduled and stamps["last_success_at"] and cadence_seconds:
        expected_next = stamps["last_success_at"] + dt.timedelta(
            seconds=int(cadence_seconds)
        )
        if sla:
            deadline = stamps["last_success_at"] + dt.timedelta(seconds=int(sla))
            overdue_by = round((stamp - deadline).total_seconds(), 1)

    # Never collected is NOT stale - it is unmeasured. A source that has
    # never run has no freshness to have lost.
    never_collected = stamps["last_success_at"] is None
    stale = bool(
        scheduled and sla and not never_collected and deadline and stamp > deadline
    )

    # Succeeding but useless. 172M's separation, measured here because this is
    # where the timestamps live.
    silence = expectation.get("max_payload_silence_seconds")
    useful_silence = None
    if stamps["last_useful_change_at"] and silence:
        useful_silence = (
            stamp - stamps["last_useful_change_at"]
        ).total_seconds() > int(silence)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **{name: value for name, value in stamps.items()},
            **ages,
            "expected_next_run_at": expected_next,
            "freshness_deadline_at": deadline,
            "overdue_by_seconds": overdue_by,
            "is_scheduled": scheduled,
            "never_collected": never_collected,
            "is_stale": stale,
            "useful_intelligence_silent": useful_silence,
            "cadence": expectation.get("collection_cadence"),
            "freshness_sla_seconds": sla,
        }
    )


def expectation_invariant_failures(expectation: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in SLA_FIELDS:
        if field not in expectation:
            failures.append(f"expectation_missing_field:{field}")

    cadence = str(expectation.get("collection_cadence") or "")
    if cadence not in CADENCES:
        failures.append(f"cadence_outside_vocabulary:{cadence or 'missing'}")
    if str(expectation.get("priority") or "") not in PRIORITIES:
        failures.append("priority_outside_vocabulary")

    if cadence in UNSCHEDULED and expectation.get("freshness_sla_seconds"):
        failures.append("an_unscheduled_cadence_cannot_carry_a_freshness_sla")
    if cadence not in UNSCHEDULED and not expectation.get("freshness_sla_seconds"):
        failures.append("a_scheduled_cadence_without_a_freshness_sla")
    if int(expectation.get("max_consecutive_failures") or 0) < 1:
        failures.append("max_consecutive_failures_below_one")

    minimum = expectation.get("expected_min_records")
    maximum = expectation.get("expected_max_records")
    if minimum is not None and maximum is not None and int(minimum) > int(maximum):
        failures.append("expected_min_records_above_expected_max_records")

    return sorted(set(failures))


def freshness_invariant_failures(freshness: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if freshness.get("never_collected") and freshness.get("is_stale"):
        failures.append("a_source_that_never_collected_reported_as_stale")
    if not freshness.get("is_scheduled") and freshness.get("is_stale"):
        failures.append("an_unscheduled_source_reported_as_stale")
    if freshness.get("is_stale") and freshness.get("overdue_by_seconds") is None:
        failures.append("stale_without_saying_by_how_much")
    return sorted(set(failures))


def describe_expectations() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "sla_fields": list(SLA_FIELDS),
            "cadences": list(CADENCES),
            "cadence_seconds": dict(CADENCE_SECONDS),
            "unscheduled_cadences": sorted(UNSCHEDULED),
            "priorities": list(PRIORITIES),
            "fleet_default": dict(FLEET_DEFAULT),
            "adapters_with_defaults": sorted(ADAPTER_DEFAULTS),
            "layers": ["fleet_default", "adapter_default", "source_override"],
            "every_cadence_has_a_duration_or_is_unscheduled": all(
                CADENCE_SECONDS.get(c) is not None or c in UNSCHEDULED
                for c in CADENCES
            ),
        }
    )
