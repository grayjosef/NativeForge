"""Fleet-wide facts, computed once per sweep (Gate 166E).

Gate 165 measured one source authorization at ~332 ms and attributed the cost:

```text
resolve_source_authorization_facts        160 ms
  _resolve_runtime -> runtime readiness   102 ms   <- takes no source_id
    build_scheduler_readiness              51 ms   <- takes no source_id
    build_execution_health (x2)            99 ms   <- takes no source_id
  _resolve_collector -> capability          49 ms   <- takes source_id
```

**About 70% of the cost is fleet-wide work invoked per source.** A 1,000-source
sweep asks "is the scheduler ready?" a thousand times and gets the same answer
a thousand times.

## Why this is not a cache

A cache answers from the past. This answers from ONE computation whose lifetime
a caller opened and will close:

* **Explicit lifetime.** Nothing is reused outside `fleet_fact_scope()`. With no
  scope open, every call computes - byte-for-byte the pre-Gate-166 behaviour.
* **Immutable for the sweep.** The first computation inside a scope is the one
  every later call in that scope receives. Nothing invalidates mid-sweep,
  because a sweep that saw two different answers to one fleet question produced
  a report that is true of no moment in time.
* **Naturally invalidated.** Leaving the scope discards it. The next sweep
  computes again. There is no TTL to tune and no staleness to reason about.
* **Not ambient.** A `ContextVar`, not a module global. Gate 164 established the
  primitive: all 57 API route modules are sync, so Starlette runs them in
  anyio's worker threadpool with REUSED workers - `threading.local()` would
  leak one request's scope into the next request that happened to land on the
  same worker. A `ContextVar` is per-task and per-thread.

## The binding that stops a wrong answer

A memoized value keyed only by function name would hand a sweep over
organization A the fleet facts computed for organization B. So the scope
records the `(organization_id, connection)` it was opened for, and a call that
does not match **bypasses the scope entirely and computes fresh**.

That is the conservative direction: a mismatch costs time, never correctness.
The bypass is counted and reported, so "the scope was silently useless" is
visible rather than inferred from a timing number.

## What is deliberately NOT hoisted

`measure_collector_capability` takes a `source_id` and is per-source work. It
stays per-source. Hoisting a source-specific fact would make every source in a
sweep report the first source's capability - the exact class of defect this
campaign keeps finding, where a green check has two possible causes.

## It asserts nothing

Nothing here can supply a fact. There is no parameter that accepts a status,
and the only way a value enters the scope is by being computed by the same
function that would have computed it anyway. Gate 162 pinned the resolver's
signature precisely so a fact could not be passed in, and this module leaves
that signature untouched: the hoist sits BELOW the resolver, not beside it.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_fact_scope_v1"

#: The fleet questions. Each is a call that takes no `source_id` and whose
#: answer is therefore the same for every source in one sweep.
FLEET_FACTS: tuple[str, ...] = (
    "runtime_readiness_facts",
    "execution_health",
    "scheduler_readiness",
)

#: Facts that another fleet fact already computes on its way to its own answer.
#: `build_runtime_readiness_facts` calls `build_scheduler_readiness` internally,
#: so scoping the outer call bounds the inner one too.
#:
#: This is recorded rather than left implicit because a sweep report showing
#: `scheduler_readiness: 0` otherwise looks like a fact that got missed. It was
#: computed - once - by its parent. Routing it through the scope SEPARATELY
#: would compute it a second time and make the report worse, not better.
COVERED_TRANSITIVELY: dict[str, str] = {
    "scheduler_readiness": "runtime_readiness_facts",
}


class _Scope:
    """One sweep's fleet facts. Built empty; each fact computed at most once."""

    __slots__ = ("bypasses", "computations", "organization_id", "reason", "values")

    def __init__(self, *, organization_id: Any, reason: str) -> None:
        self.organization_id = organization_id
        self.reason = reason
        self.values: dict[tuple[str, Any], Any] = {}
        self.computations: dict[str, int] = dict.fromkeys(FLEET_FACTS, 0)
        self.bypasses: dict[str, int] = dict.fromkeys(FLEET_FACTS, 0)


_SCOPE: contextvars.ContextVar[_Scope | None] = contextvars.ContextVar(
    "nf_source_fleet_fact_scope", default=None
)


def _org_key(organization_id: Any) -> str:
    return str(organization_id) if organization_id is not None else ""


@contextlib.contextmanager
def fleet_fact_scope(*, organization_id: Any = None, reason: str = ""):
    """Open one sweep. Fleet facts inside are computed once and reused.

    Nested scopes are not merged: the inner scope is its own sweep and the
    outer one is restored on exit. A sweep is a unit of measurement, and
    silently joining two of them would report facts from one moment under the
    name of another.
    """
    scope = _Scope(organization_id=organization_id, reason=str(reason or ""))
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        _SCOPE.reset(token)


def in_fleet_scope() -> bool:
    return _SCOPE.get() is not None


def _scoped(
    name: str,
    compute,
    *,
    connection: Any,
    organization_id: Any,
):
    """Return `compute()`, once per (scope, fact, connection).

    Outside a scope, or when the scope was opened for a different
    organization, this is exactly `compute()` - no storage, no reuse.
    """
    scope = _SCOPE.get()
    if scope is None:
        return compute()

    if _org_key(scope.organization_id) != _org_key(organization_id):
        # Not this sweep's organization. Compute fresh rather than answer from
        # another tenant's fleet, and record that the scope did not apply.
        scope.bypasses[name] = scope.bypasses.get(name, 0) + 1
        return compute()

    # The connection is part of the key: two connections can see different
    # data, and a fleet fact read through one is not evidence about the other.
    key = (name, id(connection))
    if key in scope.values:
        return scope.values[key]

    value = compute()
    scope.values[key] = value
    scope.computations[name] = scope.computations.get(name, 0) + 1
    return value


def scoped_runtime_readiness_facts(
    *, connection: Any = None, organization_id: Any = None, exercise: bool = False
) -> dict[str, Any]:
    """`build_runtime_readiness_facts`, computed once per sweep.

    `exercise=True` is never scoped. Exercising WRITES and deletes fixture
    rows; reusing one exercise's result for a later call would report that
    lanes were exercised when they were not. A measurement with a side effect
    is not a value to hand around.
    """
    from nativeforge.services.source_runtime_readiness_fact_service import (
        build_runtime_readiness_facts,
    )

    def compute() -> dict[str, Any]:
        return build_runtime_readiness_facts(
            connection=connection,
            organization_id=organization_id,
            exercise=exercise,
        )

    if exercise:
        scope = _SCOPE.get()
        if scope is not None:
            scope.bypasses["runtime_readiness_facts"] = (
                scope.bypasses.get("runtime_readiness_facts", 0) + 1
            )
        return compute()

    return _scoped(
        "runtime_readiness_facts",
        compute,
        connection=connection,
        organization_id=organization_id,
    )


def scoped_execution_health(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """`build_execution_health`, computed once per sweep."""
    from nativeforge.services.source_collector_execution_health_service import (
        build_execution_health,
    )

    return _scoped(
        "execution_health",
        lambda: build_execution_health(
            connection=connection, organization_id=organization_id
        ),
        connection=connection,
        organization_id=organization_id,
    )


def scoped_scheduler_readiness(
    *, connection: Any = None, organization_id: Any = None, repo_root: Any = None
) -> dict[str, Any]:
    """`build_scheduler_readiness`, computed once per sweep.

    It takes neither a connection nor an organization - it detects repository
    state - but it is keyed the same way so one rule covers every fleet fact.
    """
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    return _scoped(
        "scheduler_readiness",
        lambda: build_scheduler_readiness(repo_root=repo_root),
        connection=connection,
        organization_id=organization_id,
    )


def describe_scope(scope: Any = None) -> dict[str, Any]:
    """What one sweep computed. Counts only; no fleet values are copied out."""
    resolved = scope if isinstance(scope, _Scope) else _SCOPE.get()
    if resolved is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "scope_open": False,
            "fleet_facts": list(FLEET_FACTS),
            "computations": dict.fromkeys(FLEET_FACTS, 0),
            "bypasses": dict.fromkeys(FLEET_FACTS, 0),
            "total_computations": 0,
        }

    computations = {
        name: int(resolved.computations.get(name, 0)) for name in FLEET_FACTS
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "scope_open": True,
        "reason": resolved.reason or None,
        "organization_id": _org_key(resolved.organization_id) or None,
        "fleet_facts": list(FLEET_FACTS),
        "computations": computations,
        # A zero here means "not requested through the scope", which for a
        # transitively covered fact means its parent computed it once - not
        # that it was missed.
        "covered_transitively": dict(COVERED_TRANSITIVELY),
        "bypasses": {name: int(resolved.bypasses.get(name, 0)) for name in FLEET_FACTS},
        "total_computations": sum(computations.values()),
        "distinct_values_held": len(resolved.values),
    }


def scope_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Refuse a sweep that recomputed a fleet fact, or that never used one.

    The O(1) claim is the point of this module, so it is checked rather than
    asserted in a docstring.
    """
    fails: list[str] = []

    if not report.get("scope_open"):
        return ["no_scope_was_open"]

    computations = report.get("computations") or {}
    for name in FLEET_FACTS:
        count = int(computations.get(name) or 0)
        if count > 1:
            fails.append(f"fleet_fact_computed_more_than_once:{name}:{count}")

    if report.get("total_computations", 0) < 1:
        fails.append("no_fleet_fact_was_computed_in_this_scope")

    return sorted(set(fails))
