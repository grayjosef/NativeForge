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
from nativeforge.services.live_grants_gov_honest_orchestrator_service import (
    run_live_grants_gov_honest_block,
)
from nativeforge.services.mixed_corpus_discrimination_orchestrator_service import (
    run_mixed_corpus_discrimination_block,
)
from nativeforge.services.nf15_no_evidence_honesty_orchestrator_service import (
    run_nf15_no_evidence_honesty_block,
)
from nativeforge.services.nf16_no_proxy_honesty_orchestrator_service import (
    run_nf16_no_proxy_honesty_block,
)
from nativeforge.services.real_grant_classify_match_orchestrator_service import (
    run_real_grant_classify_match_block,
)
from nativeforge.services.real_grant_workbench_queue_service import (
    build_real_grant_workbench_queues,
)
from nativeforge.services.real_resolver_seed_preview_report_service import (
    build_real_resolver_seed_preview_report,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    is_real_resolver_validation_approved,
)
from nativeforge.services.real_resolver_validation_orchestrator_service import (
    run_real_resolver_validation_block,
)
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
from nativeforge.services.tier1_batch_live_pull_orchestrator_service import (
    run_tier1_batch_live_pull_block,
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


def _require_real_resolver_validation_query(
    nf_live_source_ingestion: bool,
    nf_real_resolver_validation: bool,
) -> None:
    if not is_real_resolver_validation_approved(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "real resolver validation requires NF_APP_ENV=staging, "
                "nf_live_source_ingestion=true, "
                "nf_real_resolver_validation=true, "
                "NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED, and "
                "NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED"
            ),
        )


@demo_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/real-resolver-seed-preview"
)
def demo_real_resolver_seed_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return build_real_resolver_seed_preview_report()


@real_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/real-resolver-seed-preview"
)
def real_real_resolver_seed_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return build_real_resolver_seed_preview_report()


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/real-resolver-validation"
)
def demo_real_resolver_validation(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_real_resolver_validation_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/real-resolver-validation"
)
def real_real_resolver_validation(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_real_resolver_validation_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/live-grants-gov-honest"
)
def demo_live_grants_gov_honest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_live_grants_gov_honest_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/live-grants-gov-honest"
)
def real_live_grants_gov_honest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_live_grants_gov_honest_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/tier1-batch-live-pull"
)
def demo_tier1_batch_live_pull(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_tier1_batch_live_pull_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/tier1-batch-live-pull"
)
def real_tier1_batch_live_pull(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: dict[str, Any],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    result = run_tier1_batch_live_pull_block(
        db,
        org=org,
        org_id=org_id,
        operator_confirmation=body,
    )
    db.commit()
    return result


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/real-grant-classify-match"
)
def demo_real_grant_classify_match(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_real_grant_classify_match_block(org_id=org_id)


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/real-grant-classify-match"
)
def real_real_grant_classify_match(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_real_grant_classify_match_block(org_id=org_id)


@demo_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/real-grant-workbench-queues"
)
def demo_real_grant_workbench_queues(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return build_real_grant_workbench_queues()


@real_source_ingestion_router.get(
    "/{org_id}/discovery/source-ingestion/real-grant-workbench-queues"
)
def real_real_grant_workbench_queues(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return build_real_grant_workbench_queues()


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/mixed-corpus-discrimination"
)
def demo_mixed_corpus_discrimination(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_mixed_corpus_discrimination_block(org_id=org_id)


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/mixed-corpus-discrimination"
)
def real_mixed_corpus_discrimination(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_mixed_corpus_discrimination_block(org_id=org_id)


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/no-evidence-honesty-reingest"
)
def demo_no_evidence_honesty_reingest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_nf15_no_evidence_honesty_block(org_id=org_id)


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/no-evidence-honesty-reingest"
)
def real_no_evidence_honesty_reingest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_nf15_no_evidence_honesty_block(org_id=org_id)


@demo_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/no-proxy-honesty"
)
def demo_no_proxy_honesty(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_nf16_no_proxy_honesty_block(org_id=org_id)


@real_source_ingestion_router.post(
    "/{org_id}/discovery/source-ingestion/no-proxy-honesty"
)
def real_no_proxy_honesty(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    nf_live_source_ingestion: bool = Query(False),
    nf_real_resolver_validation: bool = Query(False),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    _require_real_resolver_validation_query(
        nf_live_source_ingestion,
        nf_real_resolver_validation,
    )
    return run_nf16_no_proxy_honesty_block(org_id=org_id)


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
