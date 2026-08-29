"""Customer auth routes (Gate 116D).

Five endpoints that authenticate nobody, and say so.

## Why register routes that do not work yet

Gate 115 found that customer auth was not a configuration problem. Even with
every `OIDC_*` variable set and a validated issuer, there was nowhere for a
customer to log in — 178 endpoints, none requiring a credential, no security
scheme anywhere.

These five routes close that gap in the only way that is honest today: they
exist, they are shaped like the real thing, and each one refuses with a named
reason instead of pretending. `/login` says not-configured rather than
redirecting nowhere; `/callback` refuses to mint a session rather than minting
an empty one; `/session` and `/current-user` report `authenticated: false`.

**None of them makes auth live.** Every response carries `customer_auth_live`
and `login_live` read from Gate 115's activation gate, and both are false.

## What these routes must never do

```text
contact an identity provider    no provider is configured, and nothing here
                                would reach one if it were
create a real session           only /callback could, and only once callback
                                validation, organization_id resolution and
                                membership verification have all passed
create a user                   no row, anywhere
set app.current_org_id          these routes are the eventual *replacement*
                                for the dev org header, so they must not
                                consume it or the RLS context it sets
print or return a secret        presence booleans only, and never a value
```

## Why no dependency on the org context

Sixteen route modules obtain an organization through
`deps_db.get_org_context_with_db` and the `X-NF-Org-Id` header. These routes
deliberately do not. They are what should eventually replace that header, and a
replacement that depends on the thing it replaces is not one.

## The security scheme is advertised, not applied

`install_auth_security_scheme` adds a `securitySchemes` entry to the generated
OpenAPI document and attaches it to **no operation**. That is deliberate: a
scheme referenced by an operation would make Gate 115C's route readiness report
`route_auth_enforced: true`, while these routes still answered everyone
identically. A scheme in a document is documentation; enforcement is a refusal,
and nothing here refuses yet.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response

from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_session_cookie_policy_service import (
    build_session_cookie_policy,
)

router = APIRouter(prefix="/api/auth", tags=["customer-auth"])

# Advertised in the OpenAPI document and applied to no operation. See the module
# docstring: applying it would make readiness report enforcement that does not
# exist.
SECURITY_SCHEME_NAME = "nf_session_cookie"


def _gate() -> dict[str, Any]:
    """The activation gate, for the two fields every response carries."""
    return build_customer_auth_activation_gate()


def _envelope(route: str, status: str, gate: dict[str, Any]) -> dict[str, Any]:
    """The fields every auth route returns, whatever else it says.

    `blocked_reasons` and `next_required_actions` come from the activation gate
    rather than being written here, so a route can never disagree with the gate
    about why auth is unavailable.
    """
    return {
        "route": route,
        "status": status,
        "customer_auth_live": bool(gate["customer_auth_live"]),
        "login_live": bool(gate["login_live"]),
        "blocked_reasons": list(gate["blocked_reasons"]),
        "next_required_actions": list(gate["next_required_actions"]),
        # Constants, restated per response so a caller reading one endpoint in
        # isolation still sees them.
        "real_session_created": False,
        "real_user_created": False,
        "provider_contacted": False,
    }


@router.get("/login")
def login() -> dict[str, Any]:
    """Start a login. Refuses while no provider is configured.

    Returns a structured refusal rather than a redirect: redirecting to an
    unconfigured issuer would produce a browser error page with no explanation,
    and a 500 would suggest a bug rather than a missing configuration.
    """
    gate = _gate()
    configured = bool(gate["provider_configured"] and gate["secret_present"])

    status = "auth_not_configured"
    if configured and not gate["login_live"]:
        status = "auth_not_live"

    body = _envelope("login", status, gate)
    body.update(
        {
            "provider_configured": bool(gate["provider_configured"]),
            "authorization_redirect_issued": False,
            # Both are generated at this route once a flow exists. Neither is
            # generated now, because there is nowhere to send them.
            "state_issued": False,
            "pkce_challenge_issued": False,
        }
    )
    return body


@router.get("/callback")
def callback() -> dict[str, Any]:
    """Receive a provider redirect. Refuses to mint a session.

    The one route that could ever create a session, and it does so only once
    callback validation, organization_id resolution and membership verification
    have all passed. None has.
    """
    gate = _gate()
    body = _envelope("callback", "callback_validation_not_passed", gate)
    body.update(
        {
            "session_created": False,
            "state_validated": False,
            "pkce_verified": False,
            "callback_session_validated": bool(gate["callback_session_validated"]),
            "org_binding_passed": bool(gate["org_binding_passed"]),
            # Named individually: a caller who gets a refusal here needs to know
            # which of the three is missing, not merely that one is.
            "organization_id_resolved": False,
            "membership_verified": False,
        }
    )
    return body


@router.post("/logout")
def logout(response: Response) -> dict[str, Any]:
    """Clear the session cookie. Safe whether or not one exists.

    The only route permitted to act while auth is not live. Refusing to clear on
    the grounds that there is no session would leave a stale cookie behind on
    exactly the path somebody uses to get rid of one.

    `delete_cookie` writes an expiry, never a value.
    """
    gate = _gate()
    policy = build_session_cookie_policy()

    response.delete_cookie(
        key=policy["cookie_name"],
        path=policy["path"],
        domain=policy["domain"],
        httponly=policy["http_only"],
        secure=policy["secure"],
        samesite=policy["same_site"],
    )

    body = _envelope("logout", "no_live_session", gate)
    body.update(
        {
            "cookie_cleared": True,
            "cookie_name": policy["cookie_name"],
            "had_live_session": False,
        }
    )
    return body


@router.get("/session")
def session() -> dict[str, Any]:
    """Report on the caller's session. There are none."""
    gate = _gate()
    body = _envelope("session", "unauthenticated", gate)
    body.update(
        {
            "authenticated": False,
            "session_present": False,
            "organization_id": None,
            "expires_at": None,
        }
    )
    return body


@router.get("/current-user")
def current_user() -> dict[str, Any]:
    """Report who the caller is. Nobody, so far.

    `organization_id` is `None` rather than absent, and it stays `None` until
    Gate 112's resolution plus a verified membership say otherwise. A route that
    reported an organization from an unverified claim would be the exact defect
    Gates 110 through 113 exist to prevent.
    """
    gate = _gate()
    body = _envelope("current_user", "unauthenticated", gate)
    body.update(
        {
            "authenticated": False,
            "subject": None,
            "email": None,
            "organization_id": None,
            "organization_id_resolved": False,
            "membership_verified": False,
            "roles": [],
            "least_privilege_role": "unknown",
        }
    )
    return body


def install_auth_security_scheme(app: Any) -> None:
    """Advertise the session cookie scheme in the OpenAPI document.

    Applied to no operation, deliberately. FastAPI emits `securitySchemes` only
    for schemes an operation actually depends on, so declaring one that nothing
    enforces means post-processing the generated document.

    That asymmetry is the honest state of the system: NativeForge has decided
    what its session credential looks like and has not yet made any route
    require one.
    """
    from nativeforge.services.customer_session_cookie_policy_service import (
        build_session_cookie_policy as _policy,
    )

    original = app.openapi

    def _openapi() -> dict[str, Any]:
        schema = original()
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes[SECURITY_SCHEME_NAME] = {
            "type": "apiKey",
            "in": "cookie",
            "name": _policy()["cookie_name"],
            "description": (
                "NativeForge customer session cookie. Declared and applied to "
                "no operation: no route requires a credential yet. See Gate 116."
            ),
        }
        return schema

    app.openapi = _openapi
