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

import time
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_authorization_url_service import (
    build_authorization_url,
)
from nativeforge.services.customer_auth_dependency_contract_service import (
    evaluate_auth_dependency,
)
from nativeforge.services.customer_auth_redirect_flow_service import (
    build_redirect_flow_contract,
)
from nativeforge.services.customer_auth_redirect_state_repository_service import (
    TABLE_NAME as REDIRECT_STATE_TABLE,
)
from nativeforge.services.customer_auth_redirect_state_store_service import (
    DEFAULT_SCOPE as STATE_STORE_SCOPE,
)
from nativeforge.services.customer_auth_redirect_state_store_service import (
    consume_state,
    store_state,
)
from nativeforge.services.customer_auth_signing_key_readiness_service import (
    build_signing_key_readiness,
)
from nativeforge.services.customer_auth_state_pkce_service import (
    generate_state_and_pkce,
)
from nativeforge.services.customer_auth_token_exchange_boundary_service import (
    evaluate_token_exchange_boundary,
)
from nativeforge.services.customer_session_cookie_policy_service import (
    build_session_cookie_policy,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
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
    """Verify the cookie, then ask the dependency contract what to do.

    Gate 117 passed the cookie's *presence* and derived `valid=False`, because
    no session format existed to check it against. Gate 118 built one, so the
    cookie is now verified rather than assumed invalid - and it still comes out
    invalid, because no signing key is configured and nothing has issued a
    session.

    The cookie value goes into the verifier and no further. Nothing here logs,
    echoes or returns it: a session value in a response body is a session
    anybody can replay.

    `membership_verified=False` is passed deliberately rather than omitted. A
    membership record is a database question this route does not ask, and Gate
    112's rule is that a valid session is not a membership - so the answer is
    no until something looks it up.
    """
    policy = build_session_cookie_policy()

    verification = verify_session_cookie(
        cookie_value=cookie,
        membership_verified=False,
    )

    return evaluate_auth_dependency(
        dependency_mode=mode,
        session_verification=verification,
    ) | {
        "cookie_name": policy["cookie_name"],
        "session_verification": {
            # Booleans only. The value never leaves the verifier.
            "cookie_parseable": verification["cookie_parseable"],
            "signature_valid": verification["signature_valid"],
            "session_expired": verification["session_expired"],
            "organization_id_valid": verification["organization_id_valid"],
            "membership_verified": verification["membership_verified"],
            "rls_context_allowed": verification["rls_context_allowed"],
            "blocked_reasons": verification["blocked_reasons"],
        },
    }


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
    """Start a login. Issues state and PKCE; refuses to redirect.

    Returns a structured refusal rather than a redirect: redirecting to an
    unconfigured issuer would produce a browser error page with no explanation,
    and a 500 would suggest a bug rather than a missing configuration.

    Gate 119E: the state and the PKCE pair are now generated for real. They are
    local work — `secrets` and `hashlib`, no provider involved — so they do not
    wait on configuration. What waits on configuration is whether they can be
    placed in a URL, which is a separate boolean and is false.

    Neither value is returned. `state_issued` says one was made; a response body
    carrying the state itself would hand an attacker the thing the state exists
    to prove.
    """
    gate = _gate()
    flow = build_redirect_flow_contract()
    configured = bool(gate["provider_configured"] and gate["secret_present"])

    route_status = "auth_not_configured"
    if configured and not gate["login_live"]:
        route_status = "auth_not_live"

    # Local. No provider is contacted to produce either of these.
    issued = generate_state_and_pkce()
    state_issued = bool(issued["state_generated"])
    pkce_issued = bool(issued["code_challenge_generated"])

    # Recorded at the contract-only scope, which stores nothing and says so. The
    # table exists as of migration 0030 and this route does not write to it:
    # there is nowhere to send the browser, so there is no redirect to survive.
    stored = store_state(
        state_id=uuid.uuid4().hex,
        state_value=issued["state"],
        code_verifier=issued["code_verifier"],
        code_challenge=issued["code_challenge"],
        issued_at=int(time.time()),
        storage_scope=STATE_STORE_SCOPE,
    )

    # Consulted rather than assumed, so this route reports the same answer a
    # configured deployment would get. No URL is returned either way.
    url = build_authorization_url(
        redirect_uri=None,
        state=issued["state"],
        code_challenge=issued["code_challenge"],
    )
    signing = build_signing_key_readiness()

    body = _envelope("login", route_status, gate)
    body.update(
        {
            "provider_configured": bool(url["provider_configured"]),
            "authorization_url_available": bool(url["authorization_url_available"]),
            # Never returned. A URL carrying a client id and a redirect URI in a
            # response body is a configuration disclosure nobody asked for, and
            # there is nowhere to send the browser anyway.
            "authorization_redirect_issued": False,
            "authorization_url_returned": False,
            # Gate 119E: derived from a generator that ran, not constants.
            "state_issued": state_issued,
            "pkce_challenge_issued": pkce_issued,
            # Booleans about values, never the values.
            "state_value_returned": False,
            "pkce_verifier_returned": False,
            "state_stored": bool(stored["record_stored"]),
            "state_store_scope": stored["storage_scope"],
            "state_store_production": bool(stored["production_store"]),
            "redirect_state_table": REDIRECT_STATE_TABLE,
            "code_challenge_method": flow["code_challenge_method"],
            "state_required": True,
            "pkce_required": True,
            # A login that cannot sign a session cannot finish one.
            "session_signing_key_ready": bool(signing["can_sign_production_session"]),
            "signing_key_source": signing["signing_key_source"],
            # Kept out of `blocked_reasons`, which the envelope takes from the
            # activation gate so a route can never disagree with it about why
            # auth is unavailable. These are narrower: why this particular URL
            # could not be built.
            "authorization_url_blocked_reasons": list(url["blocked_reasons"]),
            "signing_key_blocked_reasons": list(signing["blocked_reasons"]),
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
    # Nothing was issued, so nothing can be found. Contract-only scope, which
    # stores nothing and says so.
    state_lookup = consume_state(state_id=None, returned_state=None)

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
            # Gate 118: no state was issued, so there is nothing stored to
            # retrieve. The store is consulted rather than assumed, so this
            # route reports the same refusal a real callback would get.
            "state_store_scope": state_lookup["storage_scope"],
            "state_store_production": state_lookup["production_store"],
            # Gate 119C: the durable store exists. This route does not read it,
            # because /login wrote nothing to it - the two facts are reported
            # separately so "a table exists" is never mistaken for "a redirect
            # can complete".
            "redirect_state_table": REDIRECT_STATE_TABLE,
            "redirect_state_repository_available": True,
            "redirect_state_durable": bool(flow["redirect_state_store_durable"]),
            "session_signing_key_ready": bool(flow["session_signing_key_ready"]),
            "stored_state_found": state_lookup["state_value_present"],
            "state_consume_allowed": state_lookup["consume_allowed"],
            "state_replay_detected": state_lookup["replay_detected"],
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
    verification = decision["session_verification"]
    body.update(
        {
            "authenticated": bool(decision["authenticated"]),
            "session_present": bool(decision["session_cookie_present"]),
            "session_valid": bool(decision["session_cookie_valid"]),
            "session_verified": bool(decision["session_verified"]),
            "dependency_mode": decision["dependency_mode"],
            # Gate 118: what the verifier found, as booleans. A caller learns
            # why their cookie did not work without the cookie coming back.
            "cookie_parseable": verification["cookie_parseable"],
            "signature_valid": verification["signature_valid"],
            "session_expired": verification["session_expired"],
            "session_blocked_reasons": verification["blocked_reasons"],
            # Still None: an organization comes from a verified membership,
            # and this route asks nobody for one.
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
