"""Sprint 229: read-only operator workbench advisory routes (Stage 11 wiring)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from nativeforge.api.deps_db import require_demo_org_db, require_real_org_db
from nativeforge.api.org_context import OrgContext
from nativeforge.services import operator_workbench_advisory_service as wb_adv

demo_workbench_advisory_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["operator-workbench-advisory-demo"],
)
real_workbench_advisory_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["operator-workbench-advisory-real"],
)


def _same_org(org_id: uuid.UUID, ctx: OrgContext) -> None:
    if org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="organization not found")


def _require_workbench_flag(nf_workbench: bool) -> None:
    if not nf_workbench:
        raise HTTPException(
            status_code=403,
            detail="nf_workbench flag required for advisory preview endpoints",
        )


def _bundle_handler(
    org_id: uuid.UUID,
    ctx: OrgContext,
    nf_workbench: bool,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_workbench_flag(nf_workbench)
    return wb_adv.build_operator_workbench_advisory_bundle(org_id=org_id)


@demo_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/bundle"
)
def demo_workbench_advisory_bundle(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    return _bundle_handler(org_id, ctx, nf_workbench)


@real_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/bundle"
)
def real_workbench_advisory_bundle(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    return _bundle_handler(org_id, ctx, nf_workbench)


@demo_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/native-relevance"
)
def demo_native_relevance_advisory(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_workbench_flag(nf_workbench)
    return wb_adv.build_native_relevance_advisory_preview()


@real_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/native-relevance"
)
def real_native_relevance_advisory(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_workbench_flag(nf_workbench)
    return wb_adv.build_native_relevance_advisory_preview()


@demo_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/matching-readiness"
)
def demo_matching_readiness_advisory(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_workbench_flag(nf_workbench)
    return wb_adv.build_matching_readiness_advisory_preview()


@real_workbench_advisory_router.get(
    "/{org_id}/discovery/operator-workbench-advisory/matching-readiness"
)
def real_matching_readiness_advisory(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_workbench: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_workbench_flag(nf_workbench)
    return wb_adv.build_matching_readiness_advisory_preview()
