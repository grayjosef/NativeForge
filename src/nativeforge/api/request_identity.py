"""FastAPI request identity resolution (Gate 59).

Resolves an identity for the request **without trusting the client for anything
that matters**.

What is read, and what it is worth:

===========================================  =====================================
Header                                       Trust
===========================================  =====================================
``Cf-Access-Authenticated-User-Email``       operator gate passed. NOT customer
                                             login, no org, no role.
``X-NF-Org-Id``                              demo/dev routing input ONLY. Never
                                             membership, authority or role proof.
``X-NF-Role`` / ``X-NF-Roles``               recorded as *asserted*, never
                                             trusted. Rejected outright in
                                             customer mode.
``Authorization: Bearer``                    presence recorded. NOT verified —
                                             no token verification path exists
                                             (see oidc_readiness_service).
===========================================  =====================================

`login_live` and `customer_login_live` are `False` here and cannot be set from
this module.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status

from nativeforge.services.oidc_readiness_service import build_oidc_readiness
from nativeforge.services.request_identity_service import (
    build_request_identity,
    evaluate_customer_action,
)

# Headers that assert a role. Recorded for audit, never trusted, and rejected
# outright when a caller asks for customer mode.
ROLE_ASSERTION_HEADERS = ("x-nf-role", "x-nf-roles", "x-nf-capability")


def resolve_request_identity(
    cf_access_email: Annotated[
        str | None, Header(alias="Cf-Access-Authenticated-User-Email")
    ] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_nf_role: Annotated[str | None, Header(alias="X-NF-Role")] = None,
    x_nf_roles: Annotated[str | None, Header(alias="X-NF-Roles")] = None,
) -> dict[str, Any]:
    """Resolve request identity. Never raises; deny decisions are separate.

    Available as a FastAPI dependency. Adding it to a route changes no
    behaviour on its own — it only makes a trustworthy identity available and
    records what the client asserted.
    """
    readiness = build_oidc_readiness()
    oidc_configured = bool(readiness.get("config_complete"))

    asserted_roles = [r for r in (x_nf_role, x_nf_roles) if r]

    bearer_present = bool(
        authorization and str(authorization).lower().startswith("bearer ")
    )

    if bearer_present:
        # A bearer token was supplied but there is no verification path, so it
        # cannot raise the identity above "configured but unverified" — and not
        # even that if OIDC is unconfigured.
        state = "oidc_configured_unverified" if oidc_configured else "oidc_unconfigured"
        return build_request_identity(
            identity_state=state,
            asserted_role_claims=asserted_roles,
            membership_source="client_asserted",
            verification_source="none",
            oidc_configured=oidc_configured,
        )

    if cf_access_email:
        identity = build_request_identity(
            identity_state="demo_operator",
            email=cf_access_email,
            email_verified=False,
            asserted_role_claims=asserted_roles,
            membership_source="none",
            verification_source="cloudflare_access",
            oidc_configured=oidc_configured,
        )
        return identity

    return build_request_identity(
        identity_state="anonymous",
        asserted_role_claims=asserted_roles,
        membership_source="none",
        verification_source="none",
        oidc_configured=oidc_configured,
    )


def reject_role_assertion_headers(headers: dict[str, str] | Any) -> None:
    """Reject a request that tries to assert its own role or capability.

    Silently ignoring such a header is safe but quiet; rejecting it makes a
    spoofing attempt visible instead of letting the caller believe it worked.
    """
    try:
        items = headers.items()
    except AttributeError:  # pragma: no cover - defensive
        return
    offenders = sorted(
        {k.lower() for k, _ in items if k.lower() in ROLE_ASSERTION_HEADERS}
    )
    if offenders:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "role and capability may not be supplied by the client: "
                + ", ".join(offenders)
            ),
        )


def require_customer_identity(
    identity: dict[str, Any], *, action: str = "customer_action"
) -> dict[str, Any]:
    """Require a trustworthy customer identity, else 403.

    Not attached to any live route in this gate. With no verifier implemented
    every identity is anonymous, demo_operator or unverified, so attaching this
    would deny every request — including the demo. See doc 376.
    """
    decision = evaluate_customer_action(identity=identity, action=action)
    if not decision.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="request identity is not a verified customer identity",
        )
    return decision


# ─────────────────── request-scoped identity for the tenant guard ───────────────────
# tenant_guard is called from handler bodies that have no access to headers, so
# threading identity through 205 call sites would be a large, risky diff. A
# contextvar lets the guard enrich its audit event when an identity has been
# resolved, and fall back to previous behaviour when it has not. Nothing depends
# on it being set.

import contextvars  # noqa: E402

_CURRENT_IDENTITY: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("nf_current_identity", default=None)
)


def set_current_identity(identity: dict[str, Any] | None) -> Any:
    """Set the request-scoped identity. Returns a token for reset()."""
    return _CURRENT_IDENTITY.set(identity)


def get_current_identity() -> dict[str, Any] | None:
    """Read the request-scoped identity, or None if none was resolved."""
    return _CURRENT_IDENTITY.get()


def reset_current_identity(token: Any) -> None:
    _CURRENT_IDENTITY.reset(token)


def identity_dependency(
    identity: Annotated[dict[str, Any], Depends(resolve_request_identity)],
) -> dict[str, Any]:
    """FastAPI dependency that resolves identity and publishes it to the guard."""
    set_current_identity(identity)
    return identity
