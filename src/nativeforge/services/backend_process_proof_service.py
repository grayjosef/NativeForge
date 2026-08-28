"""Backend process proof (Gate 102B).

Captures evidence that a persistent backend process is actually running, and
refuses to call it live on anything less.

## Why a proof and not a detection

Every other capability in this campaign is established by reading files: a module
imports, a template exists, a package is installed. Running is different. It is a
property of one host at one moment, and it stops being true the instant the
process exits.

So this service produces a **dated observation** rather than a standing fact. A
proof carries when it was taken, what pid was seen, whether the unit was active,
and whether the health endpoint answered. Absent any one of those, the proof does
not support `persistent_backend_live` - and the missing piece is named.

## Five requirements, each independently disqualifying

```text
observed_at        an undated observation is not evidence of anything
unit_active        systemd says the service is running
pid                a process id was actually seen
loopback host      127.0.0.1 / ::1 only
healthcheck ok     /backend/health answered
```

Failing any one leaves `persistent_backend_live` false with a stated reason.

The healthcheck matters more than it looks. A unit can be `active` while the
application inside it is failing every request - systemd knows the process
exists, not that it works. Requiring the endpoint to answer is the difference
between "something is running" and "the backend is running".

## source_dirty is deliberately not disqualifying

A tree with uncommitted changes blocks *production readiness*. It does not block
the observation that a process exists - the process is running whatever code it
is running, and pretending otherwise would make the proof less accurate rather
than more careful.

So `source_dirty` is recorded, feeds `production_ready: False`, and leaves
`persistent_backend_live` alone. Conflating the two would mean a developer with
an unsaved file could not observe their own running server.

## A proof is not a licence

```text
collectors_live         0
source_monitoring_live  false
scheduler_attached      false
```

A process that answers HTTP is a process that answers HTTP. None of the three is
derived from the proof, all three are held by invariants, and a test asserts them
against a *complete, passing* proof - the state where blurring them would be most
tempting.

## Loopback, checked twice

The host must be loopback and the healthcheck URL must point at it. A proof taken
against a public address would be evidence of exactly the mistake Gate 101 spent
its invariants preventing, and it is refused rather than recorded.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.backend_runtime_contract_service import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HEALTHCHECK_PATH,
    LOOPBACK_HOSTS,
    READINESS_PATH,
)

SCHEMA_VERSION = "nf_backend_process_proof_v1"

DEFAULT_UNIT_NAME = "nativeforge-backend.service"

# What a healthcheck may report. `unknown` is the honest answer when nobody
# looked, and it does not satisfy the requirement.
HEALTHCHECK_STATUSES = frozenset({"ok", "failed", "unreachable", "unknown"})
HEALTHCHECK_SATISFYING = frozenset({"ok"})

READINESS_STATUSES = frozenset({"ok", "failed", "unreachable", "unknown"})

# The five requirements, in reporting order. Each is independently
# disqualifying, and an invariant asserts the set is never trimmed.
PROOF_REQUIREMENT_KEYS: tuple[str, ...] = (
    "observed_at_present",
    "unit_active",
    "pid_present",
    "loopback_host",
    "healthcheck_ok",
)

PROOF_FIELDS: tuple[str, ...] = (
    "proof_id",
    "observed_at",
    "runtime_mode",
    "unit_name",
    "unit_installed",
    "unit_enabled",
    "unit_active",
    "pid",
    "host",
    "port",
    "loopback_only",
    "healthcheck_url",
    "healthcheck_status",
    "readiness_status",
    "git_sha",
    "source_dirty",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _as_pid(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def build_proof_id(
    *, unit_name: Any, host: Any, port: Any, pid: Any, observed_at: Any
) -> str:
    """Deterministic from what was observed. Two identical observations are one."""
    return hashlib.sha256(
        "|".join(
            str(part if part is not None else "")
            for part in (unit_name, host, port, pid, observed_at)
        ).encode("utf-8")
    ).hexdigest()


def build_process_proof(
    *,
    observed_at: Any = None,
    unit_name: Any = None,
    unit_installed: bool = False,
    unit_enabled: bool = False,
    unit_active: bool = False,
    pid: Any = None,
    host: Any = None,
    port: Any = None,
    healthcheck_status: Any = None,
    readiness_status: Any = None,
    git_sha: Any = None,
    source_dirty: Any = None,
) -> dict[str, Any]:
    """One dated observation. This service makes no request and reads no host.

    Every input is supplied by whoever did the observing. That is deliberate: a
    service that went and looked would be doing I/O to answer a question about
    itself, and its answer would change under a test that never asked for a
    network call.
    """
    resolved_unit = str(unit_name).strip() if unit_name else DEFAULT_UNIT_NAME
    resolved_host = str(host).strip() if host is not None else DEFAULT_HOST
    try:
        resolved_port = int(port) if port is not None else DEFAULT_PORT
    except (TypeError, ValueError):
        resolved_port = DEFAULT_PORT

    resolved_pid = _as_pid(pid)
    loopback_only = resolved_host in LOOPBACK_HOSTS
    health = _norm(healthcheck_status, HEALTHCHECK_STATUSES, fallback="unknown")
    readiness = _norm(readiness_status, READINESS_STATUSES, fallback="unknown")

    observed = observed_at if observed_at not in (None, "") else None
    healthcheck_url = f"http://{resolved_host}:{resolved_port}{HEALTHCHECK_PATH}"
    readiness_url = f"http://{resolved_host}:{resolved_port}{READINESS_PATH}"

    # Each requirement derived affirmatively. Nothing is subtracted from a
    # permissive default.
    requirements = {
        "observed_at_present": observed is not None,
        "unit_active": bool(unit_active),
        "pid_present": resolved_pid is not None,
        "loopback_host": loopback_only,
        "healthcheck_ok": health in HEALTHCHECK_SATISFYING,
    }
    missing = sorted(k for k, ok in requirements.items() if not ok)

    blocked_reasons: list[str] = []
    if observed is None:
        blocked_reasons.append("no_observed_at")
    if not unit_active:
        blocked_reasons.append("unit_not_active")
    if resolved_pid is None:
        blocked_reasons.append("no_pid_observed")
    if not loopback_only:
        blocked_reasons.append(f"host_is_not_loopback:{resolved_host}")
    if health not in HEALTHCHECK_SATISFYING:
        blocked_reasons.append(f"healthcheck_not_ok:{health}")
    if unit_active and not unit_installed:
        # systemd cannot run a unit it does not have. Something is being
        # reported that cannot be true.
        blocked_reasons.append("unit_active_without_being_installed")

    persistent_backend_live = not missing and bool(unit_installed)
    if not unit_installed:
        blocked_reasons.append("unit_not_installed")

    runtime_mode = (
        "persistent_backend_live"
        if persistent_backend_live
        else (
            "loopback_backend_configured"
            if unit_installed
            else "loopback_backend_contract"
        )
    )

    # Dirty source blocks production readiness. It does not unmake a process.
    dirty = None if source_dirty is None else bool(source_dirty)
    production_ready = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proof_id": build_proof_id(
                unit_name=resolved_unit,
                host=resolved_host,
                port=resolved_port,
                pid=resolved_pid,
                observed_at=observed,
            ),
            "observed_at": observed,
            "runtime_mode": runtime_mode,
            "unit_name": resolved_unit,
            "unit_installed": bool(unit_installed),
            "unit_enabled": bool(unit_enabled),
            "unit_active": bool(unit_active),
            "pid": resolved_pid,
            "host": resolved_host,
            "port": resolved_port,
            "loopback_only": loopback_only,
            "healthcheck_url": healthcheck_url,
            "readiness_url": readiness_url,
            "healthcheck_status": health,
            "readiness_status": readiness,
            "git_sha": git_sha,
            "source_dirty": dirty,
            "persistent_backend_live": persistent_backend_live,
            "requirements_satisfied": sorted(
                k for k, ok in requirements.items() if ok
            ),
            "requirements_missing": missing,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # A dirty tree blocks production readiness without unmaking the
            # observation that a process exists.
            "production_ready": production_ready,
            # A proof is not a licence.
            "collectors_live": 0,
            "source_monitoring_live": False,
            "scheduler_attached": False,
            "live_fetch_performed": False,
            "live_source_coverage": False,
            "fabricated": False,
        }
    )


def as_runtime_contract_proof(proof: dict[str, Any]) -> dict[str, Any] | None:
    """The shape Gate 101B's `process_proof` argument expects, or None.

    Returns None unless this proof actually supports a live backend, so a weak
    proof cannot be handed to the runtime contract and quietly satisfy it.
    """
    if not proof.get("persistent_backend_live"):
        return None
    return {
        "observed": True,
        "pid": proof.get("pid"),
        "observed_at": proof.get("observed_at"),
    }


def proof_invariant_failures(proof: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if proof.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if proof.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for field in PROOF_FIELDS:
        if field not in proof:
            fails.append(f"proof_missing_field:{field}")

    # A proof is not a licence.
    for constant in (
        "source_monitoring_live",
        "scheduler_attached",
        "live_fetch_performed",
        "live_source_coverage",
    ):
        if proof.get(constant) is not False:
            fails.append(f"proof_claimed:{constant}")
    if proof.get("collectors_live") != 0:
        fails.append("proof_claimed_live_collectors")
    if proof.get("production_ready") is not False:
        fails.append("proof_claimed_production_ready")

    # The five requirements, each independently disqualifying.
    if proof.get("persistent_backend_live"):
        if not proof.get("observed_at"):
            fails.append("live_without_observed_at")
        if not proof.get("unit_active"):
            fails.append("live_without_an_active_unit")
        if not proof.get("unit_installed"):
            fails.append("live_without_an_installed_unit")
        if proof.get("pid") is None:
            fails.append("live_without_a_pid")
        if not proof.get("loopback_only"):
            fails.append("live_without_a_loopback_host")
        if proof.get("healthcheck_status") not in HEALTHCHECK_SATISFYING:
            fails.append("live_without_a_passing_healthcheck")
        if proof.get("requirements_missing"):
            fails.append("live_with_missing_requirements")

    # Vocabularies.
    if proof.get("healthcheck_status") not in HEALTHCHECK_STATUSES:
        fails.append("healthcheck_status_out_of_vocabulary")
    if proof.get("readiness_status") not in READINESS_STATUSES:
        fails.append("readiness_status_out_of_vocabulary")

    # Loopback, derived and cross-checked against the URL that was called.
    if proof.get("loopback_only") != (proof.get("host") in LOOPBACK_HOSTS):
        fails.append("loopback_flag_disagrees_with_the_host")
    url = str(proof.get("healthcheck_url") or "")
    if proof.get("loopback_only") and not any(
        f"//{host}:" in url for host in LOOPBACK_HOSTS
    ):
        fails.append("healthcheck_url_does_not_target_the_loopback_host")
    if url and not url.endswith(HEALTHCHECK_PATH):
        fails.append("healthcheck_url_does_not_target_the_backend_health_path")

    # systemd cannot run a unit it does not have.
    if proof.get("unit_active") and not proof.get("unit_installed"):
        if "unit_active_without_being_installed" not in (
            proof.get("blocked_reasons") or []
        ):
            fails.append("active_without_installed_not_flagged")

    # A pid, if present, is a real one.
    pid = proof.get("pid")
    if pid is not None and (
        not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0
    ):
        fails.append("pid_is_not_a_positive_integer")

    # Every requirement accounted for exactly once.
    satisfied = set(proof.get("requirements_satisfied") or [])
    missing = set(proof.get("requirements_missing") or [])
    if satisfied & missing:
        fails.append("requirement_both_satisfied_and_missing")
    if satisfied | missing != set(PROOF_REQUIREMENT_KEYS):
        fails.append("requirement_dropped_from_the_checklist")

    # A refusal must name itself.
    if not proof.get("persistent_backend_live") and not proof.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    # Identity reproducible from what was observed.
    expected = build_proof_id(
        unit_name=proof.get("unit_name"),
        host=proof.get("host"),
        port=proof.get("port"),
        pid=proof.get("pid"),
        observed_at=proof.get("observed_at"),
    )
    if proof.get("proof_id") != expected:
        fails.append("proof_id_not_derivable_from_the_observation")

    return fails
