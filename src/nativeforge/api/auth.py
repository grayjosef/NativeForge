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

## Gate 117: one route now refuses

`/api/auth/current-user` returns **401** to an unauthenticated caller. It is the
first 401 NativeForge has ever returned - Gate 117A found the application had no
concept of "you are not authenticated", because nothing could authenticate.

That makes the security scheme honest on exactly one operation, so it is
attached to exactly one. The other four still answer everyone identically and
still advertise nothing:

```text
/login         optional   200, structured refusal
/callback      optional   200, refuses to mint a session
/logout        optional   200, clears the cookie
/session       optional   200, authenticated false
/current-user  required   401 until somebody can authenticate
```

A scheme in a document is documentation; enforcement is a refusal. Now one route
refuses, and the scheme says so about that route alone.

**Enforcement is not liveness.** `/current-user` refuses everybody, because
nobody can authenticate. A 401 proves the application can say no; it proves
nothing about whether anyone could ever be told yes, and `customer_auth_live`
stays false.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_dependency_contract_service import (
    evaluate_auth_dependency,
)
from nativeforge.services.customer_auth_redirect_flow_service import (
    build_redirect_flow_contract,
)
from nativeforge.services.customer_auth_token_exchange_boundary_service import (
    evaluate_token_exchange_boundary,
)
from nativeforge.services.customer_session_cookie_policy_service import (
    build_session_cookie_policy,
)

router = APIRouter(prefix="/api/auth", tags=["customer-auth"])

# Declared in the OpenAPI document and attached to exactly one operation:
# `/current-user`, the only route that actually refuses. Gate 116 attached it to
# none, correctly, because none refused then. See the module docstring.
SECURITY_SCHEME_NAME = "nf_session_cookie"


def _gate() -> dict[str, Any]:
    """The activation gate, for the two fields every response carries."""
    return build_customer_auth_activation_gate()


def _session_decision(mode: str, cookie: str | None) -> dict[str, Any]:
    """Ask the dependency contract what to do with this caller.

    The cookie's *presence* is passed, never its value. Nothing here parses,
    decodes or logs it - there is no session format to parse it against, and a
    value that reached a log would be a session anybody could replay.
    """
    policy = build_session_cookie_policy()
    present = bool(cookie)

    # No session format exists, so no cookie can be valid. Stated as a
    # derivation rather than a constant so it moves when one does.
    valid = False
    principal_resolved = False

    return evaluate_auth_dependency(
        dependency_mode=mode,
        session_cookie_present=present,
        session_cookie_valid=valid,
        principal_resolved=principal_resolved,
    ) | {"cookie_name": policy["cookie_name"]}


def require_customer_session(
    nf_session: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    """Refuse an unauthenticated caller with 401.

    NativeForge's first refusal. It refuses everybody today, which is correct
    and is not the same as being broken: nobody can authenticate, so nobody
    should be let through.
    """
    decision = _session_decision("required", nf_session)
    if not decision["authorized"]:
        gate = _gate()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "unauthenticated",
                "customer_auth_live": bool(gate["customer_auth_live"]),
                "login_live": bool(gate["login_live"]),
                "blocked_reasons": decision["blocked_reasons"],
            },
            headers={"WWW-Authenticate": "Cookie"},
        )
    return decision


def optional_customer_session(
    nf_session: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    """Permit an unauthenticated caller, and tell them they are one."""
    return _session_decision("optional", nf_session)


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
    flow = build_redirect_flow_contract()
    configured = bool(gate["provider_configured"] and gate["secret_present"])

    route_status = "auth_not_configured"
    if configured and not gate["login_live"]:
        route_status = "auth_not_live"

    body = _envelope("login", route_status, gate)
    body.update(
        {
            "provider_configured": bool(flow["provider_configured"]),
            "authorization_url_available": bool(flow["authorization_url_available"]),
            # Never returned. A URL carrying a client id and a redirect URI in a
            # response body is a configuration disclosure nobody asked for, and
            # there is nowhere to send the browser anyway.
            "authorization_redirect_issued": False,
            # Generated locally at this route once there is somewhere to send
            # them. Not issued now, because there is not.
            "state_issued": False,
            "pkce_challenge_issued": False,
            "code_challenge_method": flow["code_challenge_method"],
            "state_required": True,
            "pkce_required": True,
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
    # No state was issued, so none can be validated. The boundary is consulted
    # rather than assumed, so this route reports the same refusal the boundary
    # would give a real callback.
    exchange = evaluate_token_exchange_boundary(
        callback_code_present=False,
        state_validated=False,
        pkce_validated=False,
    )
    flow = build_redirect_flow_contract()

    body = _envelope("callback", "callback_validation_not_passed", gate)
    body.update(
        {
            "session_created": False,
            "session_creation_allowed": bool(flow["session_creation_allowed"]),
            "state_validated": False,
            "pkce_verified": False,
            "token_exchange_allowed": bool(exchange["token_exchange_allowed"]),
            "token_exchange_performed": bool(exchange["token_exchange_performed"]),
            "network_call_allowed": bool(exchange["network_call_allowed"]),
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
def session(
    decision: Annotated[dict[str, Any], Depends(optional_customer_session)],
) -> dict[str, Any]:
    """Report on the caller's session. There are none.

    Optional rather than required: a caller asking whether they have a session
    should be told no, not refused for not having one.
    """
    gate = _gate()
    body = _envelope("session", "unauthenticated", gate)
    body.update(
        {
            "authenticated": bool(decision["authenticated"]),
            "session_present": bool(decision["session_cookie_present"]),
            "session_valid": bool(decision["session_cookie_valid"]),
            "dependency_mode": decision["dependency_mode"],
            "organization_id": None,
            "expires_at": None,
        }
    )
    return body


@router.get(
    "/current-user",
    # The one operation that actually refuses, so the one that advertises the
    # scheme. Attaching it to a route that admits everybody would tell a reader
    # a credential is needed when it is not.
    openapi_extra={"security": [{SECURITY_SCHEME_NAME: []}]},
    responses={401: {"description": "No valid customer session."}},
)
def current_user(
    decision: Annotated[dict[str, Any], Depends(require_customer_session)],
) -> dict[str, Any]:
    """Report who the caller is. Nobody, so far.

    `organization_id` is `None` rather than absent, and it stays `None` until
    Gate 112's resolution plus a verified membership say otherwise. A route that
    reported an organization from an unverified claim would be the exact defect
    Gates 110 through 113 exist to prevent.
    """
    # Unreachable while nobody can authenticate: the dependency raises 401
    # before this runs. It is written for the day that changes, and a test
    # forces the dependency to permit so this body is not dead code nobody has
    # ever executed.
    gate = _gate()
    body = _envelope("current_user", "authenticated", gate)
    body.update(
        {
            "authenticated": bool(decision["authenticated"]),
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
    """Declare the session cookie scheme in the OpenAPI document.

    Still post-processed rather than emitted by FastAPI. `/current-user`
    attaches the scheme through `openapi_extra` rather than through a
    `Security(...)` dependency, because its dependency reads a plain `Cookie`
    and raises - which enforces correctly and tells FastAPI's schema generator
    nothing.

    Gate 116 declared this scheme and attached it to no operation, correctly:
    nothing refused then. Gate 117 attaches it to the one operation that does.
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
