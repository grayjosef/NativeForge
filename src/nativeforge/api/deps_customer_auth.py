"""Auth-claim-guarded organization context dependencies (Gate 122C).

The replacement for `deps_db.get_org_context_with_db`, added **beside** it
rather than over it.

## Why beside

Fourteen route modules depend on the dev-header chain. Converting any of them
today would return 401 to every caller, because the only claim source the RLS
guard trusts is `verified_auth_claim`, and producing one needs customer auth —
which Gate 121 measured as eleven activation gates away with zero code-only
blockers.

```text
convert now  ->  14 route modules unreachable
             ->  no safety gained: the frontend calls the API zero times, so
                 no customer can reach them anyway
```

So this module exists, is tested, and is imported by no route yet. Gate 122A
records the fourteen and why each stays.

## Three dependencies

```text
get_customer_org_context_required   a verified session, or 401
get_customer_org_context_optional   a verified session, or no org context
get_dev_org_context_explicit_only   X-NF-Org-Id, refused in production
```

The third is named for what it is. The current behaviour is the same posture
reached by accident — `nf_dev_org_headers` defaults true and nobody turned it
off — and the difference between this and that is a decision.

## optional never fabricates an organization

The failure mode worth guarding is not a route that refuses too much. It is a
route that, finding no session, substitutes a default organization so the page
renders. `get_customer_org_context_optional` returns `None`, and a route that
gets `None` renders nothing scoped to anybody.

## Nothing here sets the RLS context

`apply_org_rls_gucs` is deliberately not called. The decision is made here and
the GUCs are applied by whatever ends up owning the session — which is a
separate change, in a gate where a session can actually exist. A dependency
contract that set `app.current_org_id` on the strength of a decision nobody had
acted on would be the same defect this campaign keeps finding, one layer lower.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import Cookie, Header, HTTPException, status

from nativeforge.api.org_context import OrgContext
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.lib.settings import get_settings
from nativeforge.services.customer_auth_org_context_dependency_service import (
    DEV_HEADER_NAME,
    evaluate_org_context,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)

# The cookie a session would arrive in. Bridged from Gate 116's policy.
SESSION_COOKIE_NAME = "nf_session"

# Environments where the dev header may be honoured at all. `production` is
# absent on purpose, and so is `unknown`: a deployment that cannot say what it
# is does not get the convenience.
NON_PRODUCTION_ENVIRONMENTS = frozenset({"local", "dev", "test"})


def _production_context() -> bool:
    """Is this deployment production? Unknown counts as production.

    Deny by default at the level that matters most: a misconfigured `app_env`
    should tighten the posture, not loosen it.
    """
    return str(get_settings().app_env or "").strip().lower() not in (
        NON_PRODUCTION_ENVIRONMENTS
    )


def evaluate_request_org_context(
    *,
    mode: str,
    session_cookie: str | None,
    dev_header: str | None,
) -> dict[str, Any]:
    """Verify the cookie, then ask the contract what this request may do.

    The verification is passed whole rather than as individual booleans, so a
    caller cannot assert a session the verifier did not find.
    """
    verification = verify_session_cookie(
        cookie_value=session_cookie,
        # A membership record is a database question this dependency does not
        # ask. Gate 118 established that passing False deliberately is more
        # honest than omitting it.
        membership_verified=False,
    )
    settings = get_settings()
    return evaluate_org_context(
        dependency_mode=mode,
        session_verification=verification,
        dev_header_value=dev_header,
        dev_header_setting_enabled=bool(settings.nf_dev_org_headers),
        production_context=_production_context(),
    )


def _org_context_from(decision: dict) -> OrgContext | None:
    """An OrgContext, or None. Never a fabricated organization."""
    organization_id = decision.get("organization_id")
    if not organization_id:
        return None
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, TypeError):
        return None
    # Demo-vs-real is a property of the organizations row, which this dependency
    # does not read. `real` is the safe assumption: it is the stricter of the
    # two everywhere `require_demo_org_db` and `require_real_org_db` disagree.
    org_type: OrgType = "real"
    return OrgContext(org_id=oid, org_type=org_type)


def get_customer_org_context_required(
    nf_session: Annotated[str | None, Cookie()] = None,
) -> OrgContext:
    """A verified organization context, or 401.

    Refuses today for everybody, because no session can verify while no signing
    key is configured. The refusal names why rather than being a bare 401.
    """
    decision = evaluate_request_org_context(
        mode="required", session_cookie=nf_session, dev_header=None
    )
    context = _org_context_from(decision)
    if not decision["org_context_available"] or context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "no_verified_organization_context",
                "blocked_reasons": decision["blocked_reasons"],
                "dependency_mode": decision["dependency_mode"],
            },
            headers={"WWW-Authenticate": "Cookie"},
        )
    return context


def get_customer_org_context_optional(
    nf_session: Annotated[str | None, Cookie()] = None,
) -> OrgContext | None:
    """A verified organization context, or None.

    None, never a default organization. A route that receives None renders
    nothing scoped to anybody, which is correct and looks empty.
    """
    decision = evaluate_request_org_context(
        mode="optional", session_cookie=nf_session, dev_header=None
    )
    if not decision["org_context_available"]:
        return None
    return _org_context_from(decision)


def get_dev_org_context_explicit_only(
    x_nf_org_id: Annotated[str | None, Header(alias=DEV_HEADER_NAME)] = None,
) -> OrgContext:
    """A dev-only organization context selected by header.

    Refused in production with 403, and when the setting is off with 503. The
    header is a convenience for an operator with curl; it is not authentication
    and `production_safe` is false on every result it produces.
    """
    decision = evaluate_request_org_context(
        mode="dev_demo_explicit", session_cookie=None, dev_header=x_nf_org_id
    )
    context = _org_context_from(decision)
    if not decision["dev_org_context_available"] or context is None:
        raise HTTPException(
            status_code=decision["http_status"],
            detail={
                "error": "no_dev_organization_context",
                "blocked_reasons": decision["blocked_reasons"],
                "dependency_mode": decision["dependency_mode"],
                "production_context": decision["production_context"],
            },
        )
    return context
