"""Sprint 249: Stage 12 guided demo path API routes (read-only, demo org)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from nativeforge.api.deps_db import require_demo_org_db, require_real_org_db
from nativeforge.api.org_context import OrgContext
from nativeforge.services import stage12_demo_reset_service as reset_svc
from nativeforge.services import stage12_guided_demo_path_service as guided_svc

demo_stage12_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["stage12-guided-demo-demo"],
)
real_stage12_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["stage12-guided-demo-real"],
)


def _same_org(org_id: uuid.UUID, ctx: OrgContext) -> None:
    if org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="organization not found")


def _require_stage12_flag(nf_stage12_demo: bool) -> None:
    if not nf_stage12_demo:
        raise HTTPException(
            status_code=403,
            detail="nf_stage12_demo flag required for Stage 12 guided demo endpoints",
        )


def _guided_path_handler(
    org_id: uuid.UUID,
    ctx: OrgContext,
    nf_stage12_demo: bool,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_stage12_flag(nf_stage12_demo)
    return guided_svc.build_stage12_guided_demo_path(org_id=org_id)


@demo_stage12_router.get("/{org_id}/discovery/stage12-guided-demo-path")
def demo_stage12_guided_path(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_stage12_demo: bool = Query(False),
) -> dict[str, Any]:
    return _guided_path_handler(org_id, ctx, nf_stage12_demo)


@real_stage12_router.get("/{org_id}/discovery/stage12-guided-demo-path")
def real_stage12_guided_path(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_stage12_demo: bool = Query(False),
) -> dict[str, Any]:
    return _guided_path_handler(org_id, ctx, nf_stage12_demo)


@demo_stage12_router.get("/{org_id}/discovery/stage12-demo-reset")
def demo_stage12_reset(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_stage12_demo: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_stage12_flag(nf_stage12_demo)
    return reset_svc.build_stage12_demo_reset_descriptor()


@real_stage12_router.get("/{org_id}/discovery/stage12-demo-reset")
def real_stage12_reset(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_stage12_demo: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_stage12_flag(nf_stage12_demo)
    return reset_svc.build_stage12_demo_reset_descriptor()
