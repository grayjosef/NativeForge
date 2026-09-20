"""Evaluate the whole fleet in one pass (Gate 166F).

One sweep = one fleet-fact context + N per-source evaluations.

```text
fleet facts     computed ONCE      scheduler readiness, execution health,
                                   runtime readiness
governance      TWO queries        every decision row, every activation row
per source      O(1) each          catalog row + its governance + classify
```

Gate 165 measured the shape this replaces: ~332 ms per source, of which ~70%
was fleet-wide work with no `source_id` parameter, recomputed for every source.
A 1,000-source sweep asked whether the scheduler was ready a thousand times.

## What it counts, and what it refuses to count

The buckets are the authority states, not a pass/fail. `registered` is the
floor - the 177 baseline sources sit there and that is the correct answer for
them, not a failure. A sweep that reported "177 blocked" would be describing
sources nobody ever asked to activate.

## No lifetime invariant on the numbers

This deliberately does NOT assert that exactly one source is authorized.
Gate 163's world had one; Gate 166 exists so the next one is a data change.
The count is REPORTED. `sweep_invariant_failures` checks structural properties
- every source landed in exactly one bucket, the buckets total the population,
fleet facts were computed once - which stay true at 1 source and at 5,000.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_authority_sweep_v1"

#: Every bucket a source can land in. Exhaustive and disjoint: a source counted
#: in two buckets, or in none, is a sweep that does not add up.
SWEEP_BUCKETS: tuple[str, ...] = (
    "authorized_for_live",
    "live_opted_in",
    "activated",
    "reviewed",
    "registered",
    "review_required",
    "blocked",
    "retired",
    "unregistered",
    "unknown",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def sweep_source_authority(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_ids: Any = None,
    registry_rows: dict[str, Any] | None = None,
    now: Any = None,
    include_detail: bool = False,
) -> dict[str, Any]:
    """Every registered source's authority, in one fleet-fact scope.

    `source_ids` and `registry_rows` let a scale harness supply a synthetic
    catalog. Neither can assert an authority: the governance rows still come
    from the database and the classification is the same pure function, so a
    fabricated catalog produces `registered` sources and nothing more.
    """
    from nativeforge.services.source_authority_service import (
        classify_source_authority,
        load_governance_state,
    )
    from nativeforge.services.source_fleet_fact_scope_service import (
        describe_scope,
        fleet_fact_scope,
    )

    catalog: dict[str, Any]
    if registry_rows is not None:
        catalog = dict(registry_rows)
    else:
        try:
            from nativeforge.services.source_authorization_fixture_registry_service import (  # noqa: E501
                merge_fixture_rows,
            )
            from nativeforge.services.source_monitoring_approved_source_service import (
                load_registry_rows,
            )

            catalog = merge_fixture_rows(load_registry_rows())
        except Exception:  # noqa: BLE001 - an unreadable catalog registers nothing
            catalog = {}

    if source_ids is not None:
        keys = [str(key) for key in source_ids]
    else:
        keys = sorted(catalog)

    counts = dict.fromkeys(SWEEP_BUCKETS, 0)
    detail: dict[str, Any] = {}
    errors: list[str] = []

    with fleet_fact_scope(
        organization_id=organization_id, reason="source_authority_sweep"
    ) as scope:
        # TWO queries for the whole fleet, not two per source.
        governance = load_governance_state(
            connection=connection, organization_id=organization_id, now=now
        )

        # The fleet facts are resolved once, here, rather than incidentally by
        # whichever source happened to be evaluated first. A sweep whose fleet
        # cost depends on evaluation order is a sweep nobody can reason about.
        try:
            from nativeforge.services.source_fleet_fact_scope_service import (
                scoped_execution_health,
                scoped_runtime_readiness_facts,
            )

            scoped_runtime_readiness_facts(
                connection=connection, organization_id=organization_id
            )
            scoped_execution_health(
                connection=connection, organization_id=organization_id
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fleet_facts:{type(exc).__name__}")

        for key in keys:
            try:
                verdict = classify_source_authority(
                    source_id=key,
                    registered=key in catalog,
                    governance=governance.get(key),
                )
                state = str(verdict.get("state") or "unknown")
                if state not in counts:
                    state = "unknown"
                counts[state] += 1
                if include_detail:
                    detail[key] = verdict
            except Exception as exc:  # noqa: BLE001
                counts["unknown"] += 1
                errors.append(f"{key}:{type(exc).__name__}")

        fleet = describe_scope(scope)

    evaluated = sum(counts.values())
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "registered_sources": len(catalog),
        "evaluated_sources": evaluated,
        "counts_by_state": counts,
        # The names Gate 166F asked for, composed from the buckets rather than
        # counted a second time - two tallies of one population can disagree.
        "authorized_for_live": counts["live_opted_in"] + counts["authorized_for_live"],
        "blocked": counts["blocked"],
        "review_required": counts["review_required"],
        "retired": counts["retired"],
        "unknown_or_error": counts["unknown"],
        "not_yet_authorized": (
            counts["registered"] + counts["reviewed"] + counts["activated"]
        ),
        "fleet_facts": fleet,
        "errors": sorted(set(errors)),
        "authority_is_data_derived": True,
        "exactly_one_source_is_not_an_invariant": (
            "the authorized count is REPORTED. Gate 163's world had one "
            "authorized source; Gate 166 exists so the next one is a data "
            "change, and a lifetime assertion of 1 would have to be edited to "
            "permit the thing this gate was built to allow."
        ),
    }
    if include_detail:
        report["detail"] = detail
    return _json_safe(report)


def sweep_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Structural checks that hold at 1 source and at 5,000.

    Nothing here asserts a population size or an authorized count. What it
    refuses is a sweep that does not add up, or one whose fleet facts were
    recomputed per source - the property Gate 166E exists to provide.
    """
    fails: list[str] = []

    counts = report.get("counts_by_state") or {}
    unexpected = sorted(set(counts) - set(SWEEP_BUCKETS))
    if unexpected:
        fails.append(f"state_outside_the_buckets:{unexpected}")

    # `or -1` would read a legitimate ZERO as missing. A sweep with nothing
    # authorized is the normal case for a fleet of registered-only sources,
    # and the first run of this check failed all four synthetic scales for
    # that reason alone. Absent and zero are different facts.
    def _reported(name: str) -> int:
        value = report.get(name)
        return int(value) if isinstance(value, int) else -1

    total = sum(int(counts.get(name) or 0) for name in SWEEP_BUCKETS)
    if total != _reported("evaluated_sources"):
        fails.append(
            f"buckets_do_not_total_the_population:{total}"
            f"!={report.get('evaluated_sources')}"
        )

    composed = int(counts.get("live_opted_in") or 0) + int(
        counts.get("authorized_for_live") or 0
    )
    if composed != _reported("authorized_for_live"):
        fails.append(
            f"authorized_count_disagrees_with_its_own_buckets:{composed}"
            f"!={report.get('authorized_for_live')}"
        )

    # O(1) fleet facts. The whole point of the sweep.
    fleet = report.get("fleet_facts") or {}
    computations = fleet.get("computations") or {}
    for name, count in computations.items():
        if int(count or 0) > 1:
            fails.append(f"fleet_fact_recomputed_during_the_sweep:{name}:{count}")

    if not report.get("authority_is_data_derived"):
        fails.append("sweep_did_not_derive_authority_from_data")

    return sorted(set(fails))
