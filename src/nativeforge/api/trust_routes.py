"""Sprint 7 — sovereignty / trust surface + org data export."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import trust_surface_service as tss


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


demo_trust_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["trust-demo"],
)
real_trust_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["trust-real"],
)


@demo_trust_router.get("/{org_id}/trust/manifest")
def demo_trust_manifest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return tss.build_trust_manifest(org_type=ctx.org_type)


@demo_trust_router.get("/{org_id}/trust/audit-events")
def demo_audit_events(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = audit_repo.list_audit_events_for_org(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        limit=limit,
    )
    return {
        "limit": limit,
        "events": [audit_repo.audit_event_to_dict(e) for e in rows],
    }


@demo_trust_router.get("/{org_id}/trust/review-summary")
def demo_review_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return tss.build_review_gate_summary(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )


@demo_trust_router.get("/{org_id}/export/org-data-snapshot")
def demo_org_export(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_sf424_previews: bool = False,
    audit_sample_limit: Annotated[int, Query(ge=1, le=500)] = 100,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    snap = tss.export_org_data_snapshot(
        db,
        org=org,
        org_type=ctx.org_type,
        actor_id=actor_id,
        include_sf424_previews=include_sf424_previews,
        audit_event_sample_limit=audit_sample_limit,
    )
    db.commit()
    return snap


@real_trust_router.get("/{org_id}/trust/manifest")
def real_trust_manifest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return tss.build_trust_manifest(org_type=ctx.org_type)


@real_trust_router.get("/{org_id}/trust/audit-events")
def real_audit_events(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = audit_repo.list_audit_events_for_org(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        limit=limit,
    )
    return {
        "limit": limit,
        "events": [audit_repo.audit_event_to_dict(e) for e in rows],
    }


@real_trust_router.get("/{org_id}/trust/review-summary")
def real_review_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return tss.build_review_gate_summary(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )


@real_trust_router.get("/{org_id}/export/org-data-snapshot")
def real_org_export(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_sf424_previews: bool = False,
    audit_sample_limit: Annotated[int, Query(ge=1, le=500)] = 100,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    snap = tss.export_org_data_snapshot(
        db,
        org=org,
        org_type=ctx.org_type,
        actor_id=actor_id,
        include_sf424_previews=include_sf424_previews,
        audit_event_sample_limit=audit_sample_limit,
    )
    db.commit()
    return snap
