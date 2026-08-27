"""Source scheduler readiness (Gate 98E).

Answers one question - *could this system start monitoring sources on a
schedule?* - and the answer today is no, for reasons it detects rather than
declares.

## Detected, not declared

Every component here is established by looking at the thing itself:

```text
scheduler_runtime      importlib.util.find_spec over the known packages
background_worker      an importable worker module or a console entry point
periodic_trigger       a timer/cron unit checked into the repo
schedule_decision      the Gate 98B service imports and answers
circuit_breaker        the Gate 98C service imports and answers
check_run_contract     the Gate 98D service imports and answers
production_payload_store   the Gate 96/97 readiness derivation
```

No argument to any function here can turn a missing component into a present
one. There is deliberately no `scheduler_available: bool = False` parameter,
because a parameter is a claim and this gate's whole subject is the difference
between a claim and the thing claimed.

## Why not just return False

Gate 97 found two Gate 96 guards written as `x is not False`, which asserted a
constant. They would have failed a *correct* system the moment the thing became
possible. So `scheduler_runtime_available` is a `find_spec` result, not a
literal. It reads False today because nothing is installed; it will read True on
its own when something is, without anyone remembering to come back here.

## Four facts this gate is required to report

```text
scheduler_runtime_available   no queue or scheduler package is installed
background_worker_available   no worker process or entry point exists
source_monitoring_live        nothing is monitoring anything
ready_to_start_monitoring     the conjunction of every component above
```

All four are False, and the invariants fail any result where the conjunction
disagrees with its parts.

## Contracts are not runtimes

Gate 98 built three services that a scheduler would consult. Having them is not
having a scheduler, in the same way that Gate 95's payload contract was not a
payload store. The result reports the two halves separately -
`decision_layer_available` and `scheduler_runtime_available` - so neither can be
read as the other.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_source_scheduler_readiness_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]

# Every scheduler/queue runtime that would count. Gate 98A confirmed none of
# these appears in pyproject.toml or uv.lock; this checks the installed
# environment rather than the declaration, because an environment is what a
# worker would actually run in.
SCHEDULER_RUNTIME_PACKAGES = frozenset(
    {
        "celery",
        "rq",
        "apscheduler",
        "dramatiq",
        "arq",
        "huey",
        "schedule",
        "croniter",
        "taskiq",
        "procrastinate",
    }
)

# Modules that would hold a worker loop, if one existed.
WORKER_MODULE_CANDIDATES = (
    "nativeforge.workers",
    "nativeforge.worker",
    "nativeforge.scheduler",
    "nativeforge.tasks",
    "nativeforge.jobs",
)

# Where a periodic trigger would be checked in, if one were.
TRIGGER_SEARCH_DIRS = ("deploy", "systemd", "ops", "infra", "scripts")
TRIGGER_SUFFIXES = (".timer", ".cron")

# The Gate 98 decision layer.
DECISION_LAYER_MODULES = (
    "nativeforge.services.source_schedule_decision_service",
    "nativeforge.services.source_circuit_breaker_service",
    "nativeforge.services.source_check_run_contract_service",
)

COMPONENT_KEYS: tuple[str, ...] = (
    "schedule_decision_service",
    "circuit_breaker_service",
    "check_run_contract_service",
    "production_raw_payload_store",
    "scheduler_runtime",
    "background_worker",
    "periodic_trigger",
)

# The components that are a *runtime*, as opposed to a contract. Separated so a
# full set of contracts cannot be mistaken for the ability to run anything.
RUNTIME_COMPONENT_KEYS = frozenset(
    {"scheduler_runtime", "background_worker", "periodic_trigger"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def detect_scheduler_runtime() -> dict[str, Any]:
    """Which scheduler/queue runtimes are actually importable."""
    found = sorted(
        name for name in SCHEDULER_RUNTIME_PACKAGES if _module_importable(name)
    )
    return _json_safe(
        {
            "available": bool(found),
            "packages_found": found,
            "packages_considered": sorted(SCHEDULER_RUNTIME_PACKAGES),
            "detection_method": "importlib.util.find_spec",
        }
    )


def detect_background_worker() -> dict[str, Any]:
    """Whether a worker module or console entry point exists."""
    modules = [name for name in WORKER_MODULE_CANDIDATES if _module_importable(name)]

    entry_points: list[str] = []
    try:
        from importlib.metadata import entry_points as _entry_points

        for entry in _entry_points(group="console_scripts"):
            lowered = str(entry.name).lower()
            value = str(getattr(entry, "value", "")).lower()
            if "nativeforge" not in value:
                continue
            if any(word in lowered for word in ("worker", "scheduler", "beat")):
                entry_points.append(str(entry.name))
    except Exception:  # noqa: BLE001 - absence of metadata is absence of a worker
        entry_points = []

    return _json_safe(
        {
            "available": bool(modules or entry_points),
            "worker_modules": sorted(modules),
            "worker_entry_points": sorted(entry_points),
            "modules_considered": list(WORKER_MODULE_CANDIDATES),
            "detection_method": "find_spec + console_scripts entry points",
        }
    )


def detect_periodic_trigger(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Whether a timer or cron unit is checked into the repo.

    Scoped to the repo on purpose. A timer installed on one operator's laptop is
    not a property of this system, and reporting it as one would make readiness
    depend on whose machine ran the check.
    """
    root = repo_root or REPO_ROOT
    found: list[str] = []
    for directory in TRIGGER_SEARCH_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix in TRIGGER_SUFFIXES:
                found.append(str(path.relative_to(root)))

    return _json_safe(
        {
            "available": bool(found),
            "trigger_files": sorted(found),
            "searched_directories": list(TRIGGER_SEARCH_DIRS),
            "searched_suffixes": list(TRIGGER_SUFFIXES),
            "detection_method": "repo file scan",
            "host_schedulers_inspected": False,
        }
    )


def _detect_decision_service(module: str, symbol: str) -> dict[str, Any]:
    """A service counts only if it imports *and* its entry point is callable."""
    if not _module_importable(module):
        return {
            "available": False,
            "module": module,
            "detection_method": "import + callable check",
            "reason": "module_not_importable",
        }
    try:
        imported = importlib.import_module(module)
    except Exception:  # noqa: BLE001 - a service that cannot import is absent
        return {
            "available": False,
            "module": module,
            "detection_method": "import + callable check",
            "reason": "module_import_failed",
        }
    entry = getattr(imported, symbol, None)
    return {
        "available": callable(entry),
        "module": module,
        "entry_point": symbol,
        "detection_method": "import + callable check",
        "reason": None if callable(entry) else "entry_point_missing",
    }


def _detect_production_store() -> dict[str, Any]:
    """Bridged from Gate 96/97, which detect each of their own components."""
    try:
        from nativeforge.services.raw_payload_production_readiness_service import (
            build_production_readiness,
        )
    except ImportError:
        return {
            "available": False,
            "detection_method": "gate 96/97 readiness derivation",
            "reason": "readiness_service_unavailable",
        }
    readiness = build_production_readiness()
    return {
        "available": bool(readiness["production_raw_payload_store_available"]),
        "detection_method": "gate 96/97 readiness derivation",
        "reason": None,
    }


def build_scheduler_readiness(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Could this system start monitoring sources? Everything is detected."""
    components: dict[str, dict[str, Any]] = {
        "schedule_decision_service": _detect_decision_service(
            DECISION_LAYER_MODULES[0], "evaluate_schedule"
        ),
        "circuit_breaker_service": _detect_decision_service(
            DECISION_LAYER_MODULES[1], "evaluate_circuit"
        ),
        "check_run_contract_service": _detect_decision_service(
            DECISION_LAYER_MODULES[2], "build_check_run_record"
        ),
        "production_raw_payload_store": _detect_production_store(),
        "scheduler_runtime": detect_scheduler_runtime(),
        "background_worker": detect_background_worker(),
        "periodic_trigger": detect_periodic_trigger(repo_root=repo_root),
    }

    present = sorted(k for k, v in components.items() if v.get("available"))
    absent = sorted(k for k, v in components.items() if not v.get("available"))

    scheduler_runtime_available = bool(
        components["scheduler_runtime"]["available"]
    )
    background_worker_available = bool(
        components["background_worker"]["available"]
    )
    periodic_trigger_available = bool(components["periodic_trigger"]["available"])

    decision_layer_available = all(
        components[key]["available"]
        for key in (
            "schedule_decision_service",
            "circuit_breaker_service",
            "check_run_contract_service",
        )
    )

    # Nothing can be monitoring without something to run it. Derived from the
    # runtime components rather than asserted, so this cannot go stale.
    source_monitoring_live = (
        scheduler_runtime_available
        and background_worker_available
        and periodic_trigger_available
    )

    # Readiness is every component, contracts and runtime alike. A missing
    # payload store is as disqualifying as a missing worker: a check whose bytes
    # have nowhere to land produces a number nobody can verify.
    ready_to_start_monitoring = not absent

    blocked_reasons = [f"component_missing:{key}" for key in absent]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "components": components,
            "component_keys": list(COMPONENT_KEYS),
            "components_present": present,
            "components_missing": absent,
            # The four facts this gate is required to report, each derived.
            "scheduler_runtime_available": scheduler_runtime_available,
            "background_worker_available": background_worker_available,
            "source_monitoring_live": source_monitoring_live,
            "ready_to_start_monitoring": ready_to_start_monitoring,
            # Reported apart so a complete set of contracts cannot be read as a
            # scheduler. Gate 98 builds the left column, not the right.
            "decision_layer_available": decision_layer_available,
            "periodic_trigger_available": periodic_trigger_available,
            "production_raw_payload_store_available": bool(
                components["production_raw_payload_store"]["available"]
            ),
            "blocked_reasons": sorted(blocked_reasons),
            "remaining_work": sorted(
                key for key in absent if key in RUNTIME_COMPONENT_KEYS
            ),
            # Constants: nothing in this gate runs, fetches, or monitors.
            "scheduled_jobs_started": 0,
            "checks_executed": 0,
            "live_fetch_performed": False,
            "collectors_active": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def scheduler_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "live_fetch_performed",
        "collectors_active",
        "live_source_coverage",
    ):
        if result.get(constant) is not False:
            fails.append(f"readiness_claimed:{constant}")
    for counter in ("scheduled_jobs_started", "checks_executed"):
        if result.get(counter) != 0:
            fails.append(f"readiness_counted:{counter}")

    components = result.get("components") or {}
    present = set(result.get("components_present") or [])
    missing = set(result.get("components_missing") or [])

    if present & missing:
        fails.append("component_both_present_and_missing")
    if present | missing != set(COMPONENT_KEYS):
        fails.append("component_dropped_from_the_checklist")

    # Every reported component must agree with its own detection record.
    for key in COMPONENT_KEYS:
        record = components.get(key)
        if not isinstance(record, dict):
            fails.append(f"component_detection_missing:{key}")
            continue
        if bool(record.get("available")) != (key in present):
            fails.append(f"component_summary_disagrees_with_detection:{key}")
        if not record.get("detection_method"):
            fails.append(f"component_without_a_detection_method:{key}")

    # The four required facts must be derivations, not free-standing claims.
    runtime_ok = bool(result.get("scheduler_runtime_available"))
    worker_ok = bool(result.get("background_worker_available"))
    trigger_ok = bool(result.get("periodic_trigger_available"))

    if result.get("source_monitoring_live") != (
        runtime_ok and worker_ok and trigger_ok
    ):
        fails.append("monitoring_live_disagrees_with_the_runtime_components")

    if result.get("ready_to_start_monitoring") != (not missing):
        fails.append("readiness_disagrees_with_the_component_checklist")

    if result.get("ready_to_start_monitoring") and missing:
        fails.append("ready_with_missing_components")

    # Contracts are not a runtime.
    if result.get("decision_layer_available") and result.get(
        "ready_to_start_monitoring"
    ):
        if not (runtime_ok and worker_ok):
            fails.append("decision_layer_read_as_a_scheduler")

    if result.get("source_monitoring_live") and not result.get(
        "production_raw_payload_store_available"
    ):
        fails.append("monitoring_live_without_a_payload_store")

    if not result.get("ready_to_start_monitoring") and not result.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    return fails
