"""Sprint 0 — demo/real isolated review-artifact API (minimal foundation)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import nativeforge.services.review_gate_service as rg
from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import review_artifacts as ra_repo


class ReviewArtifactOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_demo: bool
    artifact_type: str
    review_status: str


class AuditEventOut(BaseModel):
    id: uuid.UUID
    action: str
    payload: dict | None
    actor_id: uuid.UUID | None


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _artifact_out(art) -> ReviewArtifactOut:
    return ReviewArtifactOut(
        id=art.id,
        organization_id=art.organization_id,
        is_demo=art.is_demo,
        artifact_type=art.artifact_type,
        review_status=art.review_status,
    )


def _gate_error(e: rg.ReviewGateError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(e),
    )


# Demo-only router
demo_router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["sprint0-demo"])


@demo_router.post("/{org_id}/review-artifacts", response_model=ReviewArtifactOut)
def demo_create_artifact(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> ReviewArtifactOut:
    _same_org(org_id, ctx)
    org = rg.load_org(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    art = ra_repo.create_review_artifact(db, org=org, actor_id=actor_id)
    db.commit()
    db.refresh(art)
    return _artifact_out(art)


@demo_router.get("/{org_id}/review-artifacts", response_model=list[ReviewArtifactOut])
def demo_list_artifacts(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[ReviewArtifactOut]:
    _same_org(org_id, ctx)
    arts = ra_repo.list_review_artifacts(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [_artifact_out(a) for a in arts]


@demo_router.post("/{org_id}/review-artifacts/{artifact_id}/request-review")
def demo_request_review(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, str]:
    _same_org(org_id, ctx)
    try:
        rg.request_review(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            artifact_id=artifact_id,
            actor_id=actor_id,
        )
        db.commit()
    except rg.ReviewGateError as e:
        raise _gate_error(e) from e
    return {"status": "pending_review"}


@demo_router.post("/{org_id}/review-artifacts/{artifact_id}/approve")
def demo_approve(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, str]:
    _same_org(org_id, ctx)
    try:
        rg.approve(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            artifact_id=artifact_id,
            actor_id=actor_id,
        )
        db.commit()
    except rg.ReviewGateError as e:
        raise _gate_error(e) from e
    return {"status": "approved"}


@demo_router.post("/{org_id}/review-artifacts/{artifact_id}/reject")
def demo_reject(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, str]:
    _same_org(org_id, ctx)
    try:
        rg.reject(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            artifact_id=artifact_id,
            actor_id=actor_id,
        )
        db.commit()
    except rg.ReviewGateError as e:
        raise _gate_error(e) from e
    return {"status": "rejected"}


@demo_router.post("/{org_id}/review-artifacts/{artifact_id}/finalize")
def demo_finalize(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, str]:
    _same_org(org_id, ctx)
    try:
        rg.finalize(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            artifact_id=artifact_id,
            actor_id=actor_id,
        )
        db.commit()
    except rg.ReviewGateError as e:
        raise _gate_error(e) from e
    return {"status": "finalized"}


@demo_router.get(
    "/{org_id}/review-artifacts/{artifact_id}/audit-events",
    response_model=list[AuditEventOut],
)
def demo_list_audit(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[AuditEventOut]:
    _same_org(org_id, ctx)
    evs = ra_repo.list_audit_events_for_artifact(
        db,
        artifact_id=artifact_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    return [
        AuditEventOut(id=e.id, action=e.action, payload=e.payload, actor_id=e.actor_id)
        for e in evs
    ]


# Real-org router (same minimal surface; separate HTTP gate per Layer 3)
real_router = APIRouter(prefix="/v1/nf/real/orgs", tags=["sprint0-real"])


@real_router.post("/{org_id}/review-artifacts", response_model=ReviewArtifactOut)
def real_create_artifact(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> ReviewArtifactOut:
    _same_org(org_id, ctx)
    org = rg.load_org(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    art = ra_repo.create_review_artifact(db, org=org, actor_id=actor_id)
    db.commit()
    db.refresh(art)
    return _artifact_out(art)


@real_router.get("/{org_id}/review-artifacts", response_model=list[ReviewArtifactOut])
def real_list_artifacts(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[ReviewArtifactOut]:
    _same_org(org_id, ctx)
    arts = ra_repo.list_review_artifacts(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [_artifact_out(a) for a in arts]


@real_router.post("/{org_id}/review-artifacts/{artifact_id}/finalize")
def real_finalize(
    org_id: uuid.UUID,
    artifact_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, str]:
    _same_org(org_id, ctx)
    try:
        rg.finalize(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            artifact_id=artifact_id,
            actor_id=actor_id,
        )
        db.commit()
    except rg.ReviewGateError as e:
        raise _gate_error(e) from e
    return {"status": "finalized"}
