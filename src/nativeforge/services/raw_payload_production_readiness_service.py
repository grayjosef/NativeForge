"""Production raw payload storage readiness (Gate 96E).

Reports whether production raw payload storage is ready. Today it is not, and
the reason is specific: there is a metadata table and no body store.

## The derivation, which is the whole point

```text
metadata_table_available      true   after Alembic 0028
secret_scan_available         true   Gate 95D
promotion_gate_available      true   Gate 95E
body_store_configured         FALSE  no client, no bucket, no credential

production_raw_payload_store_available = metadata AND body_store AND
                                         scan AND promotion_gate
                                       = false
production_storage_live                = available AND collectors active
                                       = false
```

Both are **derived**, never set beside their inputs. `production_storage_live`
is deliberately stricter than `available`: a store can be ready and still not be
live, and conflating the two is how "we built it" becomes "it is running".

## Adding a table is not production storage

Alembic 0028 creates `nf_raw_source_payloads`. That makes one of four
requirements true. The gate's own precedent for this is migration 0027, which
carries the line *"Approved environment: staging/dev proof first. No production
customer claim."* in its docstring - the distinction was drawn before this gate
needed it.

## Everything is detected

Each input is established by looking: importing the module, inspecting the
settings model, checking the migration file. Nothing here accepts a caller
saying a component exists. That is the Gate 87-89 lesson - a flag asserting
provenance is a claim about a claim - applied to infrastructure instead of to
records.

## next_required_actions is ordered by what blocks first

An operator reading this should be able to start at the top. The list names the
decision, not just the gap: "choose an object store and add a client" is
actionable; "body store missing" is not.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.production_raw_payload_repository_service import (
    detect_metadata_table,
)
from nativeforge.services.raw_payload_body_store_contract_service import (
    build_body_store_contract,
)

SCHEMA_VERSION = "nf_raw_payload_production_readiness_v1"

# The four components production storage requires. Named so the derivation is
# a set membership check rather than a chain of ands nobody can audit.
REQUIRED_COMPONENTS: tuple[str, ...] = (
    "metadata_table_available",
    "body_store_configured",
    "secret_scan_available",
    "promotion_gate_available",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_available(module_path: str, attribute: str) -> bool:
    """Import and check. A module that does not expose the callable is absent."""
    try:
        import importlib

        module = importlib.import_module(module_path)
    except ImportError:
        return False
    return callable(getattr(module, attribute, None))


def detect_secret_scan_available() -> bool:
    return _module_available(
        "nativeforge.services.raw_payload_secret_scan_service",
        "scan_payload_for_secrets",
    )


def detect_promotion_gate_available() -> bool:
    return _module_available(
        "nativeforge.services.raw_payload_promotion_gate_service",
        "evaluate_payload_promotion",
    )


def detect_local_store_available() -> bool:
    return _module_available(
        "nativeforge.services.local_raw_payload_store_service",
        "store_raw_payload",
    )


def build_production_readiness(
    *, session: Any = None, collectors_active: int = 0
) -> dict[str, Any]:
    """The readiness position. Every input detected, both verdicts derived."""
    body_store = build_body_store_contract()

    components = {
        "metadata_table_available": detect_metadata_table(session),
        "body_store_configured": bool(body_store.get("body_store_configured")),
        "secret_scan_available": detect_secret_scan_available(),
        "promotion_gate_available": detect_promotion_gate_available(),
    }

    missing = [name for name in REQUIRED_COMPONENTS if not components[name]]

    # Derived, never asserted beside the components.
    available = not missing
    # Stricter: ready is not running.
    live = bool(available and collectors_active > 0)

    blocked: list[str] = [f"component_missing:{name}" for name in missing]
    blocked.extend(body_store.get("blocked_reasons") or [])

    actions: list[str] = []
    if not components["body_store_configured"]:
        actions.append(
            "choose an object store, add its client to the dependency set, and "
            "add endpoint/bucket/credential settings"
        )
        actions.append(
            "implement the body store against the four required guarantees: "
            "content-addressed, hash-preserving, secret-scan-clean before "
            "promotion, no body values in logs"
        )
    if not components["metadata_table_available"]:
        actions.append("run Alembic migrations to head so 0028 applies")
    if available and not live:
        actions.append(
            "production storage is ready but no collector is active; "
            "activation is a separate decision with its own preflight"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **components,
            "object_store_required": True,
            "body_store_mode": body_store.get("detected_mode"),
            "local_raw_payload_store_available": detect_local_store_available(),
            # The two derived verdicts.
            "production_raw_payload_store_available": available,
            "production_storage_live": live,
            "required_components": list(REQUIRED_COMPONENTS),
            "components_present": sorted(
                name for name in REQUIRED_COMPONENTS if components[name]
            ),
            "components_missing": missing,
            "blocked_reasons": sorted(set(blocked)),
            "next_required_actions": actions,
            # Constants for this gate.
            "collectors_active": int(collectors_active),
            "source_monitoring_active": False,
            "live_fetch_performed": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def production_readiness_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if report.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if report.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("source_monitoring_active", "live_fetch_performed",
                     "live_source_coverage"):
        if report.get(constant) is not False:
            fails.append(f"readiness_claimed:{constant}")

    # Availability is derived from every component, not from a subset.
    components_present = set(report.get("components_present") or [])
    components_missing = set(report.get("components_missing") or [])
    if components_present & components_missing:
        fails.append("component_both_present_and_missing")
    if components_present | components_missing != set(REQUIRED_COMPONENTS):
        fails.append("component_dropped_from_the_checklist")

    available = report.get("production_raw_payload_store_available")
    if available != (not components_missing):
        fails.append("availability_disagrees_with_components")

    # A store cannot be available without a body store, whatever else is true.
    if available and not report.get("body_store_configured"):
        fails.append("available_without_a_configured_body_store")

    # Live is strictly stronger than available.
    live = report.get("production_storage_live")
    if live and not available:
        fails.append("live_without_being_available")
    if live and not report.get("collectors_active"):
        fails.append("live_with_no_active_collectors")

    if report.get("object_store_required") is not True:
        fails.append("object_store_requirement_dropped")

    # A local store is a different thing and must never satisfy production.
    if report.get("local_raw_payload_store_available") and available and not (
        report.get("body_store_configured")
    ):
        fails.append("local_store_counted_toward_production_availability")

    if not available and not report.get("blocked_reasons"):
        fails.append("unavailable_without_a_reason")
    if components_missing and not report.get("next_required_actions"):
        fails.append("missing_components_without_next_actions")

    return fails
