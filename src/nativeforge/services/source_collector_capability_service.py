"""Whether a collector can actually run for ONE source (Gate 163).

`collector_status` used to come from `phase1_collector_activation_policy_service`,
whose `collectors_active` is a hardcoded `0` — and whose own invariant checker
FAILS if that number is ever nonzero. It cannot be made true, by design, and
this module does not try: phase 1's historical zero is left exactly as it is.

Instead the question is asked of the thing that can answer it, the way the
fixture branch of the fact resolver already does:

```text
fixture source  ->  Gate 161's execution envelope IS the collector,
                    so the question is whether that envelope is ready
real source     ->  the same envelope, PLUS whether a collector capability
                    exists for THIS source's adapter
```

## Capability is not authorization

Worth saying plainly, because conflating them is how a gate gets skipped:

```text
activation approval  a human said this source may be collected   AUTHORIZATION
collector capability code exists that can actually collect it    CAPABILITY
```

An approval does not make a collector exist, and a collector existing does not
make it permitted. Both are required and neither substitutes. Nothing in this
module reads a decision record, and nothing here permits a request.

## Measured per source AND per adapter

A generic "the envelope is ready" is not capability for a particular source.
The registry row names an `adapter_key`, and this asks whether that adapter can
build a real request for THIS row:

```text
envelope_ready             Gate 161's own health lane, measured
adapter_is_known           the adapter_key has a capability descriptor
adapter_module_resolves    the module imports
request_builds_for_source  the builder produces a request from THIS row
endpoint_matches_registry  the adapter targets the row's own authority
transport_is_injectable    the executor takes an injectable transport
```

The last one is load-bearing rather than cosmetic. The adapter's default
transport is `default_grants_gov_http_post`, which gates on
`assert_live_network_allowed` — the legacy environment flag. A capability that
could only be exercised through that default would make the flag required for
the authorized path, so "capable" here means capable of being driven through
the authorization-aware enforcement path instead.

An unknown adapter yields `not_active` and names why, so the refusal is
readable rather than a bare false.
"""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

SCHEMA_VERSION = "nf_source_collector_capability_v1"

ACTIVE = "active"
NOT_ACTIVE = "not_active"

#: What a collector capability for one adapter consists of. Deliberately a
#: description of code that exists, not a flag: every field is resolved and
#: exercised, and a field that cannot be resolved makes the adapter incapable.
ADAPTER_CAPABILITIES: dict[str, dict[str, str]] = {
    "grants_gov_search2": {
        "module": "nativeforge.services.grants_gov_search_api_adapter_service",
        "request_builder": "build_grants_gov_search_body",
        "executor": "search_grants_gov_opportunities",
        "endpoint_constant": "SEARCH2_URL",
        "transport_parameter": "http_post",
        "method": "POST",
    },
}

#: The measurements a capable adapter must pass, in the order a reader wants
#: them: the runtime first, then the adapter, then this specific source.
CAPABILITY_CHECKS: tuple[str, ...] = (
    "envelope_ready",
    "adapter_is_known",
    "adapter_module_resolves",
    "request_builds_for_source",
    "endpoint_matches_registry",
    "transport_is_injectable",
)

NOT_IMPLIED: tuple[str, ...] = (
    "capability is not authorization - no decision record is read here",
    "capability is not an opt-in - nothing in this module permits a request",
    "capability is not a running collector - it is code that could run",
    "a capable adapter still refuses without a warrant at dispatch",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _host_of(url: Any) -> str:
    text = str(url or "")
    return text.split("//", 1)[-1].split("/", 1)[0].lower()


def _envelope_ready(*, connection: Any, organization_id: Any) -> bool:
    """Gate 161's own lane, measured. WITH the connection.

    Without one the lane reads no attempt table, reports not-ready, and the
    collector fact would refuse for a reason that has nothing to do with
    collectors.
    """
    try:
        from nativeforge.services.source_collector_execution_health_service import (
            build_execution_health,
        )

        return bool(
            build_execution_health(
                connection=connection, organization_id=organization_id
            ).get("execution_envelope_ready")
        )
    except Exception:  # noqa: BLE001 - an unobservable lane is not a ready one
        return False


def measure_collector_capability(
    *,
    source_id: Any = None,
    registry_row: dict[str, Any] | None = None,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Can a collector actually run for this source? Measured, never declared."""
    row = registry_row or {}
    adapter_key = str(row.get("adapter_key") or "").strip()
    descriptor = ADAPTER_CAPABILITIES.get(adapter_key)

    measured: dict[str, bool] = dict.fromkeys(CAPABILITY_CHECKS, False)
    notes: dict[str, Any] = {}

    measured["envelope_ready"] = _envelope_ready(
        connection=connection, organization_id=organization_id
    )
    measured["adapter_is_known"] = descriptor is not None
    if descriptor is None:
        notes["adapter_key"] = adapter_key or "absent"
        notes["known_adapters"] = sorted(ADAPTER_CAPABILITIES)
        return _capability_result(
            source_id=source_id,
            adapter_key=adapter_key,
            measured=measured,
            notes=notes,
        )

    module: Any = None
    try:
        module = importlib.import_module(descriptor["module"])
        measured["adapter_module_resolves"] = True
    except Exception as exc:  # noqa: BLE001
        notes["import_error"] = f"{type(exc).__name__}: {exc}"

    if module is not None:
        # Build a real request for THIS row. A builder that cannot produce one
        # is not a capability for this source, whatever it can do for others.
        try:
            builder = getattr(module, descriptor["request_builder"])
            built = builder(dict(row))
            measured["request_builds_for_source"] = bool(
                isinstance(built, dict) and built
            )
            notes["request_body"] = built if isinstance(built, dict) else None
        except Exception as exc:  # noqa: BLE001
            notes["request_builder_error"] = f"{type(exc).__name__}: {exc}"

        # The adapter must target this row's own authority. An adapter aimed at
        # a different host is capability for a different source.
        try:
            endpoint = getattr(module, descriptor["endpoint_constant"])
            declared = row.get("source_url")
            measured["endpoint_matches_registry"] = bool(
                _host_of(endpoint)
                and _host_of(endpoint) == _host_of(declared)
                and str(endpoint).strip() == str(declared or "").strip()
            )
            notes["adapter_endpoint"] = str(endpoint)
            notes["registry_endpoint"] = str(declared or "")
        except Exception as exc:  # noqa: BLE001
            notes["endpoint_error"] = f"{type(exc).__name__}: {exc}"

        # And it must accept an injected transport, or the only way to exercise
        # it is its own default - which gates on the legacy environment flag.
        try:
            executor = getattr(module, descriptor["executor"])
            parameters = set(inspect.signature(executor).parameters)
            measured["transport_is_injectable"] = bool(
                descriptor["transport_parameter"] in parameters
            )
            notes["executor"] = descriptor["executor"]
            notes["transport_parameter"] = descriptor["transport_parameter"]
        except Exception as exc:  # noqa: BLE001
            notes["executor_error"] = f"{type(exc).__name__}: {exc}"

    return _capability_result(
        source_id=source_id,
        adapter_key=adapter_key,
        measured=measured,
        notes=notes,
    )


def _capability_result(
    *,
    source_id: Any,
    adapter_key: str,
    measured: dict[str, bool],
    notes: dict[str, Any],
) -> dict[str, Any]:
    unmet = sorted(name for name in CAPABILITY_CHECKS if not measured[name])
    capable = not unmet
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": str(source_id or "") or None,
            "adapter_key": adapter_key or None,
            "collector_status": ACTIVE if capable else NOT_ACTIVE,
            "capable": capable,
            "measured": measured,
            "checks": list(CAPABILITY_CHECKS),
            "unmet": unmet,
            "notes": notes,
            "evidence_ref": (
                "source_collector_capability_service:measure_collector_capability"
            ),
            # Said in the output, so a reader of the fact does not have to find
            # this module's docstring to learn what it did NOT establish.
            "capability_is_not_authorization": (
                "an approval says a source may be collected; this says code "
                "exists that can collect it. Both are required and neither "
                "substitutes for the other."
            ),
            "phase1_is_untouched": (
                "phase1_collector_activation_policy_service.collectors_active "
                "stays 0. Its invariant checker fails if that number is ever "
                "nonzero, and this module does not write to it or read it."
            ),
            "not_implied": list(NOT_IMPLIED),
        }
    )


def capability_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a capability report that contradicts itself or overclaims."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    capable = bool(result.get("capable"))
    status = str(result.get("collector_status") or "")
    if capable and status != ACTIVE:
        fails.append("capable_without_saying_active")
    if not capable and status != NOT_ACTIVE:
        fails.append("not_capable_but_status_is_not_not_active")

    # capable and unmet must agree, both directions. One of them alone is how
    # "every check passed" becomes "the report said so".
    unmet = list(result.get("unmet") or [])
    if capable and unmet:
        fails.append(f"capable_alongside_unmet_checks:{unmet}")
    if not capable and not unmet:
        fails.append("not_capable_without_naming_an_unmet_check")

    measured = result.get("measured") or {}
    if set(measured) != set(CAPABILITY_CHECKS):
        fails.append("measured_does_not_match_the_declared_checks")
    for name in CAPABILITY_CHECKS:
        if measured.get(name) not in (True, False):
            fails.append(f"check_was_not_measured:{name}")

    if not str(result.get("capability_is_not_authorization") or "").strip():
        fails.append("did_not_say_capability_is_not_authorization")

    return sorted(set(fails))
