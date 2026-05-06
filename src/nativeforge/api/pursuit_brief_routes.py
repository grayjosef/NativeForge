"""Sprint 9 — pursuit brief (deterministic grant engine output)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import pursuit_brief_service as pbsvc
from nativeforge.services.pursuit_service import PursuitNotFoundError


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _brief_exc(e: Exception) -> None:
    if isinstance(e, pbsvc.GrantSparkNotFoundError):
        raise HTTPException(status_code=404, detail=str(e)) from e
    if isinstance(e, PursuitNotFoundError):
        raise HTTPException(status_code=404, detail=str(e)) from e
    if isinstance(e, pbsvc.PursuitMismatchError):
        raise HTTPException(status_code=400, detail=str(e)) from e
    if isinstance(e, pbsvc.PursuitBriefNotFoundError):
        raise HTTPException(status_code=404, detail=str(e)) from e
    raise e


_OPTIONAL_PURSUITS_QUERY = Query(
    default=None,
    description="Optional pursuit; must belong to this Grant Spark.",
)

demo_pursuit_brief_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["pursuit-brief-demo"],
)
real_pursuit_brief_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["pursuit-brief-real"],
)


@demo_pursuit_brief_router.post(
    "/{org_id}/grant-sparks/{spark_id}/pursuit-brief",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_pursuit_brief(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    pursuit_id: uuid.UUID | None = _OPTIONAL_PURSUITS_QUERY,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    pid = pursuit_id
    try:
        row = pbsvc.generate_pursuit_brief(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            pursuit_id_explicit=pid,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        pbsvc.GrantSparkNotFoundError,
        PursuitNotFoundError,
        pbsvc.PursuitMismatchError,
    ) as e:
        db.rollback()
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)


@demo_pursuit_brief_router.get(
    "/{org_id}/grant-sparks/{spark_id}/pursuit-brief/latest",
)
def demo_get_latest_pursuit_brief_for_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = pbsvc.get_latest_by_spark(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            spark_id=spark_id,
        )
    except pbsvc.PursuitBriefNotFoundError as e:
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)


@demo_pursuit_brief_router.get(
    "/{org_id}/pursuits/{pursuit_id}/pursuit-brief/latest",
)
def demo_get_latest_pursuit_brief_for_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = pbsvc.get_latest_by_pursuit(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except pbsvc.PursuitBriefNotFoundError as e:
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)


@real_pursuit_brief_router.post(
    "/{org_id}/grant-sparks/{spark_id}/pursuit-brief",
    status_code=status.HTTP_201_CREATED,
)
def real_create_pursuit_brief(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    pursuit_id: uuid.UUID | None = _OPTIONAL_PURSUITS_QUERY,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    pid = pursuit_id
    try:
        row = pbsvc.generate_pursuit_brief(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            pursuit_id_explicit=pid,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        pbsvc.GrantSparkNotFoundError,
        PursuitNotFoundError,
        pbsvc.PursuitMismatchError,
    ) as e:
        db.rollback()
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)


@real_pursuit_brief_router.get(
    "/{org_id}/grant-sparks/{spark_id}/pursuit-brief/latest",
)
def real_get_latest_pursuit_brief_for_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = pbsvc.get_latest_by_spark(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            spark_id=spark_id,
        )
    except pbsvc.PursuitBriefNotFoundError as e:
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)


@real_pursuit_brief_router.get(
    "/{org_id}/pursuits/{pursuit_id}/pursuit-brief/latest",
)
def real_get_latest_pursuit_brief_for_pursuit(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = pbsvc.get_latest_by_pursuit(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except pbsvc.PursuitBriefNotFoundError as e:
        _brief_exc(e)
    return pbsvc.pursuit_brief_to_dict(row)
