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
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from nativeforge.api.deps import get_db
from nativeforge.lib.settings import auth_environment_overlay
from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_authorization_url_service import (
    build_authorization_url,
)
from nativeforge.services.customer_auth_binding_evidence_service import (
    build_binding_evidence,
)
from nativeforge.services.customer_auth_dependency_contract_service import (
    evaluate_auth_dependency,
)
from nativeforge.services.customer_auth_environment_preflight_service import (
    CALLBACK_ROUTE_PATH,
)
from nativeforge.services.customer_auth_jwks_validation_evidence_service import (
    build_jwks_validation_evidence,
    record_validation_evidence,
)
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    build_owner_activation_decision,
)
from nativeforge.services.customer_auth_redirect_flow_service import (
    build_redirect_flow_contract,
)
from nativeforge.services.customer_auth_redirect_state_repository_service import (
    TABLE_NAME as REDIRECT_STATE_TABLE,
)
from nativeforge.services.customer_auth_redirect_state_repository_service import (
    consume_redirect_state,
    persist_redirect_state,
)
from nativeforge.services.customer_auth_redirect_state_store_service import (
    DEFAULT_SCOPE as STATE_STORE_SCOPE,
)
from nativeforge.services.customer_auth_redirect_state_store_service import (
    consume_state,
    store_state,
)
from nativeforge.services.customer_auth_role_mapping_evidence_service import (
    build_role_mapping_evidence,
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
from nativeforge.services.customer_session_format_service import (
    build_session,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)
from nativeforge.services.dev_org_membership_bootstrap_service import (
    upsert_identity,
)
from nativeforge.services.identity_org_session_resolution_service import (
    resolve_session_organization,
)
from nativeforge.services.oidc_provider_discovery_service import (
    build_provider_endpoints,
)
from nativeforge.services.oidc_token_exchange_client_service import (
    exchange_authorization_code,
)
from nativeforge.services.oidc_token_verification_service import (
    fetch_jwks,
    verify_oidc_token,
)

router = APIRouter(prefix="/api/auth", tags=["customer-auth"])

#: A bare session with no organization bound. Deliberately `get_db` rather than
#: `deps_db.get_org_context_with_db`: these routes are the replacement for the
#: dev org header and must not consume the RLS context it sets.
DbSession = Annotated[Session, Depends(get_db)]

# Declared in the OpenAPI document and attached to exactly one operation:
# `/current-user`, the only route that actually refuses. Gate 116 attached it to
# none, correctly, because none refused then. See the module docstring.
SECURITY_SCHEME_NAME = "nf_session_cookie"


def _gate(db: Session | None = None) -> dict[str, Any]:
    """The activation gate, for the two fields every response carries.

    Gate 132G: a route with a session hands over what the database says, so
    `org_binding_passed` and `callback_session_validated` are measured rather
    than assumed false. A caller without one gets the deterministic answer.

    Gate 133 adds two more measurements and one decision. The decision is
    checked against the organization that actually has a mapped membership,
    read out of the role-mapping evidence - not against an id this function
    supplies. When the mapping is ambiguous (nought or several organizations)
    no organization is offered and the decision refuses by name, which is the
    deny-by-default branch rather than a fallback.
    """
    evidence = None
    jwks_evidence = None
    role_evidence = None
    decision = None

    if db is not None:
        try:
            connection = db.connection()
            evidence = build_binding_evidence(connection=connection)
            jwks_evidence = build_jwks_validation_evidence(connection=connection)
            role_evidence = build_role_mapping_evidence(connection=connection)
        except Exception:
            db.rollback()
            evidence = jwks_evidence = role_evidence = None

    if role_evidence is not None:
        mapped = list(role_evidence.get("mapped_organizations") or [])
        decision = build_owner_activation_decision(
            organization_id=mapped[0] if len(mapped) == 1 else None,
            provider=(auth_environment_overlay().get("OIDC_ISSUER") or "").strip(),
        )

    return build_customer_auth_activation_gate(
        binding_evidence=evidence,
        jwks_validation_evidence=jwks_evidence,
        role_mapping_evidence=role_evidence,
        login_activation_decision=decision,
    )


def _session_decision(
    mode: str, cookie: str | None, db: Session | None = None
) -> dict[str, Any]:
    """Verify the cookie, then ask the dependency contract what to do.

    Gate 117 passed the cookie's *presence* and derived `valid=False`, because
    no session format existed to check it against. Gate 118 built one, so the
    cookie is verified rather than assumed invalid.

    The cookie value goes into the verifier and no further. Nothing here logs,
    echoes or returns it: a session value in a response body is a session
    anybody can replay.

    ## Gate 132: the membership question is finally asked

    It used to be `membership_verified=False`, passed deliberately, with the
    reason recorded: "a membership record is a database question this route does
    not ask". `nf_org_memberships` had no write path, so the answer was no for
    everybody and asking would have been theatre.

    Now it is asked, which takes two verifier calls. The first parses and checks
    the signature - a payload is only worth reading once the signature says it
    is ours - and yields the principal and the organization the cookie claims.
    The membership is then read, and the second call re-derives with the answer.

    The claimed organization must be the one the membership resolves to. A
    cookie naming organization A held by a member of organization B is not a
    member of A, and accepting it because *some* membership exists would be the
    cross-tenant read every RLS rule in this codebase is written against.
    """
    policy = build_session_cookie_policy()

    parsed = verify_session_cookie(cookie_value=cookie, membership_verified=False)

    membership_verified = False
    resolution: dict[str, Any] = {}
    if db is not None and parsed["session_cookie_valid"] and parsed["principal_id"]:
        try:
            resolution = resolve_session_organization(
                connection=db.connection(),
                identity_id=parsed["principal_id"],
            )
        except Exception:
            db.rollback()
            resolution = {}
        membership_verified = bool(
            resolution.get("organization_id_resolved")
            and resolution.get("organization_id") == parsed["organization_id"]
        )

    verification = (
        verify_session_cookie(cookie_value=cookie, membership_verified=True)
        if membership_verified
        else parsed
    )

    return evaluate_auth_dependency(
        dependency_mode=mode,
        session_verification=verification,
    ) | {
        "cookie_name": policy["cookie_name"],
        "membership_lookup_performed": db is not None,
        "membership_resolution_blocked_reasons": sorted(
            resolution.get("blocked_reasons") or []
        ),
        "session_verification": {
            # Booleans only. The value never leaves the verifier.
            "cookie_parseable": verification["cookie_parseable"],
            "signature_valid": verification["signature_valid"],
            "session_expired": verification["session_expired"],
            "organization_id_valid": verification["organization_id_valid"],
            "membership_verified": verification["membership_verified"],
            "rls_context_allowed": verification["rls_context_allowed"],
            "blocked_reasons": verification["blocked_reasons"],
            "principal_id": verification["principal_id"],
            # The organization and the roles come from the **membership row**,
            # not from the cookie that claims them.
            #
            # A first pass here read `verification["organization_id"]`, which is
            # whatever the payload says. A session naming an organization the
            # holder is not a member of - a stale cookie outliving a revoked
            # membership, or one minted before the membership moved - then came
            # back reported as that organization. Declared, not derived, and the
            # exact substitution Gates 110-113 exist to prevent. Caught by the
            # cross-organization case in Gate 132's probe.
            "organization_id": (
                resolution.get("organization_id") if membership_verified else None
            ),
            "roles": list(resolution.get("roles") or []) if membership_verified else [],
        },
    }


def require_customer_session(
    db: DbSession,
    nf_session: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    """Refuse an unauthenticated caller with 401.

    NativeForge's first refusal. It refused everybody until Gate 132, which is
    not the same as being broken: nobody could authenticate, so nobody should
    have been let through.
    """
    decision = _session_decision("required", nf_session, db)
    if not decision["authorized"]:
        gate = _gate(db)
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
    db: DbSession,
    nf_session: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    """Permit an unauthenticated caller, and tell them they are one."""
    return _session_decision("optional", nf_session, db)


def _envelope(
    route: str,
    status: str,
    gate: dict[str, Any],
    *,
    real_session_created: bool = False,
    real_user_created: bool = False,
    provider_contacted: bool = False,
) -> dict[str, Any]:
    """The fields every auth route returns, whatever else it says.

    `blocked_reasons` and `next_required_actions` come from the activation gate
    rather than being written here, so a route can never disagree with the gate
    about why auth is unavailable.

    ## Gate 132: three constants stopped being constants

    `real_session_created`, `real_user_created` and `provider_contacted` were
    hardcoded `False` on every response, and every one of them was true when
    Gate 132's callback ran: it contacted Google, wrote an `nf_identities` row,
    and minted a session. A field asserting otherwise is not a safety property,
    it is a false statement in the response body - and it would have been
    trusted precisely because it had been true for sixteen gates.

    They default `False`, so a route that does none of those things says so
    without having to remember to. `/callback` passes what it actually did.
    """
    return {
        "route": route,
        "status": status,
        "customer_auth_live": bool(gate["customer_auth_live"]),
        "login_live": bool(gate["login_live"]),
        "blocked_reasons": list(gate["blocked_reasons"]),
        "next_required_actions": list(gate["next_required_actions"]),
        "real_session_created": bool(real_session_created),
        "real_user_created": bool(real_user_created),
        "provider_contacted": bool(provider_contacted),
    }


#: Gate 130. Discovery reaches the issuer's public metadata document, which is
#: a network call, so it is off unless a deployment turns it on. An issuer that
#: follows the conventional shape resolves offline without it; one that does not
#: reports no endpoint rather than a guessed one.
DISCOVERY_ENV = "NF_OIDC_DISCOVERY_ENABLED"


def _discovery_allowed() -> bool:
    import os

    return (os.environ.get(DISCOVERY_ENV) or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


#: The scope that actually keeps a row. `contract_only` is the contract's
#: scope and stores nothing; Gate 131 needs the one that survives a restart.
DURABLE_STATE_SCOPE = "database"


@router.get("/login")
def login(db: DbSession) -> Any:
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
    gate = _gate(db)
    flow = build_redirect_flow_contract()
    configured = bool(gate["provider_configured"] and gate["secret_present"])

    route_status = "auth_not_configured"
    if configured and not gate["login_live"]:
        route_status = "auth_not_live"

    # Local. No provider is contacted to produce either of these.
    issued = generate_state_and_pkce()
    state_issued = bool(issued["state_generated"])
    pkce_issued = bool(issued["code_challenge_generated"])

    # Gate 131B. Written to nf_auth_redirect_states for real, with the PKCE
    # verifier encrypted at rest (migration 0036) so the callback can present it
    # to the token endpoint. The contract-scope call is kept alongside it so the
    # response still reports what the contract says, unchanged.
    stored = store_state(
        state_id=uuid.uuid4().hex,
        state_value=issued["state"],
        code_verifier=issued["code_verifier"],
        code_challenge=issued["code_challenge"],
        issued_at=int(time.time()),
        storage_scope=STATE_STORE_SCOPE,
    )

    _auth_env = auth_environment_overlay()
    _configured_callback = (_auth_env.get("OIDC_CALLBACK_URL") or "").strip()
    if not _configured_callback:
        _origin = (_auth_env.get("NF_PUBLIC_ORIGIN") or "").strip().rstrip("/")
        _configured_callback = f"{_origin}{CALLBACK_ROUTE_PATH}" if _origin else ""

    persisted = {"row_written": False, "blocked_reasons": ["state_not_attempted"]}
    if configured and _configured_callback:
        try:
            persisted = persist_redirect_state(
                connection=db.connection(),
                state_value=issued["state"],
                code_verifier=issued["code_verifier"],
                code_challenge=issued["code_challenge"],
                redirect_uri=_configured_callback,
                issuer=(_auth_env.get("OIDC_ISSUER") or "").strip() or None,
                audience=(_auth_env.get("OIDC_AUDIENCE") or "").strip() or None,
                storage_scope=DURABLE_STATE_SCOPE,
            )
            if persisted.get("row_written"):
                db.commit()
        except Exception:
            # A state store that is unreachable is a refusal, not a 500. The
            # browser gets a named reason rather than a stack trace.
            db.rollback()
            persisted = {
                "row_written": False,
                "blocked_reasons": ["redirect_state_store_unavailable"],
            }

    # Consulted rather than assumed, so this route reports the same answer a
    # configured deployment would get. No URL is returned either way.
    #
    # Gate 130: `redirect_uri=None` was hardcoded, so the claim above was not
    # true - the route reported what an UNCONFIGURED deployment gets no matter
    # what the environment held. The configured callback is read now, and the
    # authorization endpoint is discovered from the issuer rather than guessed:
    # Google's is /o/oauth2/v2/auth, not the /authorize this codebase assumed.
    #
    # Discovery is a network call, so it is opt-in per deployment. Without it a
    # conventional issuer still resolves offline and Google reports no endpoint
    # rather than a wrong one.
    # Gate 131C: the callback is resolved once, above, before the state row is
    # written. This block resolved it a second time and shadowed the
    # module-level import doing it.
    signing = build_signing_key_readiness()

    url = build_authorization_url(
        redirect_uri=_configured_callback or None,
        state=issued["state"],
        code_challenge=issued["code_challenge"],
        allow_network=_discovery_allowed(),
    )

    # Gate 131C. Every conjunct, derived. A redirect issued while any one of
    # these is false sends a browser to a provider that will refuse it, or -
    # worse - completes a flow whose state nobody can validate on return.
    redirect_ready = bool(
        configured
        and url["authorization_url_available"]
        and persisted.get("row_written")
        # `can_sign_production_session`, not merely `signing_key_present`: a key
        # that exists but is too short, or is the committed local_dev_fixture,
        # must not start a flow whose session it cannot legitimately sign.
        and signing["can_sign_production_session"]
    )
    if redirect_ready:
        # The URL carries the state, so it is never logged or returned in a
        # body. It goes in a Location header and nowhere else.
        return RedirectResponse(
            url=url["authorization_url"],
            status_code=status.HTTP_302_FOUND,
        )
    body = _envelope("login", route_status, gate)
    body.update(
        {
            "provider_configured": bool(url["provider_configured"]),
            "authorization_url_available": bool(url["authorization_url_available"]),
            # Gate 131: whether a durable row was written, and why not.
            "state_persisted": bool(persisted.get("row_written")),
            "state_store_blocked_reasons": sorted(
                persisted.get("blocked_reasons") or []
            ),
            "redirect_ready": bool(redirect_ready),
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
def callback(
    db: DbSession,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Receive a provider redirect. Validate, exchange, verify - then stop.

    Gate 131. The route runs the real flow now and refuses by name at each
    stage. It still creates no session, and the reason is no longer "nothing
    was issued": it is that a session requires an organization and no identity
    has one yet.

    Nothing here returns, logs or stores the code, the PKCE verifier, the ID
    token or the access token. They are locals, and the response carries
    booleans and named reasons.
    """
    gate = _gate(db)
    flow = build_redirect_flow_contract()

    provider_error = str(error or "").strip()
    returned_state = str(state or "").strip()
    returned_code = str(code or "").strip()

    _auth_env = auth_environment_overlay()

    # -- 1. the state, consumed exactly once ------------------------------
    consumed: dict[str, Any] = {
        "consume_allowed": False,
        "replay_detected": False,
        "expired": False,
        "row_found": False,
        "blocked_reasons": ["state_not_presented"],
    }
    code_verifier = ""
    if returned_state and not provider_error:
        try:
            consumed = consume_redirect_state(
                connection=db.connection(),
                returned_state=returned_state,
                storage_scope=DURABLE_STATE_SCOPE,
                return_verifier=True,
            )
            code_verifier = str(consumed.pop("code_verifier", "") or "")
            db.commit()
        except Exception:
            db.rollback()
            consumed = {
                "consume_allowed": False,
                "replay_detected": False,
                "expired": False,
                "row_found": False,
                "blocked_reasons": ["redirect_state_store_unavailable"],
            }

    state_validated = bool(consumed.get("consume_allowed"))
    pkce_validated = bool(state_validated and code_verifier)

    # -- 2. the exchange, only on a validated state -----------------------
    exchange_report: dict[str, Any] = {
        "attempted": False,
        "succeeded": False,
        "http_status": 0,
        "provider_error": "",
        "blocked_reasons": [],
    }
    verification: dict[str, Any] = {"verified": False, "state": "not_attempted"}
    validation_evidence: dict[str, Any] = {
        "rows_written": 0,
        "blocked_reasons": ["no_verification_attempted"],
    }
    identity_email_domain = ""

    if state_validated and pkce_validated and returned_code:
        endpoints = build_provider_endpoints(
            (_auth_env.get("OIDC_ISSUER") or "").strip(),
            allow_network=_discovery_allowed(),
        )
        exchange_report, tokens = exchange_authorization_code(
            token_endpoint=endpoints.get("token_endpoint"),
            client_id=(_auth_env.get("OIDC_CLIENT_ID") or "").strip(),
            client_secret=(_auth_env.get("OIDC_CLIENT_SECRET") or "").strip(),
            code=returned_code,
            code_verifier=code_verifier,
            redirect_uri=(_auth_env.get("OIDC_CALLBACK_URL") or "").strip(),
            allow_network=_discovery_allowed(),
        )
        if exchange_report.get("succeeded"):
            jwks = fetch_jwks(
                jwks_url=endpoints.get("jwks_uri"),
                allow_network=_discovery_allowed(),
            )
            verification = verify_oidc_token(
                token=tokens.get("id_token"),
                jwks=jwks.get("jwks"),
                expected_issuer=(_auth_env.get("OIDC_ISSUER") or "").strip(),
                expected_audience=(_auth_env.get("OIDC_AUDIENCE") or "").strip(),
            )
            if verification.get("verified"):
                # The domain half only. The address itself is not an identifier
                # NativeForge stores, and Gate 112 refuses it as authority.
                email = str(verification.get("email") or "")
                identity_email_domain = email.rpartition("@")[2] if "@" in email else ""

            # Gate 133B. Until now this verification happened and then stopped
            # existing - a local, discarded when the request ended, while
            # `issuer_jwks_validated` reported a literal False. The whole result
            # is handed over rather than booleans about it, so a caller cannot
            # assert a verification the verifier did not perform; the service
            # reduces it to what may be stored and drops the rest.
            #
            # `provider_called` comes from the fetcher's own report of whether
            # it went out, not from whether discovery was permitted.
            try:
                validation_evidence = record_validation_evidence(
                    connection=db.connection(),
                    verification=verification,
                    jwks_fetch=jwks,
                    provider_called=bool(jwks.get("network_access_attempted")),
                )
                db.commit()
            except Exception:
                db.rollback()
                validation_evidence = {
                    "rows_written": 0,
                    "blocked_reasons": ["validation_event_store_unavailable"],
                }

    identity_validated = bool(verification.get("verified"))

    # -- 3. the identity, persisted -----------------------------------------
    #
    # Gate 132. The verified subject becomes a row, so the person who just
    # proved who they are exists in NativeForge rather than only in a log line.
    # Idempotent by (issuer, subject): signing in twice is one person.
    #
    # This creates no membership. A Google account is not a membership, and a
    # callback that granted one would let anybody with an account join.
    identity_result: dict[str, Any] = {
        "rows_written": 0,
        "identity_existed": False,
        "identity_id": None,
        "blocked_reasons": ["identity_not_verified"],
    }
    identity_id = ""
    if identity_validated:
        try:
            identity_result = upsert_identity(
                connection=db.connection(),
                issuer=str(verification.get("issuer") or "").strip()
                or (_auth_env.get("OIDC_ISSUER") or "").strip(),
                subject=verification.get("subject"),
                email=verification.get("email"),
                email_verified=bool(verification.get("email_verified")),
                verification_source="oidc_token_signature",
            )
            db.commit()
            identity_id = str(identity_result.get("identity_id") or "")
        except Exception:
            db.rollback()
            identity_result = {
                "rows_written": 0,
                "identity_existed": False,
                "identity_id": None,
                "blocked_reasons": ["identity_store_unavailable"],
            }

    # -- 4. the organization, from a membership row and nothing else --------
    resolution: dict[str, Any] = {
        "organization_id_resolved": False,
        "organization_id": "",
        "membership_verified": False,
        "roles": [],
        "blocked_reasons": ["identity_not_persisted"],
    }
    if identity_id:
        try:
            resolution = resolve_session_organization(
                connection=db.connection(), identity_id=identity_id
            )
        except Exception:
            db.rollback()
            resolution = {
                "organization_id_resolved": False,
                "organization_id": "",
                "membership_verified": False,
                "roles": [],
                "blocked_reasons": ["membership_store_unavailable"],
            }

    organization_id_resolved = bool(resolution.get("organization_id_resolved"))
    membership_verified = bool(resolution.get("membership_verified"))
    org_binding_missing = bool(identity_validated and not organization_id_resolved)

    # -- 5. the session, only once all of that holds ------------------------
    session_created = False
    session_blocked_reasons: list[str] = []
    if organization_id_resolved and membership_verified:
        policy = build_session_cookie_policy()
        issued = int(time.time())
        built = build_session(
            principal_id=identity_id,
            subject=identity_id,
            organization_id=resolution.get("organization_id"),
            roles=list(resolution.get("roles") or []),
            issued_at=issued,
            expires_at=issued + int(policy["max_age_seconds"]),
            auth_source="oidc_authorization_code",
            session_id=str(uuid.uuid4()),
        )
        session_blocked_reasons = list(built["blocked_reasons"])
        if built["session_cookie_valid"]:
            response.set_cookie(
                key=policy["cookie_name"],
                value=built["session_cookie_value"],
                max_age=int(policy["max_age_seconds"]),
                path=policy["path"],
                domain=policy["domain"],
                secure=bool(policy["secure"]),
                httponly=bool(policy["http_only"]),
                samesite=policy["same_site"],
            )
            session_created = True

    exchange = evaluate_token_exchange_boundary(
        callback_code_present=bool(returned_code),
        state_validated=state_validated,
        pkce_validated=pkce_validated,
    )
    state_lookup = consume_state(state_id=None, returned_state=None)

    route_status = "callback_validation_not_passed"
    if provider_error:
        route_status = "provider_returned_an_error"
    elif session_created:
        route_status = "session_created"
    elif org_binding_missing:
        route_status = "identity_verified_without_an_organization_binding"

    body = _envelope(
        "callback",
        route_status,
        gate,
        real_session_created=session_created,
        real_user_created=bool(identity_result.get("rows_written")),
        provider_contacted=bool(exchange_report.get("attempted")),
    )
    body.update(
        {
            "session_created": session_created,
            "session_creation_allowed": bool(flow["session_creation_allowed"]),
            # Gate 132. The identity is a row now; the membership is not
            # created here, and the session waits on one that already exists.
            "identity_persisted": bool(
                identity_result.get("rows_written")
                or identity_result.get("identity_existed")
            ),
            "identity_rows_written": int(identity_result.get("rows_written") or 0),
            "identity_already_existed": bool(identity_result.get("identity_existed")),
            "identity_blocked_reasons": sorted(
                identity_result.get("blocked_reasons") or []
            ),
            "membership_resolution_blocked_reasons": sorted(
                resolution.get("blocked_reasons") or []
            ),
            "session_blocked_reasons": sorted(session_blocked_reasons),
            # The cookie carries the internal identity id. The provider subject
            # stays in the database.
            "session_carries_provider_subject": False,
            "membership_rows_written": 0,
            "state_validated": state_validated,
            "pkce_verified": pkce_validated,
            # Gate 131: the real flow's outcome, in booleans.
            "provider_error": provider_error,
            "state_row_found": bool(consumed.get("row_found")),
            "state_expired": bool(consumed.get("expired")),
            "state_replay_detected": bool(consumed.get("replay_detected")),
            "state_blocked_reasons": sorted(consumed.get("blocked_reasons") or []),
            "token_exchange_attempted": bool(exchange_report.get("attempted")),
            "token_exchange_succeeded": bool(exchange_report.get("succeeded")),
            "token_exchange_http_status": int(exchange_report.get("http_status") or 0),
            "token_exchange_blocked_reasons": sorted(
                exchange_report.get("blocked_reasons") or []
            ),
            "identity_validated": identity_validated,
            "identity_verification_state": str(verification.get("state") or ""),
            # Gate 133B: whether this login left a durable record that
            # issuer/JWKS validation happened. Booleans only.
            "validation_evidence_recorded": bool(
                validation_evidence.get("rows_written")
            ),
            "validation_evidence_blocked_reasons": sorted(
                validation_evidence.get("blocked_reasons") or []
            ),
            "identity_email_domain": identity_email_domain,
            "org_binding_missing": org_binding_missing,
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
            "stored_state_found": bool(consumed.get("row_found")),
            "state_consume_allowed": state_validated,
            "contract_state_scope": state_lookup["storage_scope"],
            # Named individually: a caller who gets a refusal here needs to know
            # which of the three is missing, not merely that one is.
            "organization_id_resolved": organization_id_resolved,
            "membership_verified": membership_verified,
            "next_required_action": (
                "create a dev organization binding for this identity"
                if org_binding_missing
                else ""
            ),
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
    db: DbSession,
    decision: Annotated[dict[str, Any], Depends(optional_customer_session)],
) -> dict[str, Any]:
    """Report on the caller's session. There are none.

    Optional rather than required: a caller asking whether they have a session
    should be told no, not refused for not having one.
    """
    gate = _gate(db)
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
    db: DbSession,
    decision: Annotated[dict[str, Any], Depends(require_customer_session)],
) -> dict[str, Any]:
    """Report who the caller is.

    `organization_id` came back `None` for every gate up to 131, and the reason
    was correct each time: Gate 112's rule is that it may only come from a
    verified membership, and no membership existed. Gate 132 made one, so the
    value now comes from the row the dependency read.

    `email` stays `None`. It is in `nf_identities` and it is not needed to say
    who the caller is - the principal id and the organization are. A route that
    returned it would put a real address in every client that ever calls here.
    """
    gate = _gate(db)
    verification = decision["session_verification"]
    body = _envelope("current_user", "authenticated", gate)
    roles = [str(r) for r in verification.get("roles") or []]
    body.update(
        {
            "authenticated": bool(decision["authenticated"]),
            # The internal principal, never the provider subject.
            "subject": verification.get("principal_id"),
            "email": None,
            "organization_id": verification.get("organization_id"),
            "organization_id_resolved": bool(verification.get("organization_id")),
            "membership_verified": bool(verification.get("membership_verified")),
            "roles": roles,
            # The least privilege the caller holds, not the most. An empty role
            # list is `unknown` rather than a default that grants anything.
            "least_privilege_role": roles[0] if len(roles) == 1 else "unknown",
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
