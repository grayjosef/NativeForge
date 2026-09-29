"""Customer member directory and invite issue. Session-backed, no mail."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.commercial_entitlement_dependency import (
    require_substantive_commercial_benefit,
)
from nativeforge.api.customer_org_context_dependency import (
    SESSION_COOKIE_NAME,
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.customer_membership_directory_service import (
    list_organization_people,
)
from nativeforge.services.customer_membership_invite_issue_service import (
    issue_customer_invite,
)
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)

demo_membership_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["customer-membership-demo"],
)
real_membership_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["customer-membership-real"],
)

_demo_invite, _real_invite = require_substantive_commercial_benefit("INVITE_MEMBERS")


class IssueInviteBody(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str | None = None


def _viewer_id(cookie: str | None) -> str | None:
    parsed = verify_session_cookie(cookie_value=cookie, membership_verified=False)
    if not parsed.get("session_cookie_valid"):
        return None
    principal = parsed.get("principal_id")
    return str(principal) if principal else None


def _people(
    org_id: UUID,
    ctx: OrgContext,
    db: Session,
    cookie: str | None,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    return list_organization_people(
        connection=db.connection(),
        organization_id=ctx.org_id,
        viewer_identity_id=_viewer_id(cookie),
    )


def _issue(
    org_id: UUID,
    ctx: OrgContext,
    db: Session,
    cookie: str | None,
    body: IssueInviteBody,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    viewer = _viewer_id(cookie)
    if not viewer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "no_verified_session", "email_recorded": False},
        )
    result = issue_customer_invite(
        connection=db.connection(),
        organization_id=ctx.org_id,
        requested_by=viewer,
        invited_email=body.email,
        requested_role=body.role,
    )
    if result.get("issued"):
        db.commit()
    else:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result,
        )
    return result


@demo_membership_router.get("/{org_id}/members")
def demo_members(
    org_id: UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _people(org_id, ctx, db, nf_session)


@real_membership_router.get("/{org_id}/members")
def real_members(
    org_id: UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _people(org_id, ctx, db, nf_session)


@demo_membership_router.post("/{org_id}/invites")
def demo_issue_invite(
    org_id: UUID,
    body: IssueInviteBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    _benefit: Annotated[dict[str, Any], Depends(_demo_invite)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _issue(org_id, ctx, db, nf_session, body)


@real_membership_router.post("/{org_id}/invites")
def real_issue_invite(
    org_id: UUID,
    body: IssueInviteBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    _benefit: Annotated[dict[str, Any], Depends(_real_invite)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _issue(org_id, ctx, db, nf_session, body)
