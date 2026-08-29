"""Dev org header containment (Gate 112E).

A standing record of the one path that sets `app.current_org_id` today, why it is
not safe for production, and what currently keeps it harmless.

## The path

```python
# api/deps_db.py
async def get_org_context_with_db(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    ...
    apply_org_rls_gucs(db, oid, ot)
```

An unauthenticated request header, gated by `NF_DEV_ORG_HEADERS`, which defaults
to `True`. Sixteen route modules depend on it.

## Containment is deployment posture, not the flag

The distinction matters, and stating it precisely is the point of this service.

```text
backend_unit_active     false - the API is not running
backend_loopback_only   true  - binds 127.0.0.1:8000, a test parses the unit file
tunnel_routes_backend   false - the tunnel's ingress origin is the static preview
backend_publicly_exposed false
```

Nothing reaches the API. That is what makes an unauthenticated header harmless
today — not the flag, which is on by default.

**"The door is unlocked and the building is empty" is not a security property.**
It is a true statement about right now, and it stops being true the moment
somebody starts the unit or adds it to the ingress.

## production_safe is false, and cannot become true here

```text
production_safe                    false, always
must_disable_before_customer_auth  true
must_replace_with_auth_claim_guard true
```

`production_safe` is a constant, not a measurement. While an unauthenticated
header can set the org context, the answer is no — regardless of how well
contained the deployment happens to be. An invariant fails any result claiming
otherwise.

Containment can be true and production-safety still false. Those are different
questions and this service answers both, separately.

## Detected, not declared

Unit state, bind address and tunnel ingress are read from the unit file, the
running units and the cloudflared config. A containment claim nobody checked
would be the same kind of assertion this whole campaign refuses.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_dev_org_header_containment_v1"

DEV_HEADER_NAME = "X-NF-Org-Id"
DEV_HEADER_SETTING = "NF_DEV_ORG_HEADERS"
BACKEND_UNIT = "nativeforge-backend.service"
BACKEND_UNIT_FILE = "deploy/systemd/nativeforge-backend.service"
LOOPBACK_BIND = "127.0.0.1"

RESULT_FIELDS: tuple[str, ...] = (
    "dev_header_name",
    "dev_header_enabled_default",
    "backend_publicly_exposed",
    "backend_unit_active",
    "backend_loopback_only",
    "tunnel_routes_backend",
    "production_safe",
    "must_disable_before_customer_auth",
    "must_replace_with_auth_claim_guard",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root(detect_root: Any = None) -> Path:
    return Path(detect_root) if detect_root else Path(__file__).resolve().parents[3]


def _dev_header_default() -> bool:
    """Read from the settings model, not from memory of what it says."""
    try:
        from nativeforge.lib.settings import Settings
    except ImportError:
        return True
    field = Settings.model_fields.get("nf_dev_org_headers")
    return True if field is None else bool(field.default)


def _backend_unit_active() -> bool:
    """Is the API actually running? Asked of systemd."""
    if not shutil.which("systemctl"):
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", BACKEND_UNIT],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() == "active"


def _backend_loopback_only(detect_root: Any = None) -> bool:
    """Does every ExecStart bind loopback? Parsed from the unit file."""
    unit = _repo_root(detect_root) / BACKEND_UNIT_FILE
    if not unit.is_file():
        return False
    exec_lines = [
        line
        for line in unit.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("ExecStart")
    ]
    if not exec_lines:
        return False
    return all(f"--host {LOOPBACK_BIND}" in line for line in exec_lines)


def _tunnel_routes_backend(detect_root: Any = None) -> bool:
    """Does the tunnel's ingress point at the API? Read from its config."""
    candidates = [
        Path.home() / ".cloudflared" / "config.yml",
        _repo_root(detect_root) / "ops" / "cloudflared" / "config.yml",
    ]
    for path in candidates:
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        # The API port. Its absence from every ingress origin is the claim.
        if ":8000" in text:
            return True
    return False


def build_dev_header_containment(*, detect_root: Any = None) -> dict[str, Any]:
    """What contains the dev header today, and why it is still not safe."""
    enabled_default = _dev_header_default()
    unit_active = _backend_unit_active()
    loopback_only = _backend_loopback_only(detect_root)
    tunnel_routes = _tunnel_routes_backend(detect_root)

    publicly_exposed = bool(tunnel_routes or (unit_active and not loopback_only))

    blocked_reasons: list[str] = [
        "unauthenticated_header_can_set_app_current_org_id",
    ]
    if enabled_default:
        blocked_reasons.append(f"{DEV_HEADER_SETTING}_defaults_true")
    if publicly_exposed:
        blocked_reasons.append("backend_reachable_from_outside_loopback")
    if not loopback_only:
        blocked_reasons.append("backend_unit_does_not_bind_loopback_only")

    # Containment is a measurement. Production safety is not - see the module
    # docstring. While an unauthenticated header can set the org context, the
    # answer is no however well contained the deployment happens to be.
    contained_today = bool(not publicly_exposed and loopback_only)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dev_header_name": DEV_HEADER_NAME,
            "dev_header_setting": DEV_HEADER_SETTING,
            "dev_header_enabled_default": enabled_default,
            "backend_unit": BACKEND_UNIT,
            "backend_unit_active": unit_active,
            "backend_loopback_only": loopback_only,
            "tunnel_routes_backend": tunnel_routes,
            "backend_publicly_exposed": publicly_exposed,
            "contained_by_deployment_posture": contained_today,
            "production_safe": False,
            "must_disable_before_customer_auth": True,
            "must_replace_with_auth_claim_guard": True,
            "replacement_service": (
                "nativeforge.services.rls_context_claim_guard_service"
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this records a posture, it changes none of it.
            "dev_header_is_customer_auth": False,
            "header_disabled_by_this_service": False,
            "current_org_id_set": False,
            "customer_auth_live": False,
            "fabricated": False,
        }
    )


def containment_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in RESULT_FIELDS:
        if field not in result:
            fails.append(f"containment_missing_field:{field}")

    for constant in (
        "dev_header_is_customer_auth",
        "header_disabled_by_this_service",
        "current_org_id_set",
        "customer_auth_live",
        "fabricated",
    ):
        if result.get(constant) is not False:
            fails.append(f"containment_claimed:{constant}")

    # The whole point: this can never be safe for production.
    if result.get("production_safe") is not False:
        fails.append("dev_header_claimed_production_safe")

    # The replacement obligations never lapse while the header exists.
    if result.get("must_disable_before_customer_auth") is not True:
        fails.append("disable_obligation_dropped")
    if result.get("must_replace_with_auth_claim_guard") is not True:
        fails.append("replacement_obligation_dropped")

    # Containment must agree with the measurements it summarises.
    expected_contained = bool(
        not result.get("backend_publicly_exposed")
        and result.get("backend_loopback_only")
    )
    if result.get("contained_by_deployment_posture") is not expected_contained:
        fails.append("containment_disagrees_with_the_measurements")

    # Public exposure must be reported when the tunnel routes the backend.
    if result.get("tunnel_routes_backend") and not result.get(
        "backend_publicly_exposed"
    ):
        fails.append("tunnel_routed_backend_not_reported_as_exposed")

    # A refusal must name itself, always - there is no safe configuration.
    if not result.get("blocked_reasons"):
        fails.append("containment_without_a_reason")

    return fails
