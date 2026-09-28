"""Organization-wide Mission Control: derived work across pursuits."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    SESSION_COOKIE_NAME,
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)
from nativeforge.services.mission_control_service import (
    assemble_mission_control,
    membership_id_for_identity,
)

demo_mission_router = APIRouter(
    prefix="/v1/nf/demo/orgs", tags=["mission-control-demo"]
)
real_mission_router = APIRouter(
    prefix="/v1/nf/real/orgs", tags=["mission-control-real"]
)


def _viewer_membership(
    db: Session, org: OrgContext, cookie: str | None
) -> uuid.UUID | None:
    parsed = verify_session_cookie(cookie_value=cookie, membership_verified=False)
    if not parsed.get("session_cookie_valid"):
        return None
    return membership_id_for_identity(
        connection=db.connection(),
        organization_id=org.org_id,
        identity_id=parsed.get("principal_id"),
    )


def _read(
    org_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
    cookie: str | None,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    return assemble_mission_control(
        session=db,
        organization_id=ctx.org_id,
        viewer_membership_id=_viewer_membership(db, ctx, cookie),
    )


@demo_mission_router.get("/{org_id}/mission-control")
def demo_mission(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _read(org_id, ctx, db, nf_session)


@real_mission_router.get("/{org_id}/mission-control")
def real_mission(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _read(org_id, ctx, db, nf_session)
