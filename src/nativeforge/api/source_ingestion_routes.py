"""Sprint 269: live source ingestion API routes (plan-gated)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import source_ingestion_orchestrator_service as orch
from nativeforge.services.source_ingestion_plan_gate_service import (
    is_live_source_ingestion_plan_approved,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
)
from nativeforge.services.staging_activation_dry_run_gate_service import (
    is_staging_activation_dry_run_approved,
)
from nativeforge.services.staging_activation_dry_run_orchestrator_service import (
    run_staging_activation_dry_run,
)
from nativeforge.services.staging_seed_preview_report_service import (
    build_staging_seed_preview_report,
)

demo_source_ingestion_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["source-ingestion-demo"],
)
real_source_ingestion_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["source-ingestion-real"],
)


def _same_org(org_id: uuid.UUID, ctx: OrgContext) -> None:
    if org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="organization not found")


def _require_plan_gate_query(nf_live_source_ingestion: bool) -> None:
    if not nf_live_source_ingestion or not is_live_source_ingestion_plan_approved():
        raise HTTPException(
            status_code=403,
            detail=(
                "nf_live_source_ingestion flag and "
                "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED required"
            ),
        )


def _require_staging_dry_run_query(
    nf_live_source_ingestion: bool,
    nf_staging_activation_dry_run: bool,
) -> None:
    if not is_staging_activation_dry_run_approved(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_staging_activation_dry_run=nf_staging_activation_dry_run,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "staging dry-run requires NF_APP_ENV=staging, "
                "nf_live_source_ingestion=true, "
                "nf_staging_activation_dry_run=true, and "
                "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED"
            ),
        )


@demo_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/staging-seed-preview-report"
)
def demo_staging_seed_preview_report(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_staging_activation_dry_run: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_staging_dry_run_query(
        nf_live_source_ingestion,
        nf_staging_activation_dry_run,
    )
    return build_staging_seed_preview_report()


@real_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/staging-seed-preview-report"
)
def real_staging_seed_preview_report(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_staging_activation_dry_run: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_staging_dry_run_query(
        nf_live_source_ingestion,
        nf_staging_activation_dry_run,
    )
    return build_staging_seed_preview_report()


@demo_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/staging-activation-dry-run"
)
def demo_staging_activation_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_staging_activation_dry_run: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_staging_dry_run_query(
        nf_live_source_ingestion,
        nf_staging_activation_dry_run,
    )
    return run_staging_activation_dry_run(org_id=org_id)


@real_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/staging-activation-dry-run"
)
def real_staging_activation_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_staging_activation_dry_run: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_staging_dry_run_query(
        nf_live_source_ingestion,
        nf_staging_activation_dry_run,
    )
    return run_staging_activation_dry_run(org_id=org_id)


@demo_source_ingestion_router.get("/{org_id}/discovery/source-ingestion/seed-preview")
def demo_seed_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_plan_gate_query(nf_live_source_ingestion)
    return orch.run_source_seed_ingestion_preview(org_id=org_id)


@real_source_ingestion_router.get("/{org_id}/discovery/source-ingestion/seed-preview")
def real_seed_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_plan_gate_query(nf_live_source_ingestion)
    return orch.run_source_seed_ingestion_preview(org_id=org_id)


@demo_source_ingestion_router.post("/{org_id}/discovery/source-ingestion/load-seed-candidates")
def demo_load_seed_candidates(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_live_source_ingestion: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_plan_gate_query(nf_live_source_ingestion)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    bundle = build_source_seed_candidate_bundle()
    stats = orch.persist_seed_candidates_to_registry(
        db,
        org=org,
        candidates=bundle["candidates"],
    )
    db.commit()
    return {
        "schema_version": "nf_source_ingestion_load_seed_v1",
        "seed_row_count": bundle["seed_row_count"],
        "persist_stats": stats,
        "all_inactive": True,
        "human_activation_required": True,
    }


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/load-seed-candidates"
)
def real_load_seed_candidates(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    nf_live_source_ingestion: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_plan_gate_query(nf_live_source_ingestion)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    bundle = build_source_seed_candidate_bundle()
    stats = orch.persist_seed_candidates_to_registry(
        db,
        org=org,
        candidates=bundle["candidates"],
    )
    db.commit()
    return {
        "schema_version": "nf_source_ingestion_load_seed_v1",
        "seed_row_count": bundle["seed_row_count"],
        "persist_stats": stats,
        "all_inactive": True,
        "human_activation_required": True,
    }
