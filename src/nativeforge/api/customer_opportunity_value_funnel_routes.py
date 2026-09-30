"""Org-scoped opportunity value funnel (Gate 174 / pursuits)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.opportunity_value_funnel_service import (
    compute_org_funnel_aggregate,
)

demo_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["opportunity-value-funnel-demo"],
)
real_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["opportunity-value-funnel-real"],
)


def _org_funnel(
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    org_key = str(ctx.org_id)
    return compute_org_funnel_aggregate(
        session.connection(),
        organization_id=org_key,
        tenant_id=org_key,
    )


@demo_router.get("/{org_id}/intelligence/opportunity-value-funnel")
def demo_org_opportunity_value_funnel(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _org_funnel(org_id, ctx, session)


@real_router.get("/{org_id}/intelligence/opportunity-value-funnel")
def real_org_opportunity_value_funnel(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _org_funnel(org_id, ctx, session)
