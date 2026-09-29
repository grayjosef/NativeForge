"""Gate 179: canonical-backed customer opportunity feed + decisions."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.commercial_entitlement_dependency import (
    require_substantive_commercial_benefit,
)
from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.customer_canonical_feed_assembler_service import (
    assemble_customer_opportunity_feed,
)
from nativeforge.services.customer_decision_repository_service import (
    load_current_decision,
    persist_decision,
)
from nativeforge.services.customer_decision_service import apply_decision

_demo_mut_benefit, _real_mut_benefit = require_substantive_commercial_benefit(
    "OPEN_PURSUIT"
)

demo_feed_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["customer-opportunity-feed-demo"],
)
real_feed_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["customer-opportunity-feed-real"],
)


class CustomerDecisionBody(BaseModel):
    canonical_id: str = Field(min_length=1, max_length=256)
    to_state: str = Field(min_length=2, max_length=16)
    reason: str | None = Field(default=None, max_length=4096)
    actor_id: str = Field(min_length=1, max_length=128)


def _feed_handler(
    *,
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
    limit: int,
    offset: int,
    ordering: str,
    include_dismissed: bool,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    org_key = str(ctx.org_id)
    payload = assemble_customer_opportunity_feed(
        session.connection(),
        organization_id=org_key,
        tenant_id=org_key,
        limit=limit,
        offset=offset,
        ordering=ordering,
        include_dismissed=include_dismissed,
    )
    return payload


@demo_feed_router.get("/{org_id}/discovery/customer-opportunity-feed")
def demo_customer_opportunity_feed(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ordering: str = Query(default="DEADLINE_SOONEST"),
    include_dismissed: bool = Query(default=False),
) -> dict[str, Any]:
    return _feed_handler(
        org_id=org_id,
        ctx=ctx,
        session=session,
        limit=limit,
        offset=offset,
        ordering=ordering,
        include_dismissed=include_dismissed,
    )


@real_feed_router.get("/{org_id}/discovery/customer-opportunity-feed")
def real_customer_opportunity_feed(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ordering: str = Query(default="DEADLINE_SOONEST"),
    include_dismissed: bool = Query(default=False),
) -> dict[str, Any]:
    return _feed_handler(
        org_id=org_id,
        ctx=ctx,
        session=session,
        limit=limit,
        offset=offset,
        ordering=ordering,
        include_dismissed=include_dismissed,
    )


def _decision_handler(
    *,
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
    body: CustomerDecisionBody,
    is_demo: bool,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    org_key = str(ctx.org_id)
    current_row = load_current_decision(
        session.connection(),
        organization_id=org_key,
        canonical_id=body.canonical_id,
    )
    current = (
        {
            "decision_state": current_row.get("decision_state"),
            "previous_state": current_row.get("previous_state"),
            "actor_id": current_row.get("actor_id"),
            "decided_at": current_row.get("decided_at"),
            "reason": current_row.get("reason"),
            "organization_id": org_key,
            "canonical_id": body.canonical_id,
            "model_version": current_row.get("model_version"),
        }
        if current_row
        else None
    )
    result = apply_decision(
        current=current,
        organization_id=org_key,
        canonical_id=body.canonical_id,
        to_state=body.to_state,
        actor_id=body.actor_id,
        decided_at=dt.datetime.now(dt.UTC).isoformat(),
        reason=body.reason,
    )
    if not result.get("accepted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "decision_refused", "why": result.get("why")},
        )
    persisted = persist_decision(
        session.connection(),
        decision=result["decision"],
        previous=current,
        is_demo=is_demo,
    )
    session.commit()
    return {
        "decision_result": result,
        "persisted": persisted,
        "global_intelligence_unchanged": True,
    }


@demo_feed_router.post("/{org_id}/discovery/customer-opportunity-decisions")
def demo_apply_customer_decision(
    org_id: uuid.UUID,
    body: CustomerDecisionBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    _benefit: Annotated[dict[str, Any], Depends(_demo_mut_benefit)] = None,
) -> dict[str, Any]:
    return _decision_handler(
        org_id=org_id, ctx=ctx, session=session, body=body, is_demo=True
    )


@real_feed_router.post("/{org_id}/discovery/customer-opportunity-decisions")
def real_apply_customer_decision(
    org_id: uuid.UUID,
    body: CustomerDecisionBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    _benefit: Annotated[dict[str, Any], Depends(_real_mut_benefit)] = None,
) -> dict[str, Any]:
    return _decision_handler(
        org_id=org_id, ctx=ctx, session=session, body=body, is_demo=False
    )
