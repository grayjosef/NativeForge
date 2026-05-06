"""Sprint 2 — Grant Spark routes (DB-backed org context)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
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
from nativeforge.domain.enums import (
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
)
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import grant_spark_service as gss
from nativeforge.services.grant_spark_service import DuplicateGrantSparkError


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _dec(v: float | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(str(v))


class GrantSparkBody(BaseModel):
    source: GrantSparkSource
    source_id: str = Field(min_length=1, max_length=256)
    agency: str = Field(min_length=1, max_length=512)
    opportunity_title: str = Field(min_length=1, max_length=512)
    award_type: GrantAwardType
    sub_agency: str | None = Field(default=None, max_length=512)
    program_name: str | None = Field(default=None, max_length=512)
    opportunity_number: str | None = Field(default=None, max_length=128)
    cfda_assistance_listing: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    funding_floor: float | None = None
    funding_ceiling: float | None = None
    total_program_funding: float | None = None
    expected_awards: int | None = None
    match_required: bool = False
    match_percent: float | None = None
    match_waiver_available: bool = False
    indirect_cost_allowable: bool = True
    posted_date: date | None = None
    loi_deadline: datetime | None = None
    application_deadline: datetime | None = None
    performance_period_start: date | None = None
    performance_period_end: date | None = None
    raw_nofo_text: str | None = None
    raw_nofo_url: str | None = Field(default=None, max_length=2048)
    eligibility_tags: list[str] | None = None
    tribal_eligible: bool = False
    pipeline_stage: GrantPipelineStage = GrantPipelineStage.new


def _body_to_payload(body: GrantSparkBody) -> gss.GrantSparkPayload:
    return gss.GrantSparkPayload(
        source=body.source,
        source_id=body.source_id,
        agency=body.agency,
        opportunity_title=body.opportunity_title,
        award_type=body.award_type,
        sub_agency=body.sub_agency,
        program_name=body.program_name,
        opportunity_number=body.opportunity_number,
        cfda_assistance_listing=body.cfda_assistance_listing,
        url=body.url,
        funding_floor=_dec(body.funding_floor),
        funding_ceiling=_dec(body.funding_ceiling),
        total_program_funding=_dec(body.total_program_funding),
        expected_awards=body.expected_awards,
        match_required=body.match_required,
        match_percent=_dec(body.match_percent),
        match_waiver_available=body.match_waiver_available,
        indirect_cost_allowable=body.indirect_cost_allowable,
        posted_date=body.posted_date,
        loi_deadline=body.loi_deadline,
        application_deadline=body.application_deadline,
        performance_period_start=body.performance_period_start,
        performance_period_end=body.performance_period_end,
        raw_nofo_text=body.raw_nofo_text,
        raw_nofo_url=body.raw_nofo_url,
        eligibility_tags=body.eligibility_tags,
        tribal_eligible=body.tribal_eligible,
        pipeline_stage=body.pipeline_stage,
    )


demo_grant_spark_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["grant-sparks-demo"],
)
real_grant_spark_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["grant-sparks-real"],
)


@demo_grant_spark_router.post("/{org_id}/grant-sparks/seed-demo-catalog")
def demo_seed_catalog(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, int]:
    """Insert the 12 deterministic demo Sparks for this org (idempotent)."""
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        result = gss.seed_demo_catalog(db, org=org)
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@demo_grant_spark_router.get("/{org_id}/grant-sparks")
def demo_list_sparks(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = gss.list_sparks(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [gss.spark_to_dict(r) for r in rows]


@demo_grant_spark_router.post(
    "/{org_id}/grant-sparks",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_spark(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: GrantSparkBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = gss.create_grant_spark(db, org=org, body=_body_to_payload(body))
        db.commit()
        db.refresh(row)
    except DuplicateGrantSparkError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="grant spark already exists for this source and source_id",
        ) from None
    return gss.spark_to_dict(row)


@demo_grant_spark_router.get("/{org_id}/grant-sparks/{spark_id}")
def demo_get_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = gss.get_spark(db, org_id=ctx.org_id, org_type=ctx.org_type, spark_id=spark_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    return gss.spark_to_dict(row)


@demo_grant_spark_router.put("/{org_id}/grant-sparks/{spark_id}")
def demo_put_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: GrantSparkBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = gss.update_grant_spark(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        spark_id=spark_id,
        body=_body_to_payload(body),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    db.commit()
    db.refresh(row)
    return gss.spark_to_dict(row)


@real_grant_spark_router.get("/{org_id}/grant-sparks")
def real_list_sparks(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = gss.list_sparks(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [gss.spark_to_dict(r) for r in rows]


@real_grant_spark_router.post(
    "/{org_id}/grant-sparks",
    status_code=status.HTTP_201_CREATED,
)
def real_create_spark(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: GrantSparkBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = gss.create_grant_spark(db, org=org, body=_body_to_payload(body))
        db.commit()
        db.refresh(row)
    except DuplicateGrantSparkError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="grant spark already exists for this source and source_id",
        ) from None
    return gss.spark_to_dict(row)


@real_grant_spark_router.get("/{org_id}/grant-sparks/{spark_id}")
def real_get_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = gss.get_spark(db, org_id=ctx.org_id, org_type=ctx.org_type, spark_id=spark_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    return gss.spark_to_dict(row)


@real_grant_spark_router.put("/{org_id}/grant-sparks/{spark_id}")
def real_put_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: GrantSparkBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = gss.update_grant_spark(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        spark_id=spark_id,
        body=_body_to_payload(body),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    db.commit()
    db.refresh(row)
    return gss.spark_to_dict(row)
