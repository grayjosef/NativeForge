"""Backend lifespan hook capability (Gate 102C).

The attach point a future in-process scheduler would use, and a record of the
fact that nothing is attached to it.

## An attach point is not an attachment

`main.py` now has a lifespan hook. Startup runs, shutdown runs, and between them
the application does exactly what it did before: serve HTTP. No scheduler is
started, no collector is invoked, and no request goes out.

That distinction is the whole of this gate's second half. Having somewhere for a
scheduler to attach is a prerequisite for attaching one; it is not attaching one,
and the four constants below are what stop the first being read as the second:

```text
scheduler_attached      false
collectors_started      false
urls_fetched            false
source_monitoring_live  false
```

All four are held by invariants, and the hook itself records what it did on each
transition so a test can assert the record rather than trust the flag.

## Why the hook exists at all if it does nothing

Gate 100A and Gate 101A both ended at the same wall: `main.py` had no lifespan
hook, so there was nowhere for an in-process background task to live even once a
process existed. Adding the hook is cheap, reversible, and removes that wall
without stepping over it.

It also makes the *absence* of a scheduler explicit and testable. Before, "no
scheduler runs at startup" was true because startup did not exist. Now it is true
because startup ran and deliberately started nothing, which is a claim a test can
check.

## Deterministic transitions

`record_startup` and `record_shutdown` return records, and the module keeps a
per-process transition log so a test can assert both fired exactly once and in
order. The log holds no clock: an injected `at` is recorded when supplied, and
the ordering assertions rely on sequence rather than timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_backend_lifespan_hook_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]

LIFESPAN_PHASES = frozenset({"startup", "shutdown"})

# What a future scheduler would attach to, named so the attach point is explicit
# rather than implied. Nothing reads this yet.
SCHEDULER_ATTACH_POINT = "nativeforge.main:lifespan"

# The services an in-process scheduler would consult once one exists. Recorded
# as a plan, never imported here - importing them at startup would make the
# application's boot depend on the scheduler layer for no benefit.
FUTURE_SCHEDULER_DEPENDENCIES: tuple[str, ...] = (
    "nativeforge.services.source_schedule_decision_service",
    "nativeforge.services.source_circuit_breaker_service",
    "nativeforge.services.source_scheduler_queue_service",
    "nativeforge.services.source_scheduler_dry_run_worker_service",
)

# What must be true before anything may be attached here. Each is owned by an
# earlier gate and none is satisfied today.
ATTACH_PREREQUISITES: tuple[tuple[str, str], ...] = (
    (
        "persistent_backend_live",
        "gate 101B/102B - a proven long-running process, not a smoke script",
    ),
    (
        "background_worker_available",
        "gate 98E - a worker module or console entry point; there is none",
    ),
    (
        "periodic_trigger_configured",
        "gate 98E - a timer or cron entry checked into the repo",
    ),
    (
        "production_raw_payload_store_available",
        "gate 96/97 - somewhere durable for a check's bytes to land",
    ),
)

# Per-process transition log. Reset by `reset_lifespan_log` in tests.
_TRANSITIONS: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def reset_lifespan_log() -> None:
    """Clear the transition log. For tests, and for nothing else."""
    _TRANSITIONS.clear()


def lifespan_transitions() -> list[dict[str, Any]]:
    """Every startup/shutdown this process recorded, in order."""
    return [dict(entry) for entry in _TRANSITIONS]


def _record(phase: str, *, at: Any = None) -> dict[str, Any]:
    entry = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "phase": phase,
            "at": at,
            "sequence": len(_TRANSITIONS),
            # The four constants, on every transition record. A scheduler that
            # started here would have to falsify one of them.
            "scheduler_attached": False,
            "collectors_started": False,
            "urls_fetched": False,
            "source_monitoring_live": False,
            "fabricated": False,
        }
    )
    _TRANSITIONS.append(entry)
    return dict(entry)


def record_startup(*, at: Any = None) -> dict[str, Any]:
    """Called by the lifespan hook on startup. Starts nothing."""
    return _record("startup", at=at)


def record_shutdown(*, at: Any = None) -> dict[str, Any]:
    """Called by the lifespan hook on shutdown. Stops nothing, because nothing ran."""
    return _record("shutdown", at=at)


def detect_lifespan_hook_wired(*, repo_root: Any = None) -> dict[str, Any]:
    """Whether `main.py` actually passes a lifespan to FastAPI.

    Parsed rather than imported: importing constructs the app and registers
    thirty routers, which is a side effect nobody asked for from a detection
    call. This is the same approach Gate 101B uses.

    `repo_root` exists so a test can point this at a synthetic `main.py` and
    check the half-wired case. Both halves are currently true in the real tree,
    which makes the conjunction below unobservable without one.
    """
    import ast
    from pathlib import Path

    root = Path(repo_root) if repo_root else REPO_ROOT
    path = root / "src" / "nativeforge" / "main.py"
    if not path.is_file():
        return _json_safe(
            {
                "available": False,
                "detection_method": "ast parse of main.py",
                "reason": "main_py_not_found",
            }
        )

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return _json_safe(
            {
                "available": False,
                "detection_method": "ast parse of main.py",
                "reason": "main_py_unparseable",
            }
        )

    passes_lifespan = False
    defines_lifespan = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name == "FastAPI":
                for keyword in node.keywords:
                    if keyword.arg == "lifespan":
                        passes_lifespan = True
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name == "lifespan":
                defines_lifespan = True

    return _json_safe(
        {
            # Both halves. A defined-but-unpassed lifespan is dead code, and a
            # passed-but-undefined one would not import.
            "available": passes_lifespan and defines_lifespan,
            "lifespan_defined": defines_lifespan,
            "lifespan_passed_to_fastapi": passes_lifespan,
            "attach_point": SCHEDULER_ATTACH_POINT,
            "detection_method": "ast parse of main.py",
        }
    )


def build_lifespan_hook_contract() -> dict[str, Any]:
    """The hook's capability, and everything it deliberately does not do."""
    detected = detect_lifespan_hook_wired()

    blocked_reasons: list[str] = []
    if not detected["available"]:
        blocked_reasons.append("lifespan_hook_not_wired")
    for name, _why in ATTACH_PREREQUISITES:
        blocked_reasons.append(f"attach_prerequisite_unmet:{name}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lifespan_hook_available": bool(detected["available"]),
            "lifespan_defined": bool(detected["lifespan_defined"]),
            "lifespan_passed_to_fastapi": bool(
                detected["lifespan_passed_to_fastapi"]
            ),
            "attach_point": SCHEDULER_ATTACH_POINT,
            "future_scheduler_dependencies": list(FUTURE_SCHEDULER_DEPENDENCIES),
            "attach_prerequisites": [
                {"requirement": name, "owner": why}
                for name, why in ATTACH_PREREQUISITES
            ],
            # The four the gate requires, held by invariants.
            "scheduler_attached": False,
            "collectors_started": False,
            "urls_fetched": False,
            "source_monitoring_live": False,
            # And the rest of the boundary.
            "live_source_coverage": False,
            "raw_payloads_written": False,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "fabricated": False,
        }
    )


def lifespan_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "scheduler_attached",
        "collectors_started",
        "urls_fetched",
        "source_monitoring_live",
        "live_source_coverage",
        "raw_payloads_written",
    ):
        if contract.get(constant) is not False:
            fails.append(f"lifespan_claimed:{constant}")

    # A hook is available only when it is both defined and passed. A defined
    # lifespan nobody wired in is dead code that would report a capability the
    # application does not have.
    if contract.get("lifespan_hook_available") != (
        bool(contract.get("lifespan_defined"))
        and bool(contract.get("lifespan_passed_to_fastapi"))
    ):
        fails.append("lifespan_availability_disagrees_with_its_halves")

    if contract.get("attach_point") != SCHEDULER_ATTACH_POINT:
        fails.append("attach_point_altered")

    # An attach point with nothing attached must say what is missing.
    if not contract.get("scheduler_attached") and not contract.get(
        "blocked_reasons"
    ):
        fails.append("nothing_attached_without_a_reason")

    # Every prerequisite must still be listed. Dropping one would make the
    # remaining work look shorter than it is.
    listed = {
        item.get("requirement")
        for item in contract.get("attach_prerequisites") or []
    }
    if listed != {name for name, _ in ATTACH_PREREQUISITES}:
        fails.append("attach_prerequisite_dropped_from_the_checklist")

    return fails


def transition_invariant_failures(entries: list[dict[str, Any]]) -> list[str]:
    """Invariants over what the hook actually did on this process's transitions."""
    fails: list[str] = []

    for entry in entries:
        if entry.get("phase") not in LIFESPAN_PHASES:
            fails.append(f"phase_out_of_vocabulary:{entry.get('phase')}")
        for constant in (
            "scheduler_attached",
            "collectors_started",
            "urls_fetched",
            "source_monitoring_live",
        ):
            if entry.get(constant) is not False:
                fails.append(f"transition_claimed:{constant}")

    phases = [entry.get("phase") for entry in entries]
    if phases.count("startup") > 1:
        fails.append("startup_recorded_more_than_once")
    if phases.count("shutdown") > 1:
        fails.append("shutdown_recorded_more_than_once")
    if "shutdown" in phases and "startup" not in phases:
        fails.append("shutdown_without_a_startup")
    if (
        "startup" in phases
        and "shutdown" in phases
        and phases.index("shutdown") < phases.index("startup")
    ):
        fails.append("shutdown_recorded_before_startup")

    return fails
