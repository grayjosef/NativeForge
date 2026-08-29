"""Dev org header shutdown readiness (Gate 115E).

What must happen before `X-NF-Org-Id` can be disabled, and why it cannot be
disabled today.

## Two different questions

```text
safe_to_disable_now                 would turning it off leave a working system?
must_disable_before_production_auth  may it survive into production auth?
```

The answers are **no** and **yes**, and they are not in tension. The header is
load-bearing: sixteen route modules depend on it, and no authenticated
replacement exists, so removing it now breaks the application without making
anything safer. It must still never reach production auth, because an
unauthenticated header that sets `app.current_org_id` is a way to read another
Tribe's data by typing a UUID.

`must_disable_before_production_auth` is `True` unconditionally and an invariant
enforces it. That is not the kind of hard-coded constant this campaign keeps
removing - it is a boundary that has no true-branch by design, and the invariant
is there so nobody quietly gives it one.

## What the header actually is

```text
deps_db.get_org_context_with_db
  requires header X-NF-Org-Id
  refuses entirely unless settings.nf_dev_org_headers is true
  parses the value as a UUID, looks it up in `organizations`
  then calls apply_org_rls_gucs(session, org_id, org_type)
```

It is UUID-validated and existence-checked, which stops a label reaching the
RLS context - Gate 114 verified that no label can. What it does not do is
establish *who is asking*. Any caller who reaches the port and knows an
organization's UUID gets that organization's RLS context.

Gate 112 recorded that this is contained by deployment posture - loopback-only
backend behind Cloudflare Access - and that containment is not safety.
**Cloudflare Access is not customer app auth.**

## Detection avoids the containment service on purpose

`dev_org_header_containment_service` shells out to `systemctl`, so its output
depends on the machine it ran on. Gate 114 avoided depending on it for anything
that reaches a committed artifact, and this service does the same: the header
flag is read from settings and the route dependency is counted by reading the
`api/` package.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_dev_org_header_shutdown_readiness_v1"

DEV_HEADER_NAME = "X-NF-Org-Id"
DEV_HEADER_SETTING = "nf_dev_org_headers"

# The dependency names that mean a route module obtains its organization from
# the dev header path.
ORG_CONTEXT_DEPENDENCIES: tuple[str, ...] = (
    "get_org_context_with_db",
    "require_demo_org_db",
)

# Gate 116: matched as a FastAPI dependency rather than as a substring.
#
# The first version searched for the bare name, which counted any module that
# mentioned it - including `capability_guard.py`, whose only reference is a
# docstring describing the header, and `api/auth.py`, whose docstring explains
# why it deliberately does *not* use it. A module documenting its refusal was
# being counted as a dependant.
#
# `Depends(name)` is what actually wires the dependency into a route.
DEPENDENCY_USE_PATTERN = r"Depends\(\s*{name}\s*\)"

# What an authenticated replacement would have to provide. Each is detected by
# import; naming them individually means a report can say which is missing.
REPLACEMENT_COMPONENT_MODULES: dict[str, str] = {
    "organization_id_resolution_available": (
        "nativeforge.services.oidc_organization_id_resolution_service"
    ),
    "membership_verification_available": (
        "nativeforge.services.customer_org_membership_verification_service"
    ),
    "rls_claim_guard_available": (
        "nativeforge.services.rls_context_claim_guard_service"
    ),
    "role_mapping_available": (
        "nativeforge.services.customer_auth_role_mapping_service"
    ),
}

READINESS_FIELDS: tuple[str, ...] = (
    "auth_replacement_routes_available",
    "dev_header_enabled_default",
    "dev_header_used_by_routes",
    "auth_replacement_available",
    "rls_claim_guard_available",
    "organization_id_resolution_available",
    "membership_verification_available",
    "safe_to_disable_now",
    "must_disable_before_production_auth",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def detect_dev_header_route_usage(api_dir: Path | None = None) -> dict[str, Any]:
    """Which route modules obtain an organization through the dev header path.

    The directory is injectable so a test can point at one where nothing uses
    it and observe the zero branch - otherwise `dev_header_used_by_routes: 0`
    would be unreachable in this repository.
    """
    if api_dir is None:
        api_dir = Path(__file__).resolve().parents[3] / "src/nativeforge/api"

    modules: list[str] = []
    mentions_only: list[str] = []
    if api_dir.is_dir():
        for path in sorted(api_dir.glob("*.py")):
            body = path.read_text(encoding="utf-8", errors="replace")
            uses = any(
                re.search(DEPENDENCY_USE_PATTERN.format(name=dep), body)
                for dep in ORG_CONTEXT_DEPENDENCIES
            )
            if uses:
                modules.append(path.name)
            elif any(dep in body for dep in ORG_CONTEXT_DEPENDENCIES):
                # Named so the difference between using and discussing the
                # header is visible rather than silently dropped.
                mentions_only.append(path.name)

    return {
        "module_count": len(modules),
        "modules": modules,
        "mention_only_module_count": len(mentions_only),
        "mention_only_modules": mentions_only,
    }


def _dev_header_enabled() -> bool:
    try:
        from nativeforge.lib.settings import get_settings

        return bool(getattr(get_settings(), DEV_HEADER_SETTING))
    except Exception:  # pragma: no cover - settings always load here
        # Unknown means enabled. An unreadable setting is not permission.
        return True


def build_dev_header_shutdown_readiness(
    *,
    api_dir: Path | None = None,
    dev_header_enabled: bool | None = None,
    auth_route_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What must happen before the dev header can go. Deny by default."""
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )

    usage = detect_dev_header_route_usage(api_dir)
    enabled = (
        _dev_header_enabled()
        if dev_header_enabled is None
        else bool(dev_header_enabled)
    )
    routes = (
        auth_route_readiness
        if auth_route_readiness is not None
        else build_route_readiness()
    )

    components = {
        key: _module_importable(module)
        for key, module in REPLACEMENT_COMPONENT_MODULES.items()
    }

    blocked_reasons: list[str] = []

    # Gate 116 added five auth routes, which makes a fact that was previously
    # meaningless worth reporting separately: the routes now *exist*.
    #
    #   auth_replacement_routes_available   the endpoints are registered
    #   replacement_route_available         one of them can actually
    #                                       authenticate somebody
    #
    # The first is true as of Gate 116. The second is not, and will not be until
    # a route refuses an unauthenticated caller. Reporting only the first would
    # let "the auth routes are in" read as "the dev header can go".
    auth_replacement_routes_available = all(
        bool(routes.get(field))
        for field in (
            "login_route_available",
            "logout_route_available",
            "callback_route_available",
            "session_route_available",
            "current_user_route_available",
        )
    )
    replacement_route_available = bool(routes.get("ready_for_live_login"))

    # A replacement is not a set of contracts, and it is not a set of endpoints
    # either. It is a route a customer can actually authenticate through, plus
    # the contracts behind it.
    auth_replacement_available = bool(
        replacement_route_available and all(components.values())
    )

    if not auth_replacement_routes_available:
        blocked_reasons.append("auth_replacement_routes_are_not_registered")
    elif not replacement_route_available:
        # The state Gate 116 leaves the system in, named rather than silent.
        blocked_reasons.append(
            "auth_routes_exist_but_none_of_them_authenticates_anybody_yet"
        )

    if not replacement_route_available:
        blocked_reasons.append(
            "no_authenticated_route_can_supply_an_organization_id_yet"
        )
    for key, present in sorted(components.items()):
        if not present:
            blocked_reasons.append(f"replacement_component_absent:{key}")

    if usage["module_count"]:
        blocked_reasons.append(
            f"dev_header_is_load_bearing_for_{usage['module_count']}_route_modules"
        )

    if enabled:
        blocked_reasons.append("dev_header_is_enabled_by_default_in_settings")

    # Disabling now would break the application without making anything safer.
    safe_to_disable_now = bool(
        auth_replacement_available and not usage["module_count"]
    )

    # No true branch by design, and an invariant keeps it that way.
    must_disable_before_production_auth = True

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dev_header_name": DEV_HEADER_NAME,
            "dev_header_setting": DEV_HEADER_SETTING,
            "dev_header_enabled_default": enabled,
            "dev_header_used_by_routes": usage["module_count"],
            "dev_header_route_modules": usage["modules"],
            # Modules that name the dependency without wiring it into a route -
            # docstrings describing the header, including api/auth.py's
            # explanation of why it does not use one.
            "dev_header_mention_only_modules": usage["mention_only_modules"],
            "auth_replacement_available": auth_replacement_available,
            "auth_replacement_routes_available": auth_replacement_routes_available,
            "replacement_route_available": replacement_route_available,
            **components,
            "safe_to_disable_now": safe_to_disable_now,
            "must_disable_before_production_auth": (
                must_disable_before_production_auth
            ),
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants, each naming something the header is not.
            "dev_header_is_customer_auth": False,
            "dev_header_is_production_safe": False,
            "cloudflare_access_is_customer_auth": False,
            "header_disabled_by_this_service": False,
            "current_org_id_set": False,
            "fabricated": False,
        }
    )


def shutdown_readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in READINESS_FIELDS:
        if field not in readiness:
            fails.append(f"shutdown_readiness_missing_field:{field}")

    for constant in (
        "dev_header_is_customer_auth",
        "dev_header_is_production_safe",
        "cloudflare_access_is_customer_auth",
        "header_disabled_by_this_service",
        "current_org_id_set",
        "fabricated",
    ):
        if readiness.get(constant) is not False:
            fails.append(f"shutdown_readiness_claimed:{constant}")

    # The boundary with no true branch.
    if readiness.get("must_disable_before_production_auth") is not True:
        fails.append("dev_header_permitted_to_survive_into_production_auth")

    # Gate 116: routes existing must never, on its own, permit the header to
    # go. This is the invariant that keeps "the auth routes are in" from
    # reading as "the dev header can be turned off".
    if readiness.get("safe_to_disable_now") and not readiness.get(
        "replacement_route_available"
    ):
        fails.append("safe_to_disable_because_routes_exist_but_none_authenticates")

    # Safe to disable requires a replacement that actually exists.
    if readiness.get("safe_to_disable_now"):
        if not readiness.get("auth_replacement_available"):
            fails.append("safe_to_disable_without_an_auth_replacement")
        if readiness.get("dev_header_used_by_routes"):
            fails.append("safe_to_disable_while_routes_still_depend_on_it")

    # A replacement is a route plus the contracts, not the contracts alone.
    if readiness.get("auth_replacement_available"):
        if not readiness.get("replacement_route_available"):
            fails.append("auth_replacement_claimed_without_an_authenticated_route")
        if not readiness.get("auth_replacement_routes_available"):
            fails.append("auth_replacement_claimed_without_the_routes_existing")
        for key in REPLACEMENT_COMPONENT_MODULES:
            if not readiness.get(key):
                fails.append(f"auth_replacement_claimed_without:{key}")

    # A refusal must name itself.
    if not readiness.get("safe_to_disable_now") and not readiness.get(
        "blocked_reasons"
    ):
        fails.append("shutdown_refused_without_a_reason")

    return fails
