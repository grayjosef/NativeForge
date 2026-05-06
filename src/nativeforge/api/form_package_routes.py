"""Sprint 6 — form packages (review-gated) + SF-424 preview."""

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
from nativeforge.services import form_package_service as fpsvc
from nativeforge.services.pursuit_service import PursuitNotFoundError


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _fp_exc(e: Exception) -> None:
    if isinstance(e, PursuitNotFoundError):
        raise HTTPException(status_code=404, detail=str(e)) from e
    if isinstance(e, fpsvc.TribalProfileRequiredError):
        raise HTTPException(status_code=400, detail=str(e)) from e
    if isinstance(e, fpsvc.FormPackageAlreadyExistsError):
        raise HTTPException(status_code=409, detail=str(e)) from e
    if isinstance(e, fpsvc.FormPackageNotFoundError):
        raise HTTPException(status_code=404, detail=str(e)) from e
    raise e


demo_form_pkg_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["form-packages-demo"],
)
real_form_pkg_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["form-packages-real"],
)


@demo_form_pkg_router.post(
    "/{org_id}/pursuits/{pursuit_id}/form-package",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_form_package(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = fpsvc.create_form_package(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        PursuitNotFoundError,
        fpsvc.TribalProfileRequiredError,
        fpsvc.FormPackageAlreadyExistsError,
    ) as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)


@demo_form_pkg_router.get("/{org_id}/pursuits/{pursuit_id}/form-package")
def demo_get_form_package(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = fpsvc.get_form_package(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except fpsvc.FormPackageNotFoundError as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)


@demo_form_pkg_router.post("/{org_id}/pursuits/{pursuit_id}/form-package/regenerate")
def demo_regenerate_preview(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = fpsvc.regenerate_sf424_preview(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        PursuitNotFoundError,
        fpsvc.TribalProfileRequiredError,
        fpsvc.FormPackageNotFoundError,
    ) as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)


@real_form_pkg_router.post(
    "/{org_id}/pursuits/{pursuit_id}/form-package",
    status_code=status.HTTP_201_CREATED,
)
def real_create_form_package(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = fpsvc.create_form_package(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        PursuitNotFoundError,
        fpsvc.TribalProfileRequiredError,
        fpsvc.FormPackageAlreadyExistsError,
    ) as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)


@real_form_pkg_router.get("/{org_id}/pursuits/{pursuit_id}/form-package")
def real_get_form_package(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    try:
        row = fpsvc.get_form_package(
            db,
            org_id=ctx.org_id,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
        )
    except fpsvc.FormPackageNotFoundError as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)


@real_form_pkg_router.post("/{org_id}/pursuits/{pursuit_id}/form-package/regenerate")
def real_regenerate_preview(
    org_id: uuid.UUID,
    pursuit_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = fpsvc.regenerate_sf424_preview(
            db,
            org=org,
            org_type=ctx.org_type,
            pursuit_id=pursuit_id,
            actor_id=actor_id,
        )
        db.commit()
        db.refresh(row)
    except (
        PursuitNotFoundError,
        fpsvc.TribalProfileRequiredError,
        fpsvc.FormPackageNotFoundError,
    ) as e:
        _fp_exc(e)
    return fpsvc.form_package_to_dict(row)
