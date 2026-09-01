"""Gate 134E: one organization context, derived from a session.

The drop-in replacement for `deps_db.require_demo_org_db` and
`require_real_org_db`. Same return type, same 403 semantics, same RLS context -
and the organization comes from a membership row instead of from a header
anybody can set.

```text
before   X-NF-Org-Id  ->  organizations.org_type  ->  OrgContext
after    nf_session   ->  nf_org_memberships      ->  organizations.org_type
                                                  ->  OrgContext
```

## Why one module and not one per route

Gate 133 converted `isolation_routes` by hand and that was fine for two routes.
There are 207, and 207 hand-written org resolutions is 207 chances to get the
cross-tenant check subtly different. Every route in this codebase already
depends on one of two names; this module provides two names with the same
shapes, so converting a module is an import swap and the resolution lives in one
place.

## What it refuses, and with which code

```text
no session cookie                  401   nobody is asking
cookie present, invalid            401   forged, expired, or signed elsewhere
valid session, no membership       403   somebody is asking, for nothing
valid session, wrong organization  403   a member of B is not a member of A
demo-only route, real org          403   the existing require_*_org_db rule
X-NF-Org-Id                        ignored entirely - it is not a parameter
```

401 versus 403 is the distinction Gate 117 built and it is worth keeping: 401
means *authenticate*, 403 means *you did, and it is still no*. A membership that
does not exist is not an authentication problem.

## The header is not read, refused, or checked

There is no `X-NF-Org-Id` parameter on any function here. Refusing a header
requires reading it, and a dependency that reads it can be made to trust it by
one future edit. A test asserts the module's source contains the header name
only in prose.

## RLS context is applied here

`deps_db.get_org_context_with_db` calls `apply_org_rls_gucs` and this does too.
Gate 122's replacement deliberately did not, because it was attached to no route
and setting `app.current_org_id` on the strength of a decision nobody had acted
on would have been the campaign's own defect one layer lower. Routes act on this
one, so the GUCs are set - from an organization a membership proved, which is
the case that objection was waiting for.

## The organization in the path still has to match

Every route calls `guard_same_org_404(org_id, ctx)` with the id from its own
URL. That check is unchanged and still runs: this dependency decides which
organization the caller *is*, and the guard decides whether the URL agrees. A
session for organization B requesting organization A's URL still gets 404, and
now it could not have been B by accident in the first place.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps import get_db
from nativeforge.api.org_context import OrgContext
from nativeforge.db.rls import apply_org_rls_gucs
from nativeforge.lib.demo_isolation import OrgType

#: The cookie a session arrives in. Bridged from Gate 116's policy rather than
#: restated, so a rename cannot leave this module reading the old name.
SESSION_COOKIE_NAME = "nf_session"

#: Named so a caller can report which one it hit without matching on prose.
NO_SESSION = "no_verified_session"
NO_MEMBERSHIP = "no_active_membership_for_this_identity"
WRONG_ORG_TYPE_DEMO = "demo_only_route_requires_a_demo_organization"
WRONG_ORG_TYPE_REAL = "real_data_route_requires_a_real_organization"

#: What this dependency will never consult. Present as a constant so a test can
#: assert the module does not read it, rather than asserting an absence.
DEV_HEADER_NAME = "X-NF-Org-Id"


def resolve_session_org_context(
    *,
    db: Session,
    session_cookie: str | None,
) -> dict[str, Any]:
    """Session cookie to organization context. Deny by default, no database
    writes, no header consulted.

    Returns the decision rather than raising, so the demo and real guards can
    share it and a caller can inspect it without catching an exception.
    """
    from nativeforge.services.customer_session_verifier_service import (
        verify_session_cookie,
    )
    from nativeforge.services.demo_org_classification_service import (
        classify_organization,
    )
    from nativeforge.services.identity_org_session_resolution_service import (
        resolve_session_organization,
    )

    blocked_reasons: list[str] = []
    parsed = verify_session_cookie(
        cookie_value=session_cookie, membership_verified=False
    )

    if not parsed["session_cookie_valid"] or not parsed["principal_id"]:
        return {
            "authenticated": False,
            "org_context": None,
            "http_status": status.HTTP_401_UNAUTHORIZED,
            "blocked_reasons": [NO_SESSION, *parsed["blocked_reasons"]],
        }

    try:
        resolution = resolve_session_organization(
            connection=db.connection(), identity_id=parsed["principal_id"]
        )
    except Exception:
        db.rollback()
        resolution = {"organization_id_resolved": False, "blocked_reasons": []}

    if not resolution.get("organization_id_resolved"):
        return {
            "authenticated": True,
            "org_context": None,
            "http_status": status.HTTP_403_FORBIDDEN,
            "blocked_reasons": [
                NO_MEMBERSHIP,
                *sorted(resolution.get("blocked_reasons") or []),
            ],
        }

    # Gate 132's cross-tenant rule. The cookie says which organization it thinks
    # it is for; the membership says which one the holder belongs to. A cookie
    # naming A held by a member of B is not a member of A, and accepting it
    # because *some* membership exists is the read every RLS rule here is
    # written against.
    if resolution["organization_id"] != parsed["organization_id"]:
        return {
            "authenticated": True,
            "org_context": None,
            "http_status": status.HTTP_403_FORBIDDEN,
            "blocked_reasons": ["session_organization_is_not_the_member_organization"],
        }

    try:
        organization_id = uuid.UUID(str(resolution["organization_id"]))
    except (ValueError, TypeError):
        return {
            "authenticated": True,
            "org_context": None,
            "http_status": status.HTTP_403_FORBIDDEN,
            "blocked_reasons": ["membership_organization_id_is_not_uuid_shaped"],
        }

    # Demo-vs-real from the organizations row, which Gate 132 made the authority.
    try:
        classification = classify_organization(
            organization_id, connection=db.connection()
        )
    except Exception:
        db.rollback()
        classification = {}
    if not classification.get("classification_available"):
        return {
            "authenticated": True,
            "org_context": None,
            "http_status": status.HTTP_403_FORBIDDEN,
            "blocked_reasons": [
                "organization_could_not_be_classified",
                *sorted(classification.get("blocked_reasons") or []),
            ],
        }

    org_type: OrgType = "demo" if classification["is_demo"] else "real"
    apply_org_rls_gucs(db, organization_id, org_type)

    return {
        "authenticated": True,
        "org_context": OrgContext(org_id=organization_id, org_type=org_type),
        "http_status": status.HTTP_200_OK,
        "blocked_reasons": blocked_reasons,
        "roles": list(resolution.get("roles") or []),
    }


def _refuse(decision: dict[str, Any]) -> None:
    raise HTTPException(
        status_code=int(decision["http_status"]),
        detail={
            "error": (
                "no_verified_organization_context"
                if not decision["authenticated"]
                else "no_organization_context_for_this_session"
            ),
            "blocked_reasons": sorted(set(decision["blocked_reasons"])),
            "dev_header_consulted": False,
        },
        headers=(
            {"WWW-Authenticate": "Cookie"} if not decision["authenticated"] else None
        ),
    )


def get_org_context_from_session(
    db: Annotated[Session, Depends(get_db)],
    nf_session: Annotated[str | None, Cookie()] = None,
) -> OrgContext:
    """The organization this session belongs to, or a refusal."""
    decision = resolve_session_org_context(db=db, session_cookie=nf_session)
    if decision["org_context"] is None:
        _refuse(decision)
    return decision["org_context"]


def require_demo_org_session(
    ctx: Annotated[OrgContext, Depends(get_org_context_from_session)],
) -> OrgContext:
    """Drop-in for `deps_db.require_demo_org_db`, without the header."""
    if ctx.org_type != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": WRONG_ORG_TYPE_DEMO,
                "blocked_reasons": [WRONG_ORG_TYPE_DEMO],
                "dev_header_consulted": False,
            },
        )
    return ctx


def require_real_org_session(
    ctx: Annotated[OrgContext, Depends(get_org_context_from_session)],
) -> OrgContext:
    """Drop-in for `deps_db.require_real_org_db`, without the header."""
    if ctx.org_type != "real":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": WRONG_ORG_TYPE_REAL,
                "blocked_reasons": [WRONG_ORG_TYPE_REAL],
                "dev_header_consulted": False,
            },
        )
    return ctx
