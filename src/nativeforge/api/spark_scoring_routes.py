"""Sprint 4 — deterministic Grant Spark scoring (pursuit-readiness)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import organizations as org_repo
from nativeforge.repositories import spark_scores as score_repo
from nativeforge.services import spark_scoring_service as sss


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


class ScoreOverrideBody(BaseModel):
    reason: str = Field(min_length=1, max_length=4096)
    spark_score_id: uuid.UUID | None = None


demo_spark_scoring_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["spark-scoring-demo"],
)
real_spark_scoring_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["spark-scoring-real"],
)


@demo_spark_scoring_router.post(
    "/{org_id}/grant-sparks/{spark_id}/score",
    status_code=status.HTTP_201_CREATED,
)
def demo_score_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = sss.run_deterministic_score(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except sss.GrantSparkNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (sss.TribalProfileRequiredError, sss.NofoExtractionRequiredError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sss.spark_score_to_dict(row)


@demo_spark_scoring_router.get("/{org_id}/grant-sparks/{spark_id}/score/latest")
def demo_score_latest(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)

    row = score_repo.get_latest_spark_score(
        session=db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="no score for this spark")
    return sss.spark_score_to_dict(row)


@demo_spark_scoring_router.post("/{org_id}/grant-sparks/{spark_id}/score/override")
def demo_score_override(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: ScoreOverrideBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    row = sss.apply_override(
        db,
        org=org,
        org_type=ctx.org_type,
        spark_id=spark_id,
        spark_score_id=body.spark_score_id,
        reason=body.reason,
        actor_id=actor_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="score not found for this spark")
    db.commit()
    db.refresh(row)
    return sss.spark_score_to_dict(row)


@real_spark_scoring_router.post(
    "/{org_id}/grant-sparks/{spark_id}/score",
    status_code=status.HTTP_201_CREATED,
)
def real_score_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = sss.run_deterministic_score(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except sss.GrantSparkNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (sss.TribalProfileRequiredError, sss.NofoExtractionRequiredError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sss.spark_score_to_dict(row)


@real_spark_scoring_router.get("/{org_id}/grant-sparks/{spark_id}/score/latest")
def real_score_latest(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)

    row = score_repo.get_latest_spark_score(
        session=db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="no score for this spark")
    return sss.spark_score_to_dict(row)


@real_spark_scoring_router.post("/{org_id}/grant-sparks/{spark_id}/score/override")
def real_score_override(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: ScoreOverrideBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    row = sss.apply_override(
        db,
        org=org,
        org_type=ctx.org_type,
        spark_id=spark_id,
        spark_score_id=body.spark_score_id,
        reason=body.reason,
        actor_id=actor_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="score not found for this spark")
    db.commit()
    db.refresh(row)
    return sss.spark_score_to_dict(row)
