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
    "security_scheme_declared",
    "session_format_available",
    "session_verifier_available",
    "redirect_state_store_available",
    "session_signing_key_present",
    # Gate 119B: presence and fitness-to-sign are different facts, and only the
    # second one gates a live login.
    "session_signing_key_ready",
    "session_cookie_policy_available",
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


def detect_route_surface(*, openapi: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read the application's own route table.

    The schema is injectable so a test can supply one describing an application
    that *does* have auth routes - without that, every `available: True` branch
    would be unreachable and this service would be a constant.
    """
    if openapi is None:
        openapi = _load_openapi()

    paths = sorted(openapi.get("paths", {}) or {})
    app_paths = [p for p in paths if not p.startswith(FRAMEWORK_ROUTE_PREFIXES)]

    matched: dict[str, list[str]] = {}
    for field, pattern in ROUTE_PATTERNS.items():
        matched[field] = [p for p in app_paths if re.search(pattern, p, re.IGNORECASE)]

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


def _module_importable(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _signing_key_ready(
    readiness: dict[str, Any] | None,
    *,
    session_signing_key_present: bool | None = None,
) -> bool:
    """Is the key fit to sign a production session? Injectable, deliberately.

    When a caller has already asserted presence but supplied no readiness, the
    assertion is honoured: a test isolating the presence conjunct should not be
    forced to construct a readiness result as well. Without that, this branch
    would be unreachable and every refusal above it unfalsifiable.
    """
    if readiness is not None:
        return bool(readiness.get("can_sign_production_session"))
    if session_signing_key_present is not None:
        return bool(session_signing_key_present)
    from nativeforge.services.customer_auth_signing_key_readiness_service import (
        build_signing_key_readiness,
    )

    return bool(build_signing_key_readiness()["can_sign_production_session"])


def _signing_key_present() -> bool:
    """Is a session signing key configured? Presence only, never the value."""
    try:
        from nativeforge.services.customer_session_format_service import (
            signing_key_present,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    return signing_key_present()


def _session_cookie_policy_available() -> bool:
    """Does a session cookie policy exist, and does it hold together?

    Available means it exists *and* passes its own invariants. A policy failing
    them is not a policy anything should rely on, and reporting one as available
    would be worse than reporting none.
    """
    try:
        from nativeforge.services.customer_session_cookie_policy_service import (
            build_session_cookie_policy,
            policy_invariant_failures,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    return not policy_invariant_failures(build_session_cookie_policy())


def _customer_auth_live() -> bool:
    """Can anybody actually authenticate?

    Read through Gate 115's cheap detector rather than the activation gate
    directly: the gate reads this module's own output, and asking it back would
    be a cycle. The detector short-circuits on environment presence before
    paying for anything.
    """
    try:
        from nativeforge.services.customer_auth_live_detector_service import (
            detect_customer_auth_live,
        )
    except ImportError:  # pragma: no cover - the module is in this repository
        return False
    return detect_customer_auth_live()


def build_route_readiness(
    *,
    openapi: dict[str, Any] | None = None,
    cloudflare_access_in_front: bool = True,
    customer_auth_live: bool | None = None,
    principal_possible: bool | None = None,
    session_signing_key_present: bool | None = None,
    signing_key_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Which login routes exist, and whether any of them enforces anything."""
    surface = detect_route_surface(openapi=openapi)
    matched = surface["matched_routes"]

    routes = {field: bool(matched[field]) for field in ROUTE_PATTERNS}

    blocked_reasons: list[str] = []
    for field in REQUIRED_ROUTES:
        if not routes[field]:
            blocked_reasons.append(f"route_absent:{field}")

    # Gate 116 split two facts that were one value while no scheme existed.
    #
    #   security_scheme_declared   a scheme appears in the OpenAPI document
    #   has_security               some operation actually depends on one
    #
    # Gate 116 declares a scheme and applies it to no operation, deliberately.
    # A scheme in a document is documentation; enforcement is a refusal, and
    # nothing refuses yet. Collapsing the two would have made this service
    # report enforcement the moment the scheme was advertised - the exact
    # "existence is not enforcement" defect it exists to catch, one layer up.
    security_scheme_declared = bool(surface["security_schemes"])
    has_security = security_scheme_declared and bool(
        surface["globally_secured"] or surface["secured_route_count"]
    )

    # Gate 117: enforcement is a refusal, so it is measured from an operation
    # that has a security requirement attached AND a route that turns callers
    # away. Gate 116 could only infer it from the scheme, because nothing
    # refused; now one route does.
    route_auth_enforced = bool(has_security and surface["secured_route_count"])

    # Organization resolution and role mapping are NOT enforced by a 401.
    #
    # Gate 116 derived both from route_auth_enforced, which was safe while that
    # was always false. Securing /current-user would have made all three true at
    # once - and while the 401 is real, no route resolves an organization or
    # maps a role, and neither can until a principal exists.
    #
    # So both now additionally require customer auth to be live, which is what
    # a principal needs to exist at all.
    # Injectable, and it has to be. Without it `ready_for_live_login: True`
    # would be unreachable in this repository, and an unreachable branch makes
    # every "not ready" claim above it unfalsifiable.
    # Injectable for the same reason customer_auth_live is: without it,
    # `ready_for_live_login: True` would be unreachable and every "not ready"
    # claim above it unfalsifiable. Gate 117 learned this the same way, one
    # conjunct earlier.
    signing_key = (
        _signing_key_present()
        if session_signing_key_present is None
        else bool(session_signing_key_present)
    )
    # Gate 119B. A key read from the committed local-dev fixture is present and
    # unfit, so `ready_for_live_login` reads readiness while the older presence
    # boolean stays reported beside it - the two answer different questions and
    # collapsing them is how a demo secret ends up signing a real session.
    signing_ready = _signing_key_ready(
        signing_key_readiness,
        session_signing_key_present=session_signing_key_present,
    )
    # Gate 134F. This used to be `customer_auth_live`, and that made the
    # whole chain circular: customer_auth_live needs the dev header gone,
    # which needs auth_replacement_available, which needs
    # ready_for_live_login, which needs this. Nothing could ever satisfy
    # it, and the cycle was invisible because every link read as a
    # reasonable precondition on its own.
    #
    # The fact this conjunct is reaching for is *can a principal exist* -
    # which was equivalent to customer_auth_live only while nobody could
    # log in. Gate 132 made an identity resolve to an organization through
    # a membership row, and Gate 133 proved it in a browser, both with
    # customer_auth_live false throughout.
    #
    # `customer_auth_live` still satisfies it, because a live customer
    # auth certainly means a principal can exist. It is no longer the only
    # way, which is what removes the cycle.
    if principal_possible is None:
        principal_possible = (
            _customer_auth_live()
            if customer_auth_live is None
            else bool(customer_auth_live)
        )
    principal_possible = bool(principal_possible)
    route_org_resolution_enforced = bool(
        route_auth_enforced
        and principal_possible
        and routes["current_user_route_available"]
    )
    route_role_mapping_enforced = route_org_resolution_enforced

    # The cookie policy is enforced at a route when a route actually reads a
    # cookie to decide - which is what the required dependency does.
    route_session_cookie_policy_enforced = bool(
        route_auth_enforced and _session_cookie_policy_available()
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

    # Gate 118: a session format exists and no key signs it. Named rather than
    # silent - this is the single thing standing between the verifier and a
    # cookie that could verify.
    if not signing_key:
        blocked_reasons.append(
            "no_session_signing_key_configured_so_no_cookie_can_verify"
        )
    elif not signing_ready:
        blocked_reasons.append(
            "session_signing_key_present_but_not_fit_to_sign_a_production_session"
        )

    if not security_scheme_declared:
        blocked_reasons.append("no_security_scheme_is_declared_anywhere")
    elif not has_security:
        # The state Gate 116 leaves the application in, named rather than
        # silent: a scheme is advertised and no operation requires it.
        blocked_reasons.append("security_scheme_declared_but_no_route_requires_it")

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
        # Gate 118: without a signing key nothing can be signed and nothing can
        # be checked, so a login flow has no credential at the end of it. The
        # invariant below said so already; this makes the service incapable of
        # producing a result that fails it.
        and signing_key
        and signing_ready
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
            "session_signing_key_ready": signing_ready,
            "ready_for_live_login": ready_for_live_login,
            "application_route_count": surface["application_route_count"],
            "security_scheme_declared": security_scheme_declared,
            # Gate 118: three contracts a login flow needs, each detected by
            # import rather than assumed. A contract existing is not a working
            # session - `session_cookie_valid` in the verifier is still false
            # for every cookie, because no signing key is configured.
            "session_format_available": _module_importable(
                "nativeforge.services.customer_session_format_service"
            ),
            "session_verifier_available": _module_importable(
                "nativeforge.services.customer_session_verifier_service"
            ),
            "redirect_state_store_available": _module_importable(
                "nativeforge.services.customer_auth_redirect_state_store_service"
            ),
            "session_signing_key_present": signing_key,
            # Gate 117: measured, and reported beside enforcement so a reader
            # can see which of the two a claim rests on.
            "customer_auth_live": principal_possible,
            # Gate 116: whether a session cookie policy exists at all, which is
            # a different question from whether a route enforces one. The
            # activation gate reads this rather than the enforcement field.
            "session_cookie_policy_available": _session_cookie_policy_available(),
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

    # Gate 116: nor is a scheme being *declared*. An advertised scheme that no
    # operation requires enforces nothing, and this is the invariant that keeps
    # advertising it from reading as securing anything.
    if readiness.get("route_auth_enforced") and not readiness.get(
        "secured_route_count"
    ):
        fails.append("auth_reported_enforced_with_zero_secured_routes")

    # Gate 117: a 401 is not an organization. Enforcing authentication says
    # nothing about whether a route resolves an organization_id or maps a role,
    # and both need a principal that only live auth can produce.
    if readiness.get("route_org_resolution_enforced") and not readiness.get(
        "customer_auth_live"
    ):
        fails.append("org_resolution_enforced_while_nobody_can_authenticate")
    if readiness.get("route_role_mapping_enforced") and not readiness.get(
        "customer_auth_live"
    ):
        fails.append("role_mapping_enforced_while_nobody_can_authenticate")

    # Gate 118: a session format existing does not make a cookie verifiable.
    # Without a signing key nothing can be signed and nothing can be checked,
    # and a readiness surface reporting login-ready while that is true would be
    # describing a flow with no credential at the end of it.
    if readiness.get("ready_for_live_login") and not readiness.get(
        "session_signing_key_present"
    ):
        fails.append("login_ready_without_a_session_signing_key")

    # And a declared scheme must be reported as declared, or the two fields
    # would be able to disagree.
    if bool(readiness.get("security_schemes_declared")) is not bool(
        readiness.get("security_scheme_declared")
    ):
        fails.append("security_scheme_declared_disagrees_with_the_scheme_list")

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
