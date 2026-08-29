"""Customer auth route readiness (Gate 115C).

Does NativeForge have the backend routes a customer login flow needs, and do
those routes enforce anything?

## Two questions, and the second is the one that matters

```text
route_available    is there an endpoint at all?
route_enforced     does reaching it require anything?
```

A route that exists and enforces nothing is worse than no route, because it
looks like progress. Gate 115A measured the current state against the running
application's OpenAPI schema:

```text
routes in the schema        178
auth-shaped routes          NONE
securitySchemes declared    NONE
routes declaring security   NONE
```

Not one of the 178 endpoints requires a credential.

## Two things that are not customer app auth

**Cloudflare Access.** It gates who reaches the tunnel. It establishes no
NativeForge principal, no organization and no role, and a route behind it is
still a route with no credential requirement. It is reported here as a separate
field precisely so it can never be counted as one.

**The frontend preview.** A served page is not a backend session. The preview on
port 5175 renders whatever the build produced and authenticates nobody.

## Detection is by route table, not by grep

The routes are read from the application's own OpenAPI schema. A service that
grepped for the string "login" would report a route that a comment mentions,
and would miss one mounted under an unexpected prefix.

`/docs/oauth2-redirect` exists in the raw route list and is excluded
deliberately: it is FastAPI's Swagger UI helper, not a NativeForge callback.
Counting it would have made `callback_route_available` true today.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_route_readiness_v1"

# Routes FastAPI mounts for its own documentation UI. None of them is a
# NativeForge auth route, and `/docs/oauth2-redirect` would otherwise be matched
# by the callback pattern below.
FRAMEWORK_ROUTE_PREFIXES: tuple[str, ...] = ("/docs", "/redoc", "/openapi.json")

# What each required route looks like. Patterns rather than exact paths, because
# a real implementation may mount them under a version prefix.
ROUTE_PATTERNS: dict[str, str] = {
    "login_route_available": r"/(auth/)?login\b",
    "logout_route_available": r"/(auth/)?logout\b",
    "callback_route_available": r"/(auth/)?callback\b",
    "session_route_available": r"/(auth/)?session\b",
    "current_user_route_available": r"/(auth/)?(me|current[-_]user)\b",
}

READINESS_FIELDS: tuple[str, ...] = (
    "login_route_available",
    "logout_route_available",
    "callback_route_available",
    "session_route_available",
    "current_user_route_available",
    "route_auth_enforced",
    "route_org_resolution_enforced",
    "route_role_mapping_enforced",
    "route_session_cookie_policy_enforced",
    "ready_for_live_login",
    "blocked_reasons",
)

# Every route above must exist before a login flow can run.
REQUIRED_ROUTES: tuple[str, ...] = (
    "login_route_available",
    "logout_route_available",
    "callback_route_available",
    "session_route_available",
    "current_user_route_available",
)

REQUIRED_ENFORCEMENT: tuple[str, ...] = (
    "route_auth_enforced",
    "route_org_resolution_enforced",
    "route_role_mapping_enforced",
    "route_session_cookie_policy_enforced",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_route_surface(
    *, openapi: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Read the application's own route table.

    The schema is injectable so a test can supply one describing an application
    that *does* have auth routes - without that, every `available: True` branch
    would be unreachable and this service would be a constant.
    """
    if openapi is None:
        openapi = _load_openapi()

    paths = sorted(openapi.get("paths", {}) or {})
    app_paths = [
        p for p in paths if not p.startswith(FRAMEWORK_ROUTE_PREFIXES)
    ]

    matched: dict[str, list[str]] = {}
    for field, pattern in ROUTE_PATTERNS.items():
        matched[field] = [
            p for p in app_paths if re.search(pattern, p, re.IGNORECASE)
        ]

    schemes = list((openapi.get("components", {}) or {}).get("securitySchemes", {}))
    secured_paths = [
        path
        for path, ops in (openapi.get("paths", {}) or {}).items()
        if isinstance(ops, dict)
        and any(isinstance(op, dict) and "security" in op for op in ops.values())
    ]

    return {
        "route_count": len(paths),
        "application_route_count": len(app_paths),
        "matched_routes": matched,
        "security_schemes": schemes,
        "globally_secured": bool(openapi.get("security")),
        "secured_route_count": len(secured_paths),
    }


def _load_openapi() -> dict[str, Any]:
    """The running application's schema. No server is started and no port bound."""
    try:
        from nativeforge.main import app

        return app.openapi()
    except Exception:  # pragma: no cover - the app imports in this repository
        # Unknown means absent. An unreadable route table is not evidence of
        # routes.
        return {"paths": {}, "components": {}}


def build_route_readiness(
    *,
    openapi: dict[str, Any] | None = None,
    cloudflare_access_in_front: bool = True,
) -> dict[str, Any]:
    """Which login routes exist, and whether any of them enforces anything."""
    surface = detect_route_surface(openapi=openapi)
    matched = surface["matched_routes"]

    routes = {field: bool(matched[field]) for field in ROUTE_PATTERNS}

    blocked_reasons: list[str] = []
    for field in REQUIRED_ROUTES:
        if not routes[field]:
            blocked_reasons.append(f"route_absent:{field}")

    # Enforcement is a property of the route table, not of the routes existing.
    # A securityScheme is the weakest possible evidence that anything is
    # required, and there is none.
    has_security = bool(surface["security_schemes"]) and bool(
        surface["globally_secured"] or surface["secured_route_count"]
    )

    route_auth_enforced = bool(has_security and routes["session_route_available"])

    # Organization resolution and role mapping are enforced at a route only if
    # something authenticates first. Gate 112's contract existing is not the
    # same as a route applying it, and this service will not conflate them.
    route_org_resolution_enforced = bool(
        route_auth_enforced and routes["current_user_route_available"]
    )
    route_role_mapping_enforced = route_org_resolution_enforced
    route_session_cookie_policy_enforced = bool(
        has_security and routes["session_route_available"]
    )

    for field, enforced in (
        ("route_auth_enforced", route_auth_enforced),
        ("route_org_resolution_enforced", route_org_resolution_enforced),
        ("route_role_mapping_enforced", route_role_mapping_enforced),
        (
            "route_session_cookie_policy_enforced",
            route_session_cookie_policy_enforced,
        ),
    ):
        if not enforced:
            blocked_reasons.append(f"enforcement_absent:{field}")

    if not surface["security_schemes"]:
        blocked_reasons.append("no_security_scheme_is_declared_anywhere")

    if cloudflare_access_in_front:
        # Stated as a refusal rather than omitted, so nobody reads the absence
        # as "edge protection covers this".
        blocked_reasons.append("cloudflare_access_is_not_customer_app_auth")

    ready_for_live_login = bool(
        all(routes[field] for field in REQUIRED_ROUTES)
        and route_auth_enforced
        and route_org_resolution_enforced
        and route_role_mapping_enforced
        and route_session_cookie_policy_enforced
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **routes,
            "route_auth_enforced": route_auth_enforced,
            "route_org_resolution_enforced": route_org_resolution_enforced,
            "route_role_mapping_enforced": route_role_mapping_enforced,
            "route_session_cookie_policy_enforced": (
                route_session_cookie_policy_enforced
            ),
            "ready_for_live_login": ready_for_live_login,
            "application_route_count": surface["application_route_count"],
            "security_schemes_declared": surface["security_schemes"],
            "secured_route_count": surface["secured_route_count"],
            "matched_routes": matched,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants, each naming a thing that is not customer app auth.
            "cloudflare_access_is_customer_auth": False,
            "frontend_preview_is_backend_login": False,
            "dev_header_is_customer_auth": False,
            "real_sessions_created": False,
            "fabricated": False,
        }
    )


def route_readiness_invariant_failures(readiness: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if readiness.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in READINESS_FIELDS:
        if field not in readiness:
            fails.append(f"route_readiness_missing_field:{field}")

    for constant in (
        "cloudflare_access_is_customer_auth",
        "frontend_preview_is_backend_login",
        "dev_header_is_customer_auth",
        "real_sessions_created",
        "fabricated",
    ):
        if readiness.get(constant) is not False:
            fails.append(f"route_readiness_claimed:{constant}")

    # Existence is not enforcement. This is the whole point of the service.
    if readiness.get("route_auth_enforced") and not readiness.get(
        "security_schemes_declared"
    ):
        fails.append("auth_reported_enforced_without_a_security_scheme")

    if readiness.get("route_org_resolution_enforced") and not readiness.get(
        "route_auth_enforced"
    ):
        fails.append("org_resolution_enforced_without_auth_enforced")

    if readiness.get("route_role_mapping_enforced") and not readiness.get(
        "route_auth_enforced"
    ):
        fails.append("role_mapping_enforced_without_auth_enforced")

    if readiness.get("ready_for_live_login"):
        for field in REQUIRED_ROUTES:
            if not readiness.get(field):
                fails.append(f"ready_for_live_login_without:{field}")
        for field in REQUIRED_ENFORCEMENT:
            if not readiness.get(field):
                fails.append(f"ready_for_live_login_without:{field}")

    # A refusal must name itself.
    if not readiness.get("ready_for_live_login") and not readiness.get(
        "blocked_reasons"
    ):
        fails.append("login_refused_without_a_reason")

    return fails
