"""Backend runtime contract (Gate 101B).

Answers whether NativeForge has a persistent backend runtime. It starts no
process, binds no socket, and makes no request.

## Five modes, and the one that has to be earned

```text
none                         no app, no way to run it
smoke_script_only            the API runs, but only inside a script that
                             backgrounds it and kills it on exit
loopback_backend_contract    a unit template exists, loopback-bound, not installed
loopback_backend_configured  a unit is installed on the host
persistent_backend_live      a long-running process is actually serving
```

`smoke_script_only` is the state Gate 100A found and it deliberately does **not**
count as a backend runtime. A process that exists for eleven seconds inside
`m8_close_gate_staging_smoke.sh` and dies on the `trap` is not something a
scheduler can live in. Treating it as one is how "the API runs" becomes true in a
status report and false in production.

## persistent_backend_live needs proof, and proof means a process

Every other mode is established by reading files. This one is not: a template can
be read, a unit file can be read, but *running* is a property of the host at a
moment in time.

So it requires `process_proof` - an explicit, caller-supplied observation that a
long-running process was seen. Nothing in this gate supplies one, and
`build_backend_runtime_contract` never goes looking for one on its own, because
a service that probed for a listener would be doing I/O to answer a question
about itself.

The absence is the honest answer today, and an invariant fails any result
claiming the mode without the proof.

## Loopback only

`loopback_only` is derived from the host, not declared. Every existing uvicorn
invocation in the repository binds `127.0.0.1`, the unit template does the same,
and an invariant fails any contract whose host is not a loopback address.

This is the one mistake in this gate that would actually matter: a backend bound
to `0.0.0.0` on this host would be reachable through the Cloudflare tunnel that
is already running.

## A backend is not the other things it is often confused for

```text
a backend runtime is NOT   collectors being live
a backend runtime is NOT   a scheduler running
a backend runtime is NOT   customer auth being live
a backend runtime is NOT   production rollout
```

All four are False on every result and none is derived from the runtime mode. A
process that answers HTTP is a process that answers HTTP.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_backend_runtime_contract_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]

RUNTIME_MODES = frozenset(
    {
        "none",
        "smoke_script_only",
        "loopback_backend_contract",
        "loopback_backend_configured",
        "persistent_backend_live",
    }
)

# Modes in which a backend runtime is available in some usable form. A smoke
# script is deliberately excluded: it is a process that exists for the length of
# one script and dies on its trap.
RUNTIME_AVAILABLE_MODES = frozenset(
    {
        "loopback_backend_contract",
        "loopback_backend_configured",
        "persistent_backend_live",
    }
)

# The only mode that means something is actually serving.
PERSISTENT_LIVE_MODES = frozenset({"persistent_backend_live"})

# Modes that require an installed unit on the host.
UNIT_INSTALLED_MODES = frozenset(
    {"loopback_backend_configured", "persistent_backend_live"}
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

# Gate 101C. Deliberately not `/health`: the Vite preview already serves a
# static `/health` from the build stamp, and it answers `ok` whether or not a
# backend exists. Two answers to one question is worse than none.
HEALTHCHECK_PATH = "/backend/health"
READINESS_PATH = "/backend/readiness"

# Addresses that keep the API off the network. The Cloudflare tunnel on this
# host is already running, so a non-loopback bind would be publicly reachable.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

# The unit template Gate 101D writes. Read, never installed.
SYSTEMD_UNIT_RELATIVE_PATH = "deploy/systemd/nativeforge-backend.service"

# The app factory, and the module a unit would point uvicorn at.
APP_MODULE = "nativeforge.main:app"
APP_FACTORY_MODULE = "nativeforge.main"

NEXT_ACTION_SEQUENCE: tuple[tuple[str, str], ...] = (
    (
        "install_backend_systemd_unit",
        "the template at deploy/systemd/ is not installed and not enabled; "
        "installing it is a host decision, not a repository change",
    ),
    (
        "prove_a_long_running_process",
        "persistent_backend_live requires an observed process, not a file that "
        "describes one",
    ),
    (
        "add_a_lifespan_hook",
        "main.py has none, so an in-process scheduler or worker still has "
        "nowhere to attach",
    ),
    (
        "configure_production_object_store",
        "Gate 97's seam, deployed and round-tripped, before any check may run",
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


def detect_app_factory() -> dict[str, Any]:
    """Whether the FastAPI app can be constructed here."""
    import importlib.util

    try:
        spec = importlib.util.find_spec(APP_FACTORY_MODULE)
    except (ImportError, ValueError):
        spec = None
    return _json_safe(
        {
            "available": spec is not None,
            "module": APP_MODULE,
            "detection_method": "importlib.util.find_spec",
        }
    )


def detect_lifespan_hook() -> dict[str, Any]:
    """Whether main.py declares a lifespan or startup hook.

    Parsed rather than imported: importing constructs the app and registers 28
    routers, which is a side effect nobody asked for from a detection call.
    """
    import ast

    path = REPO_ROOT / "src" / "nativeforge" / "main.py"
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

    found: list[str] = []
    for node in ast.walk(tree):
        # `FastAPI(lifespan=...)`
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "lifespan":
                    found.append("lifespan_argument")
        # `@app.on_event("startup")` and friends.
        if isinstance(node, ast.Attribute) and node.attr == "on_event":
            found.append("on_event_decorator")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name in {"lifespan", "startup", "shutdown"}:
                found.append(f"function:{node.name}")

    return _json_safe(
        {
            "available": bool(found),
            "hooks_found": sorted(set(found)),
            "detection_method": "ast parse of main.py",
            "reason": None if found else "no_lifespan_or_startup_hook",
        }
    )


def detect_systemd_unit_template(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Whether a backend unit template is checked into the repository.

    Scoped to the repository. A unit installed on one operator's host is not a
    property of this system, and `systemd_unit_enabled` stays False here because
    this service does not inspect the host - see `build_backend_runtime_contract`.
    """
    root = repo_root or REPO_ROOT
    path = root / SYSTEMD_UNIT_RELATIVE_PATH
    if not path.is_file():
        return _json_safe(
            {
                "available": False,
                "path": SYSTEMD_UNIT_RELATIVE_PATH,
                "detection_method": "repo file scan",
                "binds_loopback_only": False,
                "reason": "template_not_found",
            }
        )

    text = path.read_text(encoding="utf-8")
    exec_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("ExecStart")
    ]
    binds_loopback = bool(exec_lines) and all(
        any(f"--host {host}" in line for host in ("127.0.0.1", "::1"))
        for line in exec_lines
    )

    return _json_safe(
        {
            "available": True,
            "path": SYSTEMD_UNIT_RELATIVE_PATH,
            "detection_method": "repo file scan",
            "binds_loopback_only": binds_loopback,
            "exec_start_lines": exec_lines,
            "installed": False,
            "enabled": False,
            "reason": None,
        }
    )


def detect_smoke_script_startup(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Which scripts start the API ephemerally.

    Their existence is what makes `smoke_script_only` a real state rather than a
    hypothetical one, and why it needed a name that says it does not count.
    """
    root = repo_root or REPO_ROOT
    scripts_dir = root / "scripts"
    found: list[str] = []
    if scripts_dir.is_dir():
        for path in sorted(scripts_dir.glob("*.sh")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "uvicorn" in text and APP_MODULE.split(":")[0] in text:
                found.append(str(path.relative_to(root)))

    return _json_safe(
        {
            "available": bool(found),
            "scripts": found,
            "detection_method": "repo file scan",
            "counts_as_persistent_backend": False,
        }
    )


def build_backend_runtime_contract(
    *,
    repo_root: Path | None = None,
    host: Any = None,
    port: Any = None,
    systemd_unit_installed: bool = False,
    systemd_unit_enabled: bool = False,
    process_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Is there a persistent backend runtime? Nothing is started or probed."""
    root = repo_root or REPO_ROOT

    app_factory = detect_app_factory()
    lifespan = detect_lifespan_hook()
    unit = detect_systemd_unit_template(repo_root=root)
    smoke = detect_smoke_script_startup(repo_root=root)

    resolved_host = str(host).strip() if host is not None else DEFAULT_HOST
    try:
        resolved_port = int(port) if port is not None else DEFAULT_PORT
    except (TypeError, ValueError):
        resolved_port = DEFAULT_PORT
    loopback_only = resolved_host in LOOPBACK_HOSTS

    # A proof is an observation somebody made, and it has to say what it saw.
    proof_valid = bool(
        isinstance(process_proof, dict)
        and process_proof.get("observed") is True
        and process_proof.get("pid")
        and process_proof.get("observed_at")
    )

    # Resolve the mode from the strongest evidence downward. A stronger mode is
    # never reported on weaker evidence.
    if proof_valid and systemd_unit_installed:
        mode = "persistent_backend_live"
    elif systemd_unit_installed:
        mode = "loopback_backend_configured"
    elif unit["available"]:
        mode = "loopback_backend_contract"
    elif smoke["available"]:
        # The API can be started, but only by a script that kills it again.
        mode = "smoke_script_only"
    elif app_factory["available"]:
        mode = "smoke_script_only" if smoke["available"] else "none"
    else:
        mode = "none"

    backend_runtime_available = mode in RUNTIME_AVAILABLE_MODES
    persistent_backend_live = mode in PERSISTENT_LIVE_MODES

    blocked_reasons: list[str] = []
    if not proof_valid:
        blocked_reasons.append("no_long_running_process_proof")
    if not systemd_unit_installed:
        blocked_reasons.append("systemd_unit_not_installed")
    if not systemd_unit_enabled:
        blocked_reasons.append("systemd_unit_not_enabled")
    if not lifespan["available"]:
        blocked_reasons.append("no_lifespan_hook_in_main")
    if not loopback_only:
        blocked_reasons.append(f"host_is_not_loopback:{resolved_host}")
    if smoke["available"] and not systemd_unit_installed:
        blocked_reasons.append("api_started_only_by_smoke_scripts")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "runtime_mode": mode,
            "backend_runtime_available": backend_runtime_available,
            "backend_runtime_contract_available": bool(unit["available"]),
            "persistent_backend_live": persistent_backend_live,
            "loopback_only": loopback_only,
            "host": resolved_host,
            "port": resolved_port,
            "healthcheck_path": HEALTHCHECK_PATH,
            "readiness_path": READINESS_PATH,
            "trust_endpoint_available": persistent_backend_live,
            "lifespan_hook_available": bool(lifespan["available"]),
            # Gate 102D. An in-process scheduler needs both halves: a process to
            # live in, and somewhere in that process to attach. Either alone is
            # not enough, and reporting them only separately would leave the
            # conjunction for a reader to work out.
            "in_process_attach_possible": bool(lifespan["available"])
            and persistent_backend_live,
            "systemd_unit_available": bool(unit["available"]),
            "systemd_unit_installed": bool(systemd_unit_installed),
            "systemd_unit_enabled": bool(systemd_unit_enabled),
            "systemd_unit_binds_loopback_only": bool(unit["binds_loopback_only"]),
            "process_proof_supplied": proof_valid,
            "app_factory_available": bool(app_factory["available"]),
            "smoke_script_startup": smoke,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "next_required_actions": [
                {"action": action, "why": why} for action, why in NEXT_ACTION_SEQUENCE
            ],
            # A backend is a process that answers HTTP. It is none of these.
            "collectors_live": 0,
            "source_monitoring_live": False,
            "scheduler_live": False,
            "customer_auth_live": False,
            "live_fetch_performed": False,
            "live_source_coverage": False,
            "backend_started": False,
            "fabricated": False,
        }
    )


def backend_runtime_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "scheduler_live",
        "customer_auth_live",
        "live_fetch_performed",
        "live_source_coverage",
        "backend_started",
    ):
        if contract.get(constant) is not False:
            fails.append(f"contract_claimed:{constant}")
    if contract.get("collectors_live") != 0:
        fails.append("contract_claimed_live_collectors")

    mode = contract.get("runtime_mode")
    if mode not in RUNTIME_MODES:
        fails.append("runtime_mode_out_of_vocabulary")

    # Every flag derived from the mode, never set beside it.
    if contract.get("backend_runtime_available") != (mode in RUNTIME_AVAILABLE_MODES):
        fails.append("backend_runtime_available_disagrees_with_the_mode")
    if contract.get("persistent_backend_live") != (mode in PERSISTENT_LIVE_MODES):
        fails.append("persistent_backend_live_disagrees_with_the_mode")

    # A smoke script is not a backend runtime.
    if mode == "smoke_script_only":
        if contract.get("backend_runtime_available"):
            fails.append("smoke_script_read_as_a_backend_runtime")
        if contract.get("persistent_backend_live"):
            fails.append("smoke_script_read_as_a_persistent_backend")

    # Live requires proof, and proof is an observation.
    if contract.get("persistent_backend_live"):
        if not contract.get("process_proof_supplied"):
            fails.append("persistent_backend_live_without_process_proof")
        if not contract.get("systemd_unit_installed"):
            fails.append("persistent_backend_live_without_an_installed_unit")
    if mode in UNIT_INSTALLED_MODES and not contract.get("systemd_unit_installed"):
        fails.append("unit_mode_without_an_installed_unit")

    # A template is not an installation, and an installation is not enabled.
    if contract.get("systemd_unit_installed") and not contract.get(
        "systemd_unit_available"
    ):
        fails.append("unit_installed_without_a_template")
    if contract.get("systemd_unit_enabled") and not contract.get(
        "systemd_unit_installed"
    ):
        fails.append("unit_enabled_without_being_installed")

    # Loopback. The single most consequential line in this service.
    if contract.get("loopback_only") != (contract.get("host") in LOOPBACK_HOSTS):
        fails.append("loopback_flag_disagrees_with_the_host")
    if not contract.get("loopback_only"):
        fails.append("backend_host_is_not_loopback")
    if contract.get("systemd_unit_available") and not contract.get(
        "systemd_unit_binds_loopback_only"
    ):
        fails.append("systemd_template_does_not_bind_loopback_only")

    # Gate 102D. Both halves, or neither.
    if contract.get("in_process_attach_possible") != (
        bool(contract.get("lifespan_hook_available"))
        and bool(contract.get("persistent_backend_live"))
    ):
        fails.append("in_process_attach_disagrees_with_its_halves")
    if contract.get("in_process_attach_possible"):
        if not contract.get("lifespan_hook_available"):
            fails.append("in_process_attach_without_a_lifespan_hook")
        if not contract.get("persistent_backend_live"):
            fails.append("in_process_attach_without_a_persistent_backend")

    # The trust surface answers only when something is serving.
    if contract.get("trust_endpoint_available") != contract.get(
        "persistent_backend_live"
    ):
        fails.append("trust_endpoint_disagrees_with_the_backend")

    # The health path must not collide with the stamped static one.
    if contract.get("healthcheck_path") == "/health":
        fails.append("backend_health_collides_with_the_static_stamp")
    if contract.get("healthcheck_path") != HEALTHCHECK_PATH:
        fails.append("healthcheck_path_altered")

    # A refusal must name itself.
    if not contract.get("persistent_backend_live") and not contract.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    actions = [a.get("action") for a in contract.get("next_required_actions") or []]
    if actions != [a for a, _ in NEXT_ACTION_SEQUENCE]:
        fails.append("next_required_actions_reordered_or_dropped")

    return fails
