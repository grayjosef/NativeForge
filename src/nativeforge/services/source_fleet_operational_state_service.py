"""Gate 172B/C: what state a source is in, and along which dimension.

A fleet of three can be described by `healthy: true`. A fleet of five thousand
cannot, because the question an operator actually has is never "is it healthy"
- it is "which of the things that can be wrong with it is wrong, and does that
stop collection".

So this module holds two vocabularies and one derivation:

```text
DIMENSIONS   eleven independent answers, each measured from its own owner
STATE        one operational state, DERIVED from the dimensions
```

## A degraded dimension must not erase the healthy ones

The BIA source is the worked example this gate inherited: its transport is
healthy, its parser is healthy, its freshness is measurable, and its EVIDENCE
is degraded because a robots response body was lost. Collapsing that to
`healthy=false` throws away three true facts to record one, and an operator
who sees it cannot tell a dead source from a live one with a documented gap.

## UNKNOWN is not healthy

`UNKNOWN` means the inputs to classify were absent. A fleet layer that treats
absent evidence as good news is the specific failure this campaign keeps
finding, so `UNKNOWN` is its own state and never satisfies readiness.

## No source is named here

Every input arrives as data - facts resolved by the layers that own them. Gate
172AI scans this module for source names; the BIA evidence gap reaches it as a
`known_gaps` entry, not as a branch.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_operational_state_v1"

# ---- 172B: the operational states --------------------------------

HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
STALE = "STALE"
FAILING = "FAILING"
RATE_LIMITED = "RATE_LIMITED"
BLOCKED = "BLOCKED"
AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
DISABLED = "DISABLED"
RETIRED = "RETIRED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
UNKNOWN = "UNKNOWN"

OPERATIONAL_STATES: tuple[str, ...] = (
    HEALTHY,
    DEGRADED,
    STALE,
    FAILING,
    RATE_LIMITED,
    BLOCKED,
    AUTHORIZATION_REQUIRED,
    DISABLED,
    RETIRED,
    REVIEW_REQUIRED,
    UNKNOWN,
)

#: What each state MEANS, in one sentence, so two of them cannot quietly
#: become synonyms. 172B is explicit that these must not be aliases.
STATE_MEANINGS: dict[str, str] = {
    HEALTHY: "collecting within its expected freshness, no named gaps",
    DEGRADED: "collecting, but with known gaps or partial evidence",
    STALE: "its freshness SLA has been exceeded",
    FAILING: "attempts are being made and repeatedly failing",
    RATE_LIMITED: "the source is asking us to slow down",
    BLOCKED: "access policy or transport prevents collection",
    AUTHORIZATION_REQUIRED: (
        "collection is possible but permission is absent or expired"
    ),
    DISABLED: "an operator deliberately turned it off",
    RETIRED: "permanently withdrawn from the fleet",
    REVIEW_REQUIRED: "drift or terms need a human before it runs again",
    UNKNOWN: "there is not enough evidence to classify it",
}

#: States that mean "this source is not going to collect until something
#: changes". Separated from unhealthiness: a DISABLED source is not broken.
NOT_COLLECTING: frozenset[str] = frozenset(
    {DISABLED, RETIRED, BLOCKED, AUTHORIZATION_REQUIRED, REVIEW_REQUIRED}
)

#: The only state that means "nothing to report". DEGRADED is not a warning
#: shade of healthy - it is a source with a named gap.
FULLY_OPERATIONAL: frozenset[str] = frozenset({HEALTHY})

# ---- 172C: the independent dimensions ----------------------------

AUTHORIZATION_HEALTH = "authorization_health"
TRANSPORT_HEALTH = "transport_health"
SOURCE_AVAILABILITY_HEALTH = "source_availability_health"
PARSER_HEALTH = "parser_health"
SCHEMA_HEALTH = "schema_health"
FRESHNESS_HEALTH = "freshness_health"
VOLUME_HEALTH = "volume_health"
EVIDENCE_HEALTH = "evidence_health"
BACKLOG_HEALTH = "backlog_health"
SCHEDULER_HEALTH = "scheduler_health"
WORKER_HEALTH = "worker_health"

HEALTH_DIMENSIONS: tuple[str, ...] = (
    AUTHORIZATION_HEALTH,
    TRANSPORT_HEALTH,
    SOURCE_AVAILABILITY_HEALTH,
    PARSER_HEALTH,
    SCHEMA_HEALTH,
    FRESHNESS_HEALTH,
    VOLUME_HEALTH,
    EVIDENCE_HEALTH,
    BACKLOG_HEALTH,
    SCHEDULER_HEALTH,
    WORKER_HEALTH,
)

OK = "ok"
DEGRADED_DIM = "degraded"
FAILED_DIM = "failed"
UNKNOWN_DIM = "unknown"
NOT_APPLICABLE = "not_applicable"

DIMENSION_VALUES: tuple[str, ...] = (
    OK,
    DEGRADED_DIM,
    FAILED_DIM,
    UNKNOWN_DIM,
    NOT_APPLICABLE,
)

#: Which layer owns each dimension's evidence. A dimension measured from
#: somewhere other than its owner is a second source of truth.
DIMENSION_OWNERS: dict[str, str] = {
    AUTHORIZATION_HEALTH: "source_authorization_fact_resolver_service",
    TRANSPORT_HEALTH: "nf_source_collection_execution_attempts",
    SOURCE_AVAILABILITY_HEALTH: "nf_source_collection_execution_attempts.http_status",
    PARSER_HEALTH: "adapter read_records outcomes",
    SCHEMA_HEALTH: "source_fleet_drift_service",
    FRESHNESS_HEALTH: "source_freshness_service",
    VOLUME_HEALTH: "source_fleet_drift_service",
    EVIDENCE_HEALTH: "nf_source_collection_raw_payloads + robots evidence",
    BACKLOG_HEALTH: "nf_source_collection_jobs",
    SCHEDULER_HEALTH: "source_collection_scheduler_health_service",
    WORKER_HEALTH: "source_collection_worker_health_service",
}

#: Dimensions that, when FAILED, stop collection outright rather than merely
#: degrading it. Ordered: the first match decides the state, so the order IS
#: the precedence and is written down rather than emerging from an if-chain.
BLOCKING_PRECEDENCE: tuple[tuple[str, str], ...] = (
    (AUTHORIZATION_HEALTH, AUTHORIZATION_REQUIRED),
    (TRANSPORT_HEALTH, BLOCKED),
    (SOURCE_AVAILABILITY_HEALTH, FAILING),
    (SCHEMA_HEALTH, REVIEW_REQUIRED),
    (PARSER_HEALTH, FAILING),
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def blank_dimensions() -> dict[str, str]:
    """Every dimension UNKNOWN until something measures it.

    The default matters: a dimension nobody measured must not default to OK,
    because that is how an unmeasured fleet reports itself healthy.
    """
    return dict.fromkeys(HEALTH_DIMENSIONS, UNKNOWN_DIM)


def derive_operational_state(
    *,
    dimensions: dict[str, str],
    disabled: bool = False,
    retired: bool = False,
    rate_limited: bool = False,
    review_required: bool = False,
    stale: bool = False,
    consecutive_failures: int = 0,
    failure_threshold: int = 3,
    known_gaps: list[str] | None = None,
) -> dict[str, Any]:
    """One state, derived from the dimensions and the operator's own switches.

    Deliberately ordered and deliberately explicit. The precedence answers a
    real question - if a source is both disabled and stale, what does an
    operator need to see? - and the answer is written here once instead of
    being implied by the order somebody happened to write the branches in.
    """
    gaps = sorted(known_gaps or [])
    values = dict(dimensions or {})
    reasons: list[str] = []

    # Operator intent outranks measurement. A disabled source is not failing;
    # nobody is trying.
    if retired:
        return _state(RETIRED, ["source_is_retired"], values, gaps)
    if disabled:
        return _state(DISABLED, ["operator_disabled_this_source"], values, gaps)

    # A source that asked us to slow down is not broken, and treating it as
    # failing is how a fleet earns a block.
    if rate_limited:
        return _state(RATE_LIMITED, ["source_reported_rate_limiting"], values, gaps)

    if review_required:
        return _state(REVIEW_REQUIRED, ["human_review_requested"], values, gaps)

    for dimension, state in BLOCKING_PRECEDENCE:
        if values.get(dimension) == FAILED_DIM:
            reasons.append(f"{dimension}_failed")
            return _state(state, reasons, values, gaps)

    if int(consecutive_failures) >= int(failure_threshold):
        return _state(
            FAILING,
            [f"consecutive_failures_{consecutive_failures}"],
            values,
            gaps,
        )

    if stale:
        return _state(STALE, ["freshness_sla_exceeded"], values, gaps)

    # A degraded dimension, or a named gap, is DEGRADED - not a quieter
    # HEALTHY. This is the line the BIA evidence gap sits on.
    degraded = sorted(d for d, v in values.items() if v == DEGRADED_DIM)
    if degraded or gaps:
        return _state(
            DEGRADED,
            [f"{d}_degraded" for d in degraded] or ["named_gaps_present"],
            values,
            gaps,
        )

    # Unmeasured is not healthy.
    unknown = sorted(d for d, v in values.items() if v == UNKNOWN_DIM)
    if unknown:
        return _state(
            UNKNOWN, [f"{d}_not_measured" for d in unknown], values, gaps
        )

    return _state(HEALTHY, [], values, gaps)


def _state(
    state: str, reasons: list[str], dimensions: dict[str, str], gaps: list[str]
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operational_state": state,
            "meaning": STATE_MEANINGS.get(state),
            "reasons": sorted(set(reasons)),
            "dimensions": dict(sorted(dimensions.items())),
            "known_gaps": sorted(set(gaps)),
            "is_collecting": state not in NOT_COLLECTING,
            "is_fully_operational": state in FULLY_OPERATIONAL,
            "degraded_dimensions": sorted(
                d for d, v in dimensions.items() if v == DEGRADED_DIM
            ),
            "failed_dimensions": sorted(
                d for d, v in dimensions.items() if v == FAILED_DIM
            ),
            "unmeasured_dimensions": sorted(
                d for d, v in dimensions.items() if v == UNKNOWN_DIM
            ),
        }
    )


def state_invariant_failures(state: dict[str, Any]) -> list[str]:
    """Refuse a classification that claims more than its evidence supports."""
    failures: list[str] = []

    name = str(state.get("operational_state") or "")
    if name not in OPERATIONAL_STATES:
        failures.append(f"state_outside_the_vocabulary:{name or 'missing'}")

    dimensions = dict(state.get("dimensions") or {})
    for dimension in HEALTH_DIMENSIONS:
        if dimension not in dimensions:
            failures.append(f"dimension_not_reported:{dimension}")
    for dimension, value in dimensions.items():
        if value not in DIMENSION_VALUES:
            failures.append(f"dimension_value_outside_vocabulary:{dimension}={value}")

    # The three claims that matter most, each checkable.
    if name == HEALTHY and state.get("known_gaps"):
        failures.append("healthy_while_naming_gaps")
    if name == HEALTHY and state.get("degraded_dimensions"):
        failures.append("healthy_with_a_degraded_dimension")
    if name == HEALTHY and state.get("unmeasured_dimensions"):
        failures.append("healthy_with_an_unmeasured_dimension")
    if name == UNKNOWN and state.get("is_fully_operational"):
        failures.append("unknown_reported_as_fully_operational")
    if name != HEALTHY and state.get("is_fully_operational"):
        failures.append("non_healthy_state_claiming_full_operation")
    if name in NOT_COLLECTING and state.get("is_collecting"):
        failures.append(f"state_{name}_claiming_it_is_collecting")

    return sorted(set(failures))


def describe_state_model() -> dict[str, Any]:
    """The vocabularies, for anyone who needs them without importing them."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operational_states": list(OPERATIONAL_STATES),
            "state_meanings": dict(STATE_MEANINGS),
            "health_dimensions": list(HEALTH_DIMENSIONS),
            "dimension_values": list(DIMENSION_VALUES),
            "dimension_owners": dict(DIMENSION_OWNERS),
            "blocking_precedence": [list(p) for p in BLOCKING_PRECEDENCE],
            "states_are_distinct": len(set(OPERATIONAL_STATES))
            == len(OPERATIONAL_STATES),
            "every_state_has_a_meaning": all(
                s in STATE_MEANINGS for s in OPERATIONAL_STATES
            ),
            "every_dimension_has_an_owner": all(
                d in DIMENSION_OWNERS for d in HEALTH_DIMENSIONS
            ),
            "unknown_is_not_healthy": UNKNOWN not in FULLY_OPERATIONAL,
        }
    )
