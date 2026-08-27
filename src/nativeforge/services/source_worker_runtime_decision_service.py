"""Worker runtime decision (Gate 100B).

Records which worker boundary has been selected, and what is still missing before
live collection could run. It starts nothing.

## Five modes, and one of them is not a detection

Gate 99D built a *detection* ladder: four modes resolved from evidence in the
repository. This gate adds a fifth that evidence cannot produce:

```text
none                        nothing at all                       detected
dry_run_in_process          a queue can be built here            detected
external_worker_required    a worker is needed, none is chosen    DECIDED
external_worker_configured  a worker exists, not proven live      detected
production_worker_live      a worker is running and consuming     detected
```

`external_worker_required` is a statement about intent, not about the world. No
amount of inspection can find it, because it is the conclusion a person reached
after inspecting: *this needs a worker and we have not picked one*.

Keeping it in the same vocabulary as the detected modes would blur that, so
`DETECTED_RUNTIME_MODES` is imported from Gate 99 rather than restated, and this
module declares only the one mode it adds. An invariant checks the two sets have
not drifted apart.

## The decision, and the prerequisite the brief does not mention

Gate 100A found no long-running backend process. The two running systemd units
serve the frontend and a tunnel; the API is started only by smoke scripts that
kill it again, and `main.py` has no lifespan hook. So an in-process worker has
nowhere to live, and an external worker would be infrastructure for a service
that is not deployed.

That makes the ordering:

```text
1  deploy the backend as a persistent process    <- does not exist
2  decide in-process vs external worker
3  if external: choose a broker, add the dependency
4  add a periodic trigger
```

`next_required_actions` reports these in order, and step 1 comes first because
choosing a broker before it would be premature in a way that costs money and
lock-in.

## What may not be true

```text
production_worker_live        false, always, in this gate
background_worker_available   false unless a worker is actually detected
```

Neither is a constant asserted in a return value - Gate 97 found two guards of
that shape and had to convert them. `background_worker_available` is bridged
from Gate 98E's detection, and `production_worker_live` is derived from the
resolved mode. Both will change on their own when the world changes.

## No mode implies monitoring

`source_monitoring_live` is False on every decision and never derived from the
mode. Even `production_worker_live` - which this gate cannot reach - would mean
a worker is consuming jobs, not that any source is being watched. Those are
different facts and Gate 98F exists because they were once conflated.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_scheduler_readiness_service import (
    LIVE_RUNTIME_MODES,
    build_scheduler_readiness,
)
from nativeforge.services.source_scheduler_readiness_service import (
    RUNTIME_MODES as DETECTED_RUNTIME_MODES,
)

SCHEMA_VERSION = "nf_source_worker_runtime_decision_v1"

# The one mode detection cannot produce, because it is a conclusion rather than
# an observation. Declared separately so the boundary stays visible.
DECISION_ONLY_RUNTIME_MODES = frozenset({"external_worker_required"})

RUNTIME_MODES = DETECTED_RUNTIME_MODES | DECISION_ONLY_RUNTIME_MODES

# Modes in which *some* runtime exists that can do something.
WORKER_RUNTIME_AVAILABLE_MODES = frozenset(
    {"dry_run_in_process", "external_worker_configured", "production_worker_live"}
)

# Modes that mean a real background worker is present. `external_worker_required`
# is deliberately absent: needing a worker is not having one.
BACKGROUND_WORKER_MODES = frozenset(
    {"external_worker_configured", "production_worker_live"}
)

# The only mode that could put a request on the wire. Bridged from Gate 99.
PRODUCTION_WORKER_MODES = LIVE_RUNTIME_MODES

# Modes needing an external worker: either it is required and missing, or it is
# there. Used to decide whether a broker and a dependency are in the picture.
EXTERNAL_WORKER_MODES = DECISION_ONLY_RUNTIME_MODES | BACKGROUND_WORKER_MODES

# Gate 100A's decision. An in-process dry-run worker needs nothing new, because
# uvicorn and fastapi are already declared dependencies.
DRY_RUN_WORKER_REQUIRES_DEPENDENCY = False

# Candidate brokers, recorded so the choice is visible as still open rather than
# quietly absent. None is selected.
BROKER_CANDIDATES: tuple[str, ...] = (
    "redis",
    "rabbitmq",
    "postgres_queue",
    "sqs",
    "none_systemd_timer",
)

# The ordered prerequisites, from Gate 100A. The first is a deployment decision
# with no code in this repository behind it, and it precedes every other one.
NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "deploy_backend_process",
        "no long-running backend process exists; the API is started only by "
        "smoke scripts and no systemd unit serves it",
    ),
    (
        "choose_worker_topology",
        "in-process (FastAPI lifespan) or external worker; main.py has no "
        "lifespan hook today",
    ),
    (
        "select_broker_if_external",
        "only if the topology is external; an in-process or systemd-timer "
        "worker needs no broker and no dependency",
    ),
    (
        "add_periodic_trigger",
        "a systemd .timer checked into the repo is detected by Gate 98E",
    ),
    (
        "configure_production_object_store",
        "Gate 97's seam, deployed and round-tripped; a check with nowhere to "
        "put its bytes produces a number nobody can verify",
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _detected_readiness(repo_root: Any = None) -> dict[str, Any]:
    """Gate 98E/99D detection. Never passed in."""
    try:
        return build_scheduler_readiness(repo_root=repo_root)
    except Exception:  # noqa: BLE001 - absent detection is absent capability
        return {}


def build_worker_runtime_decision(
    *,
    repo_root: Any = None,
    selected_broker: Any = None,
    systemd_unit_configured: bool = False,
) -> dict[str, Any]:
    """The selected worker boundary. Nothing is started."""
    readiness = _detected_readiness(repo_root)

    detected_mode = _norm(
        readiness.get("runtime_mode"), DETECTED_RUNTIME_MODES, fallback="none"
    )
    # Detected, never declared. Gate 98E inspects for a worker module or a
    # console entry point; there is none.
    background_worker_available = bool(readiness.get("background_worker_available"))
    dry_run_runtime_available = bool(readiness.get("dry_run_runtime_available"))

    # Resolve the mode. Detection wins wherever it can speak; the decision-only
    # mode fills the gap detection cannot describe - a worker is needed, and
    # none has been chosen.
    if background_worker_available:
        mode = detected_mode
    elif dry_run_runtime_available:
        # A dry-run runtime exists *and* a real worker is still required. The
        # first is what we have; the second is the decision. Reporting the
        # first alone would let "we have a runtime" stand in for "we have a
        # worker", which is the substitution this gate exists to prevent.
        mode = "dry_run_in_process"
    else:
        mode = "external_worker_required"

    worker_runtime_available = mode in WORKER_RUNTIME_AVAILABLE_MODES
    production_worker_live = mode in PRODUCTION_WORKER_MODES

    # A real worker is still required regardless of the dry-run runtime, and
    # saying so is the point of this service.
    external_worker_required = not background_worker_available

    broker = _norm(selected_broker, frozenset(BROKER_CANDIDATES), fallback="none")
    broker_selected = selected_broker is not None and broker in BROKER_CANDIDATES
    # A broker is only in the picture for an external worker. An in-process or
    # systemd-timer worker needs none.
    broker_required = external_worker_required and broker != "none_systemd_timer"

    dependency_required = broker_required and broker_selected
    dependency_selected = None

    # Gate 101E. An in-process worker needs a process to be in, and Gate 101A
    # found there is none - the API is started only by smoke scripts that kill
    # it on exit. This is why `choose_worker_topology` sits behind
    # `deploy_backend_process` in the sequence below rather than beside it.
    persistent_backend_live = bool(readiness.get("persistent_backend_live"))
    backend_runtime_contract_available = bool(
        readiness.get("backend_runtime_contract_available")
    )

    blocked_reasons: list[str] = []
    if not persistent_backend_live:
        blocked_reasons.append("persistent_backend_not_live")
    if not background_worker_available:
        blocked_reasons.append("background_worker_not_detected")
    if external_worker_required and not broker_selected:
        blocked_reasons.append("broker_not_selected")
    if not systemd_unit_configured:
        blocked_reasons.append("systemd_unit_not_configured")
    if not readiness.get("production_raw_payload_store_available"):
        blocked_reasons.append("production_raw_payload_store_unavailable")
    if not readiness.get("periodic_trigger_available"):
        blocked_reasons.append("periodic_trigger_not_configured")

    next_actions = [
        {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "runtime_mode": mode,
            "detected_runtime_mode": detected_mode,
            "worker_runtime_available": worker_runtime_available,
            "background_worker_available": background_worker_available,
            "production_worker_live": production_worker_live,
            "dry_run_worker_available": dry_run_runtime_available,
            "external_worker_required": external_worker_required,
            # Gate 101E. Reported so the ordering is visible on the record: an
            # in-process topology is not selectable until a backend exists.
            "persistent_backend_live": persistent_backend_live,
            "backend_runtime_contract_available": backend_runtime_contract_available,
            "in_process_worker_possible": persistent_backend_live,
            "dependency_required": dependency_required,
            "dependency_selected": dependency_selected,
            "broker_required": broker_required,
            "broker_selected": broker if broker_selected else None,
            "broker_candidates": list(BROKER_CANDIDATES),
            "systemd_unit_required": external_worker_required,
            "systemd_unit_configured": bool(systemd_unit_configured),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": next_actions,
            # Gate 100A: an in-process dry-run worker needs nothing new.
            "dry_run_worker_requires_dependency": DRY_RUN_WORKER_REQUIRES_DEPENDENCY,
            # No mode implies monitoring. A worker consuming jobs is not a
            # source being watched, and those were conflated once already.
            "source_monitoring_live": False,
            "collectors_executed": False,
            "urls_fetched": False,
            "raw_payloads_written": False,
            "live_source_coverage": False,
            "worker_started": False,
            "fabricated": False,
        }
    )


def worker_runtime_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "collectors_executed",
        "urls_fetched",
        "raw_payloads_written",
        "live_source_coverage",
        "worker_started",
    ):
        if decision.get(constant) is not False:
            fails.append(f"decision_claimed:{constant}")

    mode = decision.get("runtime_mode")
    if mode not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")

    # The decision-only mode must stay outside the detected vocabulary, or the
    # distinction it exists to draw has quietly disappeared.
    if DECISION_ONLY_RUNTIME_MODES & DETECTED_RUNTIME_MODES:
        fails.append("decision_mode_leaked_into_the_detected_vocabulary")

    # Every flag derived from the mode, never set beside it.
    if decision.get("worker_runtime_available") != (
        mode in WORKER_RUNTIME_AVAILABLE_MODES
    ):
        fails.append("worker_runtime_available_disagrees_with_the_mode")
    if decision.get("production_worker_live") != (mode in PRODUCTION_WORKER_MODES):
        fails.append("production_worker_live_disagrees_with_the_mode")

    # Needing a worker is not having one.
    if decision.get("external_worker_required") and decision.get(
        "background_worker_available"
    ):
        fails.append("worker_required_while_a_worker_is_available")
    if mode in BACKGROUND_WORKER_MODES and not decision.get(
        "background_worker_available"
    ):
        fails.append("worker_mode_without_a_detected_worker")
    if decision.get("background_worker_available") and mode == (
        "external_worker_required"
    ):
        fails.append("worker_available_but_mode_says_required")

    # Gate 101E. An in-process worker needs a persistent backend, and a backend
    # *contract* is not one.
    if decision.get("in_process_worker_possible") != decision.get(
        "persistent_backend_live"
    ):
        fails.append("in_process_possibility_disagrees_with_the_backend")
    if decision.get("backend_runtime_contract_available") and decision.get(
        "in_process_worker_possible"
    ):
        if not decision.get("persistent_backend_live"):
            fails.append("backend_contract_read_as_a_persistent_backend")
    if decision.get("production_worker_live") and not decision.get(
        "persistent_backend_live"
    ):
        fails.append("production_worker_live_without_a_persistent_backend")

    # A dry-run runtime may never be read as a background worker.
    if decision.get("dry_run_worker_available") and mode == "dry_run_in_process":
        if decision.get("background_worker_available"):
            fails.append("dry_run_runtime_read_as_a_background_worker")
        if decision.get("production_worker_live"):
            fails.append("dry_run_runtime_read_as_a_production_worker")

    # A dependency is only required behind a selected broker for an external
    # worker. Requiring one otherwise would be committing to infrastructure on
    # no decision at all.
    if decision.get("dependency_required"):
        if not decision.get("broker_required"):
            fails.append("dependency_required_without_a_broker")
        if not decision.get("broker_selected"):
            fails.append("dependency_required_without_a_selected_broker")

    if decision.get("broker_selected") is not None:
        if decision["broker_selected"] not in BROKER_CANDIDATES:
            fails.append("broker_out_of_vocabulary")

    # The dry-run worker must never be the thing that pulls in a dependency.
    if decision.get("dry_run_worker_requires_dependency") is not False:
        fails.append("dry_run_worker_claimed_a_dependency")

    # A refusal must name itself.
    if not decision.get("production_worker_live") and not decision.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    # The prerequisite ordering must survive. Deploying the backend precedes
    # choosing a broker, and reversing them is how infrastructure gets bought
    # for a service nobody is running.
    actions = [a.get("action") for a in decision.get("next_required_actions") or []]
    if actions != [a for a, _ in NEXT_ACTION_SEQUENCE]:
        fails.append("next_required_actions_reordered_or_dropped")

    return fails
