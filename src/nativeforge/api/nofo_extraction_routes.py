"""Sprint 3 — NOFO stub extraction + checklist (review-gated artifacts)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import nofo_extraction_service as nes


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


demo_nofo_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["nofo-extraction-demo"],
)
real_nofo_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["nofo-extraction-real"],
)


@demo_nofo_router.post(
    "/{org_id}/grant-sparks/{spark_id}/nofo/extract-stub",
    status_code=status.HTTP_201_CREATED,
)
def demo_extract_stub(
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
        run, art = nes.run_stub_extraction(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(run)
        db.refresh(art)
    except ValueError:
        raise HTTPException(status_code=404, detail="grant spark not found") from None
    return {
        "extraction_run": nes.extraction_run_to_dict(run),
        "review_artifact": {
            "id": str(art.id),
            "artifact_type": art.artifact_type,
            "review_status": art.review_status,
        },
        "nofo_summary": run.nofo_summary,
        "structured_requirements": run.structured_requirements,
        "checklist_row_count": len(run.checklist_snapshot)
        if isinstance(run.checklist_snapshot, list)
        else None,
    }


@demo_nofo_router.get("/{org_id}/grant-sparks/{spark_id}/nofo/latest")
def demo_nofo_latest(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    payload = nes.build_latest_payload(
        db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="no extraction run for this spark")
    return payload


@demo_nofo_router.get("/{org_id}/grant-sparks/{spark_id}/nofo/requirements")
def demo_nofo_requirements(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = nes.list_checklist_requirements(
        db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if rows is None:
        raise HTTPException(status_code=404, detail="no extraction run for this spark")
    return {"requirements": rows}


@real_nofo_router.post(
    "/{org_id}/grant-sparks/{spark_id}/nofo/extract-stub",
    status_code=status.HTTP_201_CREATED,
)
def real_extract_stub(
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
        run, art = nes.run_stub_extraction(
            db,
            org=org,
            org_type=ctx.org_type,
            spark_id=spark_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(run)
        db.refresh(art)
    except ValueError:
        raise HTTPException(status_code=404, detail="grant spark not found") from None
    return {
        "extraction_run": nes.extraction_run_to_dict(run),
        "review_artifact": {
            "id": str(art.id),
            "artifact_type": art.artifact_type,
            "review_status": art.review_status,
        },
        "nofo_summary": run.nofo_summary,
        "structured_requirements": run.structured_requirements,
        "checklist_row_count": len(run.checklist_snapshot)
        if isinstance(run.checklist_snapshot, list)
        else None,
    }


@real_nofo_router.get("/{org_id}/grant-sparks/{spark_id}/nofo/latest")
def real_nofo_latest(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    payload = nes.build_latest_payload(
        db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail="no extraction run for this spark")
    return payload


@real_nofo_router.get("/{org_id}/grant-sparks/{spark_id}/nofo/requirements")
def real_nofo_requirements(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = nes.list_checklist_requirements(
        db,
        spark_id=spark_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if rows is None:
        raise HTTPException(status_code=404, detail="no extraction run for this spark")
    return {"requirements": rows}
