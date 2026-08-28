"""Backend health and readiness contracts (Gate 101C).

Two questions that are routinely collapsed into one, kept apart:

```text
/backend/health      is this process up, and which code is it running?
/backend/readiness   what is this system allowed to do?
```

A process can be perfectly healthy and allowed to do almost nothing, which is
exactly the situation today. Answering both with one endpoint is how "the
service is green" comes to mean "we are in production".

## Why not /health

The Vite preview on :5175 already serves a **static** `/health` written by
`build_frontend_stamped.sh`. It answers `ok` whether or not a backend exists, and
it is up right now. A monitor pointed at it would report the system healthy with
no backend running at all.

So the backend surface is `/backend/health`, and an invariant in the runtime
contract fails if it is ever moved to `/health`. One question, one answer.

## Health says which code, not whether it is good code

```text
status                 ok
service                nativeforge
git_sha                the commit this process is running
source_dirty           whether the tree had uncommitted changes
backend_runtime_mode   loopback_backend_contract
timestamp              when this answer was produced
```

`git_sha` and `source_dirty` are the same two facts the frontend build stamp
carries, which is what makes a mismatch between the two surfaces detectable: if
the SPA reports one sha and the backend another, somebody deployed half a system.

Health deliberately reports **no** readiness. It carries `production_ready:
False` as a constant so a caller who reads only this endpoint cannot infer
otherwise, and an invariant fails any health record claiming production
readiness.

## Readiness is a list of what is not permitted

```text
backend_runtime_available              true   (a contract, not a process)
persistent_backend_live                false
database_ready                         detected
production_raw_payload_store_available false
scheduler_runtime                      dry_run_in_process
background_worker_available            false
source_monitoring_live                 false
collectors_live                        0
```

Every value is bridged from the service that owns it - Gate 98E for the
scheduler, Gate 96/97 for the payload store, Gate 101B for the backend - rather
than restated here. A readiness endpoint that maintained its own copy of these
facts would drift from them, and the drift would always be in the optimistic
direction, because nobody notices a green light that should be red.

## No secrets, ever

Neither contract carries a credential, a connection string, or an environment
value. `database_ready` is a boolean about reachability, never a DSN. An
invariant scans both records for credential-shaped keys.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from nativeforge.services.backend_runtime_contract_service import (
    HEALTHCHECK_PATH,
    READINESS_PATH,
    build_backend_runtime_contract,
)

SCHEMA_VERSION = "nf_backend_health_readiness_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]

SERVICE_NAME = "nativeforge"
HEALTH_STATUSES = frozenset({"ok", "degraded", "unknown"})

UNKNOWN_SHA = "unknown"

# Fields every health response carries.
HEALTH_FIELDS: tuple[str, ...] = (
    "status",
    "service",
    "git_sha",
    "source_dirty",
    "backend_runtime_mode",
    "timestamp",
)

# Fields every readiness response carries.
READINESS_FIELDS: tuple[str, ...] = (
    "backend_runtime_available",
    "persistent_backend_live",
    "database_ready",
    "production_raw_payload_store_available",
    "scheduler_runtime",
    "background_worker_available",
    "source_monitoring_live",
    "collectors_live",
    "blocked_reasons",
)

# Key fragments that would mean a credential had reached a response body.
# Checked against key names on both records.
CREDENTIAL_KEY_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "authorization",
    "dsn",
    "connection_string",
    "database_url",
    "private_key",
    "access_key",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_git_identity(*, repo_root: Path | None = None) -> dict[str, Any]:
    """The commit this process is running, and whether the tree was dirty.

    The same two facts `build_frontend_stamped.sh` writes into the SPA, so a
    mismatch between the two surfaces is detectable. Any failure - no git, not a
    repository, a timeout - reports `unknown` rather than raising: a health
    endpoint that 500s because git is missing is worse than one that admits it
    does not know which code it is running.
    """
    root = repo_root or REPO_ROOT

    def _run(args: list[str]) -> str | None:
        try:
            proc = subprocess.run(
                args,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()

    sha = _run(["git", "rev-parse", "HEAD"])
    # Tracked changes only. `--porcelain` alone counts untracked files, and this
    # repository carries hundreds of untracked smoke artifacts - which made
    # `source_dirty` permanently true on this host.
    #
    # A flag that is always true carries no information. This one is paired with
    # `git_sha` to answer "does the running code differ from that commit", and
    # an untracked scratch file does not change the running code. Tracked
    # modifications do, so those are what it reports.
    status = _run(["git", "status", "--porcelain", "--untracked-files=no"])

    return _json_safe(
        {
            "git_sha": sha or UNKNOWN_SHA,
            # `None` means we could not tell. Reporting `False` for "we could
            # not check" would be claiming a clean tree we never looked at.
            "source_dirty": None if status is None else bool(status.strip()),
            "detection_method": "git rev-parse + git status --porcelain",
        }
    )


def build_backend_health(
    *,
    repo_root: Path | None = None,
    now: Any = None,
    git_sha: Any = None,
    source_dirty: Any = None,
    runtime_mode: Any = None,
) -> dict[str, Any]:
    """Is this process up, and which code is it running?

    `now`, `git_sha` and `source_dirty` are injectable so the artifact can be
    generated deterministically. Left out, they are detected.
    """
    root = repo_root or REPO_ROOT

    if git_sha is None or source_dirty is None:
        identity = detect_git_identity(repo_root=root)
        git_sha = identity["git_sha"] if git_sha is None else git_sha
        source_dirty = (
            identity["source_dirty"] if source_dirty is None else source_dirty
        )

    if runtime_mode is None:
        runtime_mode = build_backend_runtime_contract(repo_root=root)["runtime_mode"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            # A process that can answer is up. That is the whole claim.
            "status": "ok",
            "service": SERVICE_NAME,
            "git_sha": git_sha,
            "source_dirty": source_dirty,
            "backend_runtime_mode": runtime_mode,
            "timestamp": now,
            "health_path": HEALTHCHECK_PATH,
            # Health is not readiness, and a caller reading only this endpoint
            # must not be able to infer otherwise.
            "production_ready": False,
            "readiness_path": READINESS_PATH,
            "fabricated": False,
        }
    )


def _detect_database_ready() -> bool:
    """Whether the database is configured and reachable.

    Reachability is a genuine property of the moment, so this one does connect.
    Any failure is `False` - an unreachable database is not a ready one, and a
    health surface that raised on a dead database would take the whole endpoint
    down with it.
    """
    try:
        from sqlalchemy import text

        from nativeforge.db.session import SessionLocal
    except ImportError:
        return False
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any failure means not ready
        return False


def build_backend_readiness(
    *,
    repo_root: Path | None = None,
    database_ready: bool | None = None,
) -> dict[str, Any]:
    """What is this system allowed to do? Every value bridged from its owner."""
    root = repo_root or REPO_ROOT

    backend = build_backend_runtime_contract(repo_root=root)

    try:
        from nativeforge.services.source_scheduler_readiness_service import (
            build_scheduler_readiness,
        )

        scheduler = build_scheduler_readiness(repo_root=root)
    except ImportError:
        scheduler = {}

    resolved_db = (
        _detect_database_ready() if database_ready is None else bool(database_ready)
    )

    blocked_reasons: list[str] = []
    if not backend["persistent_backend_live"]:
        blocked_reasons.append("persistent_backend_not_live")
    if not resolved_db:
        blocked_reasons.append("database_not_ready")
    if not scheduler.get("production_raw_payload_store_available"):
        blocked_reasons.append("production_raw_payload_store_unavailable")
    if not scheduler.get("background_worker_available"):
        blocked_reasons.append("background_worker_unavailable")
    if not scheduler.get("ready_to_start_monitoring"):
        blocked_reasons.append("not_ready_to_start_monitoring")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "backend_runtime_available": bool(backend["backend_runtime_available"]),
            "persistent_backend_live": bool(backend["persistent_backend_live"]),
            "database_ready": resolved_db,
            "production_raw_payload_store_available": bool(
                scheduler.get("production_raw_payload_store_available")
            ),
            "scheduler_runtime": scheduler.get("runtime_mode", "none"),
            "background_worker_available": bool(
                scheduler.get("background_worker_available")
            ),
            "source_monitoring_live": bool(scheduler.get("source_monitoring_live")),
            "collectors_live": 0,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # The boundaries this endpoint must never soften.
            "ready_to_start_monitoring": bool(
                scheduler.get("ready_to_start_monitoring")
            ),
            "customer_auth_live": False,
            "production_rollout": False,
            "controlled_customer_pilot": False,
            "live_source_coverage": False,
            "live_fetch_performed": False,
            "readiness_path": READINESS_PATH,
            "fabricated": False,
        }
    )


def _credential_key_failures(record: dict[str, Any], label: str) -> list[str]:
    fails: list[str] = []
    for key in record:
        lowered = str(key).lower()
        for fragment in CREDENTIAL_KEY_FRAGMENTS:
            if fragment in lowered:
                fails.append(f"{label}_carries_a_credential_key:{key}")
    return fails


def health_invariant_failures(health: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if health.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if health.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for field in HEALTH_FIELDS:
        if field not in health:
            fails.append(f"health_missing_field:{field}")

    if health.get("status") not in HEALTH_STATUSES:
        fails.append("health_status_out_of_vocabulary")
    if health.get("service") != SERVICE_NAME:
        fails.append("health_service_name_altered")

    # Health must never be read as readiness.
    if health.get("production_ready") is not False:
        fails.append("health_claimed_production_ready")

    # It must not collide with the stamped static surface.
    if health.get("health_path") == "/health":
        fails.append("backend_health_collides_with_the_static_stamp")
    if health.get("health_path") != HEALTHCHECK_PATH:
        fails.append("health_path_altered")

    # A sha we could not read is `unknown`, never a plausible-looking value.
    sha = health.get("git_sha")
    if not isinstance(sha, str) or not sha:
        fails.append("health_git_sha_missing")
    elif sha != UNKNOWN_SHA:
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha.lower()):
            fails.append("health_git_sha_is_not_a_commit")

    dirty = health.get("source_dirty")
    if dirty is not None and not isinstance(dirty, bool):
        fails.append("health_source_dirty_not_a_boolean")

    fails.extend(_credential_key_failures(health, "health"))

    return fails


def readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if readiness.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for field in READINESS_FIELDS:
        if field not in readiness:
            fails.append(f"readiness_missing_field:{field}")

    # The boundaries this gate may not soften.
    for constant in (
        "customer_auth_live",
        "production_rollout",
        "controlled_customer_pilot",
        "live_source_coverage",
        "live_fetch_performed",
    ):
        if readiness.get(constant) is not False:
            fails.append(f"readiness_claimed:{constant}")
    if readiness.get("collectors_live") != 0:
        fails.append("readiness_claimed_live_collectors")

    # A backend runtime is not a licence for anything downstream.
    if readiness.get("backend_runtime_available"):
        if readiness.get("collectors_live"):
            fails.append("backend_runtime_read_as_live_collectors")
        if readiness.get("customer_auth_live"):
            fails.append("backend_runtime_read_as_customer_auth")

    # Monitoring needs a worker, and readiness needs everything.
    if readiness.get("source_monitoring_live") and not readiness.get(
        "background_worker_available"
    ):
        fails.append("monitoring_live_without_a_background_worker")
    if readiness.get("ready_to_start_monitoring") and readiness.get("blocked_reasons"):
        fails.append("ready_to_start_monitoring_with_blocked_reasons")

    # A refusal must name itself.
    if not readiness.get("persistent_backend_live") and not readiness.get(
        "blocked_reasons"
    ):
        fails.append("refusal_without_a_reason")

    fails.extend(_credential_key_failures(readiness, "readiness"))

    return fails
