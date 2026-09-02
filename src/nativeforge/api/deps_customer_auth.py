"""Auth-claim-guarded organization context dependencies (Gate 122C).

The replacement for `deps_db.get_org_context_with_db`, added **beside** it
rather than over it.

## Why beside

Fourteen route modules depended on the dev-header chain, and converting any of
them when this was written would have returned 401 to every caller: producing a
verified claim needed customer auth, which Gate 121 measured as eleven
activation gates away.

```text
convert then ->  14 route modules unreachable
             ->  no safety gained: the frontend called the API zero times, so
                 no customer could reach them anyway
```

## Gate 133: it is imported by a route now

Gate 132 built the two things this module was missing. A session can exist, an
identity can have a membership, and an organization knows whether it is demo or
real. So `isolation_routes` runs on these dependencies, and the count is
fifteen modules minus one.

The remaining fourteen are 207 routes the demo shell reaches with a header and
no cookie. Converting them is Gate 134's work and the plan is in
`docs/operations/703_GATE133_DEV_HEADER_KILL_PLAN.md`.

## Two upgrades this module needed first

```text
membership_verified   was hardcoded False. Gate 132 built the membership read,
                      so it is a database question now and gets asked.
org_type              was hardcoded "real" with the note that this dependency
                      does not read the organizations row. It reads it now, via
                      Gate 132's classifier, because a demo-org session
                      classified real is refused by every demo-only route.
```

Both needed a database session, so the two session-bearing dependencies take
one. `get_dev_org_context_explicit_only` does not: it authenticates nobody and
must not gain the ability to look anything up.

## Two dependencies

```text
get_customer_org_context_required   a verified session, or 401
get_customer_org_context_optional   a verified session, or no org context
```

There was a third, `get_dev_org_context_explicit_only`, which took
`X-NF-Org-Id` and refused it in production. Gate 122 added it to name the header
for what it was — a convenience for an operator with curl, not authentication.
Gate 135 deleted it: no route ever depended on it, and a function that reads the
header is one edit from a route trusting it again.

Nothing in this module reads a header now.

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

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps import get_db
from nativeforge.api.org_context import OrgContext
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.lib.settings import get_settings
from nativeforge.services.customer_auth_org_context_dependency_service import (
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
    db: Any = None,
) -> dict[str, Any]:
    """Verify the cookie, then ask the contract what this request may do.

    The verification is passed whole rather than as individual booleans, so a
    caller cannot assert a session the verifier did not find.

    ## Gate 133: the membership question gets asked

    It used to be `membership_verified=False`, hardcoded, with the reason
    recorded: a membership record is a database question this dependency does
    not ask. Gate 132 built the read path, so it asks - and the claimed
    organization has to be the one the membership resolves to. A cookie naming
    organization A held by a member of organization B is not a member of A, and
    accepting it because *some* membership exists is the cross-tenant read every
    RLS rule here is written against.

    Without a session there is nothing to look up, so the verifier is called
    once and the answer is no.
    """
    parsed = verify_session_cookie(
        cookie_value=session_cookie,
        membership_verified=False,
    )

    membership_verified = False
    resolution: dict[str, Any] = {}
    if db is not None and parsed["session_cookie_valid"] and parsed["principal_id"]:
        from nativeforge.services.identity_org_session_resolution_service import (
            resolve_session_organization,
        )

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
        verify_session_cookie(cookie_value=session_cookie, membership_verified=True)
        if membership_verified
        else parsed
    )

    settings = get_settings()
    decision = evaluate_org_context(
        dependency_mode=mode,
        session_verification=verification,
        dev_header_value=dev_header,
        dev_header_setting_enabled=bool(settings.nf_dev_org_headers),
        production_context=_production_context(),
    )
    return decision | {
        "membership_verified": membership_verified,
        "membership_blocked_reasons": sorted(resolution.get("blocked_reasons") or []),
    }


def _org_context_from(decision: dict, db: Any = None) -> OrgContext | None:
    """An OrgContext, or None. Never a fabricated organization.

    Gate 133: demo-vs-real is a property of the `organizations` row, and this
    used to assume `real` because the dependency did not read one. That was the
    safe assumption and it was also wrong for every demo session - a demo
    organization classified real is refused by every demo-only route, which is
    why this dependency could not be attached to one.

    Gate 132's classifier reads the row and derives `is_demo` from it. Without a
    connection the old assumption still applies, because guessing `demo` would
    be guessing in the permissive direction.
    """
    organization_id = decision.get("organization_id")
    if not organization_id:
        return None
    try:
        oid = uuid.UUID(str(organization_id))
    except (ValueError, TypeError):
        return None

    org_type: OrgType = "real"
    if db is not None:
        from nativeforge.services.demo_org_classification_service import (
            classify_organization,
        )

        try:
            classification = classify_organization(oid, connection=db.connection())
        except Exception:
            db.rollback()
            classification = {}
        if not classification.get("classification_available"):
            # An organization the classifier will not classify is one this
            # dependency will not hand out. Refusing beats defaulting.
            return None
        org_type = "demo" if classification.get("is_demo") else "real"

    return OrgContext(org_id=oid, org_type=org_type)


def get_customer_org_context_required(
    db: Annotated[Session, Depends(get_db)],
    nf_session: Annotated[str | None, Cookie()] = None,
) -> OrgContext:
    """A verified organization context, or 401.

    Refuses today for everybody, because no session can verify while no signing
    key is configured. The refusal names why rather than being a bare 401.
    """
    decision = evaluate_request_org_context(
        mode="required", session_cookie=nf_session, dev_header=None, db=db
    )
    context = _org_context_from(decision, db)
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
    db: Annotated[Session, Depends(get_db)],
    nf_session: Annotated[str | None, Cookie()] = None,
) -> OrgContext | None:
    """A verified organization context, or None.

    None, never a default organization. A route that receives None renders
    nothing scoped to anybody, which is correct and looks empty.
    """
    decision = evaluate_request_org_context(
        mode="optional", session_cookie=nf_session, dev_header=None, db=db
    )
    if not decision["org_context_available"]:
        return None
    return _org_context_from(decision, db)


def require_customer_demo_org(
    ctx: Annotated[OrgContext, Depends(get_customer_org_context_required)],
) -> OrgContext:
    """A verified session whose organization is a demo organization, or 403.

    The session-backed counterpart of `isolation_deps.require_demo_org`. The
    difference is where `org_type` comes from: that one reads the settings
    allowlist, this one reads the `organizations` row.
    """
    if ctx.org_type != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="demo-only route requires a demo organization",
        )
    return ctx


def require_customer_real_org(
    ctx: Annotated[OrgContext, Depends(get_customer_org_context_required)],
) -> OrgContext:
    """A verified session whose organization is a real organization, or 403."""
    if ctx.org_type != "real":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="real-data route requires a real (non-demo) organization",
        )
    return ctx
