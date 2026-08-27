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

## Four facts, and what Gate 99D changed about the first one

```text
scheduler_runtime_available   true - runtime_mode is dry_run_in_process
background_worker_available   false - no worker process or entry point exists
source_monitoring_live        false - nothing is monitoring anything
ready_to_start_monitoring     false - the conjunction of every component
```

Gate 98 reported the first as False, meaning "no scheduler package is
installed". Gate 99 built an in-process dry-run queue, so the honest answer is
now neither plain yes nor plain no, and a bare boolean would have to mislead in
one direction or the other.

So `runtime_mode` carries the real answer and the boolean is derived from it:

```text
none                        nothing at all
dry_run_in_process          a queue can be built here, executing nothing
external_worker_configured  a worker exists but is not proven live
production_worker_live      a worker is running and consuming jobs
```

The two are always reported together, because `scheduler_runtime_available:
true` read on its own - in a copied CSV row, in a status page - would be taken
for a production scheduler. `scheduler_package_installed` remains available
separately as the narrow question Gate 98 was asking.

`source_monitoring_live` is derived from `runtime_mode in LIVE_RUNTIME_MODES`
rather than from the boolean, so a dry-run runtime can never contribute to a
claim that monitoring is live, however many other components appear beside it.
An invariant fails any result where it does.

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

# Gate 99B/C: the in-process dry-run runtime. Importable and callable means a
# queue can genuinely be built in this process - which is a runtime, of the
# weakest possible kind, and `runtime_mode` says which kind.
DRY_RUN_RUNTIME_MODULES = (
    ("nativeforge.services.source_scheduler_job_model_service", "build_source_job"),
    ("nativeforge.services.source_scheduler_queue_service", "build_dry_run_queue"),
)

# Gate 99D. Four modes, ordered by how much they permit.
#
# `none`                        nothing at all
# `dry_run_in_process`          a queue can be built here, executing nothing
# `external_worker_configured`  a worker exists but has not been proven live
# `production_worker_live`      a worker is running and consuming jobs
#
# The gap between the second and third is the whole of the remaining work. A
# dry-run runtime produces a list of work nobody has agreed to do; it is not
# monitoring, and `source_monitoring_live` stays derived from the worker and the
# trigger rather than from this.
RUNTIME_MODES = frozenset(
    {
        "none",
        "dry_run_in_process",
        "external_worker_configured",
        "production_worker_live",
    }
)

# Modes that mean *something* can schedule. Deliberately not "modes that mean
# monitoring is possible" - those are two different questions and conflating
# them is what Gate 98F had to unpick in two other services.
RUNTIME_AVAILABLE_MODES = frozenset(
    {"dry_run_in_process", "external_worker_configured", "production_worker_live"}
)

# Modes that could put a request on the wire.
LIVE_RUNTIME_MODES = frozenset({"production_worker_live"})

COMPONENT_KEYS: tuple[str, ...] = (
    "schedule_decision_service",
    "circuit_breaker_service",
    "check_run_contract_service",
    "production_raw_payload_store",
    "dry_run_runtime",
    "scheduler_runtime",
    "background_worker",
    "periodic_trigger",
)

# The components that are a *runtime*, as opposed to a contract. Separated so a
# full set of contracts cannot be mistaken for the ability to run anything.
#
# `dry_run_runtime` is deliberately NOT in this set. It is a runtime in the
# narrow sense that code runs, but it is not one of the things whose absence
# stops monitoring - and listing it here would make `remaining_work` shrink for
# a reason that does not move the system any closer to monitoring.
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


def detect_dry_run_runtime() -> dict[str, Any]:
    """Whether the in-process dry-run queue can actually be built here.

    Import *and* callable, the same standard the decision-layer components are
    held to. A module that imports but has lost its entry point is not a runtime,
    and detecting only the import would let a half-deleted service keep
    reporting itself present.
    """
    found: list[str] = []
    for module, symbol in DRY_RUN_RUNTIME_MODULES:
        if not _module_importable(module):
            continue
        try:
            imported = importlib.import_module(module)
        except Exception:  # noqa: BLE001 - a runtime that cannot import is absent
            continue
        if callable(getattr(imported, symbol, None)):
            found.append(module)

    return _json_safe(
        {
            "available": len(found) == len(DRY_RUN_RUNTIME_MODULES),
            "modules_found": sorted(found),
            "modules_required": [m for m, _ in DRY_RUN_RUNTIME_MODULES],
            "detection_method": "import + callable check",
            "executes_jobs": False,
            "fetches": False,
        }
    )


def detect_runtime_mode(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Which runtime mode this system is actually in.

    Resolved from the strongest evidence downward, so a stronger mode is never
    reported on weaker evidence.
    """
    worker = detect_background_worker()
    trigger = detect_periodic_trigger(repo_root=repo_root)
    dry_run = detect_dry_run_runtime()

    if worker["available"] and trigger["available"]:
        # A worker and something to fire it. This is the only mode that could
        # put a request on the wire, and nothing in the repository reaches it.
        mode = "production_worker_live"
        evidence = "background worker and periodic trigger both detected"
    elif worker["available"]:
        mode = "external_worker_configured"
        evidence = "background worker detected, no periodic trigger"
    elif dry_run["available"]:
        mode = "dry_run_in_process"
        evidence = "in-process dry-run queue importable and callable"
    else:
        mode = "none"
        evidence = "no runtime of any kind detected"

    return _json_safe(
        {
            "runtime_mode": mode,
            "evidence": evidence,
            "detection_method": "import + callable check, worker and trigger detection",
            "dry_run_runtime_available": dry_run["available"],
            "background_worker_available": worker["available"],
            "periodic_trigger_available": trigger["available"],
            # A dry-run runtime executes nothing. Only the live mode could.
            "executes_jobs": mode in LIVE_RUNTIME_MODES,
        }
    )


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
        "dry_run_runtime": detect_dry_run_runtime(),
        "scheduler_runtime": detect_scheduler_runtime(),
        "background_worker": detect_background_worker(),
        "periodic_trigger": detect_periodic_trigger(repo_root=repo_root),
    }

    present = sorted(k for k, v in components.items() if v.get("available"))
    absent = sorted(k for k, v in components.items() if not v.get("available"))

    runtime = detect_runtime_mode(repo_root=repo_root)
    runtime_mode = runtime["runtime_mode"]

    # Gate 99D. `scheduler_runtime_available` used to mean "a scheduler package
    # is installed". It now means "some runtime mode exists", and `runtime_mode`
    # says which - because after Gate 99 the honest answer is neither plain yes
    # nor plain no. A bare boolean would have to lie in one direction or the
    # other, so the boolean is derived from the mode and always reported beside
    # it.
    scheduler_runtime_available = runtime_mode in RUNTIME_AVAILABLE_MODES
    scheduler_package_installed = bool(components["scheduler_runtime"]["available"])
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
    #
    # Gate 99D tightened this. It used to read `scheduler_runtime_available and
    # worker and trigger`, which was right while that boolean meant "a scheduler
    # package is installed". Now that it also covers `dry_run_in_process`, the
    # test has to be on the *mode*: a dry-run runtime must never be able to
    # contribute to a claim that monitoring is live, however many other
    # components appear alongside it.
    source_monitoring_live = (
        runtime_mode in LIVE_RUNTIME_MODES
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
            # The four facts, each derived.
            "scheduler_runtime_available": scheduler_runtime_available,
            "background_worker_available": background_worker_available,
            "source_monitoring_live": source_monitoring_live,
            "ready_to_start_monitoring": ready_to_start_monitoring,
            # Gate 99D. Always reported beside the boolean above, because
            # `scheduler_runtime_available: true` on its own would be read as a
            # production scheduler by anyone who copied the line out.
            "runtime_mode": runtime_mode,
            "runtime_mode_evidence": runtime["evidence"],
            "runtime_executes_jobs": runtime["executes_jobs"],
            "dry_run_runtime_available": bool(
                components["dry_run_runtime"]["available"]
            ),
            # Kept distinct from `scheduler_runtime_available`, which changed
            # meaning in Gate 99D. This is still the narrow question Gate 98
            # asked: is a scheduler or queue *package* installed?
            "scheduler_package_installed": scheduler_package_installed,
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
    mode = result.get("runtime_mode")

    if mode not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")

    # Gate 99D. The boolean is derived from the mode, never set beside it.
    if runtime_ok != (mode in RUNTIME_AVAILABLE_MODES):
        fails.append("runtime_available_disagrees_with_the_runtime_mode")

    # A dry-run runtime executes nothing, and no arrangement of other
    # components may turn it into monitoring.
    if result.get("runtime_executes_jobs") != (mode in LIVE_RUNTIME_MODES):
        fails.append("executes_jobs_disagrees_with_the_runtime_mode")
    if mode == "dry_run_in_process":
        if result.get("runtime_executes_jobs"):
            fails.append("dry_run_runtime_claimed_execution")
        if result.get("source_monitoring_live"):
            fails.append("dry_run_runtime_read_as_live_monitoring")

    if result.get("source_monitoring_live") != (
        mode in LIVE_RUNTIME_MODES and worker_ok and trigger_ok
    ):
        fails.append("monitoring_live_disagrees_with_the_runtime_components")

    # A mode stronger than dry-run must have the evidence behind it.
    if mode in {"external_worker_configured", "production_worker_live"}:
        if not worker_ok:
            fails.append("worker_mode_without_a_detected_worker")
    if mode in LIVE_RUNTIME_MODES and not trigger_ok:
        fails.append("live_mode_without_a_periodic_trigger")

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
