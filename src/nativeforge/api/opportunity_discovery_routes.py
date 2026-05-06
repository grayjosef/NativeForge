"""Discovery Engine routes — source registry and Grant Spark discovery intake."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    body_to_discovery_seed as _body_to_discovery_seed,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    discovery_evidence_pack_handler as _discovery_evidence_pack_handler,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    maybe_filter_coverage_intel as _maybe_filter_coverage_intel,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    same_org as _same_org,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    source_payload_from_body as _source_payload_from_body,
)
from nativeforge.api.opportunity_discovery_route_helpers import (
    validate_registry_id as _validate_registry_id,
)
from nativeforge.api.opportunity_discovery_schemas import (
    NF_OPERATOR_ACTIONS_LEDGER_LIST_SCHEMA_VERSION,
    DiscoveryIntakeRunCreateBody,
    DiscoverySparkCreateBody,
    OperatorActionCreateManualBody,
    OperatorActionFromDecisionBody,
    OperatorActionLedgerPatchBody,
    OpportunitySourceCreateBody,
    ReviewItemPatchBody,
    SourceCheckRunCreateBody,
    SourceCheckRunPatchBody,
    StructuredCandidatesBatchBody,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.db.models import is_demo_for_org_type
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    EvidencePackSubjectType,
    SourceCheckRunStatus,
)
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.repositories import organizations as org_repo
from nativeforge.repositories import source_check_runs as scr_repo
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import discovery_evidence_pack_service as ev_pack_svc
from nativeforge.services import discovery_intake_service as d_intake
from nativeforge.services import discovery_operator_workbench_service as op_wb
from nativeforge.services import discovery_review_service as d_review
from nativeforge.services import grant_spark_service as gss
from nativeforge.services import operator_action_service as oa_svc
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.grant_spark_service import DuplicateGrantSparkError

demo_discovery_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["opportunity-discovery-demo"],
)
real_discovery_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["opportunity-discovery-real"],
)


@demo_discovery_router.post(
    "/{org_id}/discovery/sources",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_source(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OpportunitySourceCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    row = ods.create_opportunity_source(
        db, org=org, body=_source_payload_from_body(body)
    )
    db.commit()
    db.refresh(row)
    return ods.opportunity_source_to_dict(row)


@demo_discovery_router.post("/{org_id}/discovery/sources/seed-catalog")
def demo_seed_source_catalog(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    stats = ods.seed_opportunity_source_catalog(db, org=org)
    db.commit()
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    summary = ods.discovery_coverage_summary(rows)
    return {**stats, "coverage_summary": summary}


@demo_discovery_router.get("/{org_id}/discovery/coverage-summary")
def demo_discovery_coverage_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return ods.discovery_coverage_summary(rows)


@demo_discovery_router.get("/{org_id}/discovery/sources/due")
def demo_list_sources_due(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    now = datetime.now(UTC)
    out = sfs.filter_sources_due(rows, now=now)
    return [ods.opportunity_source_to_dict(r) for r in out]


@demo_discovery_router.get("/{org_id}/discovery/sources/overdue")
def demo_list_sources_overdue(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    now = datetime.now(UTC)
    out = sfs.filter_sources_overdue(rows, now=now)
    return [ods.opportunity_source_to_dict(r) for r in out]


@demo_discovery_router.get("/{org_id}/discovery/sources/freshness-summary")
def demo_discovery_sources_freshness_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return sfs.build_freshness_summary_payload(rows, now=datetime.now(UTC))


@demo_discovery_router.get("/{org_id}/discovery/coverage-gap-intelligence")
def demo_discovery_coverage_gap_intelligence(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    return _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )


@demo_discovery_router.get("/{org_id}/discovery/coverage-gaps")
def demo_discovery_coverage_gaps(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    filtered = _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )
    return {
        "schema_version": filtered["schema_version"],
        "organization_id": filtered["organization_id"],
        "is_demo": filtered["is_demo"],
        "generated_at": filtered["generated_at"],
        "coverage_gaps": filtered["coverage_gaps"],
    }


@demo_discovery_router.get("/{org_id}/discovery/source-recommendations")
def demo_discovery_source_recommendations(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    filtered = _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )
    return {
        "schema_version": filtered["schema_version"],
        "organization_id": filtered["organization_id"],
        "is_demo": filtered["is_demo"],
        "generated_at": filtered["generated_at"],
        "source_recommendations": filtered["source_recommendations"],
    }


@demo_discovery_router.get("/{org_id}/discovery/operator-decision-pack")
@demo_discovery_router.get("/{org_id}/discovery/operator-workbench")
def demo_operator_decision_pack(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    intake_run_limit: Annotated[int, Query(ge=1, le=200)] = 40,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    include_snapshots: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return op_wb.build_operator_decision_pack(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
        intake_run_limit=intake_run_limit,
        severity=severity,
        item_type=item_type,
        action=action,
        source_registry_id=source_registry_id,
        limit=limit,
        include_snapshots=include_snapshots,
    )


@demo_discovery_router.get("/{org_id}/discovery/operator-actions")
def demo_operator_actions(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    intake_run_limit: Annotated[int, Query(ge=1, le=200)] = 40,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    include_snapshots: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return op_wb.build_operator_actions_pack(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
        intake_run_limit=intake_run_limit,
        severity=severity,
        item_type=item_type,
        action=action,
        source_registry_id=source_registry_id,
        limit=limit,
        include_snapshots=include_snapshots,
    )


@demo_discovery_router.get("/{org_id}/discovery/operator-actions-ledger/summary")
def demo_operator_actions_ledger_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return oa_svc.build_ledger_summary(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )


@demo_discovery_router.get("/{org_id}/discovery/operator-actions-ledger")
def demo_list_operator_actions_ledger(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    status: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    assigned_to: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    review_item_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_run_id: Annotated[uuid.UUID | None, Query()] = None,
    decision_id: Annotated[str | None, Query()] = None,
    open_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import operator_actions as oa_repo

    rows = oa_repo.list_operator_actions_for_org(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        status=status,
        severity=severity,
        item_type=item_type,
        action=action,
        assigned_to=assigned_to,
        source_registry_id=source_registry_id,
        review_item_id=review_item_id,
        intake_run_id=intake_run_id,
        decision_id=decision_id,
        open_only=open_only,
        limit=limit,
    )
    return {
        "schema_version": NF_OPERATOR_ACTIONS_LEDGER_LIST_SCHEMA_VERSION,
        "organization_id": str(ctx.org_id),
        "operator_actions": [oa_svc.operator_action_to_dict(r) for r in rows],
        "count": len(rows),
    }


@demo_discovery_router.get(
    "/{org_id}/discovery/operator-actions-ledger/{operator_action_id}"
)
def demo_get_operator_action_ledger_item(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import operator_actions as oa_repo

    row = oa_repo.get_operator_action_scoped(
        db,
        action_id=operator_action_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="operator action not found")
    return oa_svc.operator_action_to_dict(row)


@demo_discovery_router.post(
    "/{org_id}/discovery/operator-actions-ledger",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_operator_action_manual(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionCreateManualBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = oa_svc.create_operator_action_manual(
            db,
            org=org,
            org_type=ctx.org_type,
            decision_id=body.decision_id,
            action_title=body.action_title,
            operator_action=body.operator_action,
            item_type=body.item_type,
            severity=body.severity,
            action=body.action,
            assigned_to=body.assigned_to,
            due_at=body.due_at,
            operator_notes=body.operator_notes,
            action_summary=body.action_summary,
            source_registry_id=body.source_registry_id,
            review_item_id=body.review_item_id,
            intake_run_id=body.intake_run_id,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@demo_discovery_router.post(
    "/{org_id}/discovery/operator-actions-ledger/from-decision",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_operator_action_from_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionFromDecisionBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out, outcome = oa_svc.create_operator_action_from_decision_item(
            db,
            org=org,
            org_type=ctx.org_type,
            decision_item=body.decision_item,
            assigned_to=body.assigned_to,
            due_at=body.due_at,
            operator_notes=body.operator_notes,
            force_new=body.force_new,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"outcome": outcome, "operator_action": out}


@demo_discovery_router.patch(
    "/{org_id}/discovery/operator-actions-ledger/{operator_action_id}"
)
def demo_patch_operator_action_ledger_item(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionLedgerPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    patch = body.model_dump(exclude_unset=True, mode="json")
    try:
        out = oa_svc.patch_operator_action(
            db,
            org=org,
            org_type=ctx.org_type,
            operator_action_id=operator_action_id,
            patch=patch,
        )
        if out is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="operator action not found")
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@demo_discovery_router.get("/{org_id}/discovery/sources")
def demo_list_sources(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [ods.opportunity_source_to_dict(r) for r in rows]


@demo_discovery_router.get("/{org_id}/discovery/sources/{source_id}/freshness")
def demo_get_source_freshness(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    return sfs.opportunity_source_freshness_detail(row, now=datetime.now(UTC))


@demo_discovery_router.post(
    "/{org_id}/discovery/sources/{source_id}/check-runs",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_source_check_run(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: SourceCheckRunCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    row = scr_repo.create_source_check_run(
        db,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        source_registry_id=source_id,
        check_mode=body.check_mode.value,
        check_status=SourceCheckRunStatus.running.value,
        operator_notes=body.operator_notes,
        checked_for_period_start=body.checked_for_period_start,
        checked_for_period_end=body.checked_for_period_end,
    )
    audit_repo.append_org_audit_event(
        db,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.source_check_run_created,
        payload={
            "source_check_run_id": str(row.id),
            "source_registry_id": str(source_id),
            "check_mode": body.check_mode.value,
        },
        actor_id=None,
    )
    db.commit()
    db.refresh(row)
    return sfs.check_run_to_dict(row)


@demo_discovery_router.get("/{org_id}/discovery/sources/{source_id}/check-runs")
def demo_list_source_check_runs(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    rows = scr_repo.list_source_check_runs_for_source(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        source_registry_id=source_id,
    )
    return [sfs.check_run_to_dict(r) for r in rows]


@demo_discovery_router.post(
    "/{org_id}/discovery/sparks",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_discovery_spark(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: DiscoverySparkCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    _validate_registry_id(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        registry_id=body.source_registry_id,
    )
    try:
        row = ods.create_spark_from_discovery(
            db, org=org, body=_body_to_discovery_seed(body)
        )
        db.commit()
        db.refresh(row)
    except DuplicateGrantSparkError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="grant spark already exists for this source and source_id",
        ) from None
    return gss.spark_to_dict(row)


@demo_discovery_router.get("/{org_id}/discovery/sparks")
def demo_list_discovery_sparks(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = gss.list_sparks(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [gss.spark_to_dict(r) for r in rows]


@demo_discovery_router.get(
    "/{org_id}/grant-sparks/{spark_id}/discovery-intelligence",
)
def demo_discovery_intelligence(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    spark = ods.get_spark_for_discovery_intel(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        spark_id=spark_id,
    )
    if spark is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    return ods.opportunity_intelligence_summary(spark)


@demo_discovery_router.post(
    "/{org_id}/discovery/sources/{source_id}/intake-runs",
    status_code=status.HTTP_201_CREATED,
)
def demo_start_intake_run(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: DiscoveryIntakeRunCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = d_intake.start_intake_run(
            db,
            org=org,
            source_registry_id=source_id,
            intake_mode=body.intake_mode,
            operator_note=body.operator_note,
        )
        db.commit()
        db.refresh(row)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return d_intake.intake_run_to_dict(row)


@demo_discovery_router.get("/{org_id}/discovery/sources/{source_id}/intake-runs")
def demo_list_intake_runs_for_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = intake_repo.list_discovery_intake_runs_for_org_source(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        source_registry_id=source_id,
    )
    return [d_intake.intake_run_to_dict(r) for r in rows]


@demo_discovery_router.get("/{org_id}/discovery/intake-runs/{run_id}")
def demo_get_intake_run(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = intake_repo.get_discovery_intake_run_scoped(
        session=db,
        run_id=run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="intake run not found")
    return d_intake.intake_run_to_dict(row)


@demo_discovery_router.post("/{org_id}/discovery/intake-runs/{run_id}/candidates")
def demo_process_intake_candidates(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: StructuredCandidatesBatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        result = d_intake.process_structured_candidates(
            db,
            org=org,
            org_type=ctx.org_type,
            run_id=run_id,
            candidates=body.candidates,
        )
        db.commit()
    except d_intake.IntakeRunStateError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@demo_discovery_router.get("/{org_id}/discovery/intake-runs/{run_id}/candidates")
def demo_list_intake_candidates(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    run = intake_repo.get_discovery_intake_run_scoped(
        session=db,
        run_id=run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="intake run not found")
    rows = intake_repo.list_discovery_intake_candidates_for_run(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        intake_run_id=run_id,
    )
    return [d_intake.intake_candidate_to_dict(r) for r in rows]


@real_discovery_router.post(
    "/{org_id}/discovery/sources",
    status_code=status.HTTP_201_CREATED,
)
def real_create_source(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OpportunitySourceCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    row = ods.create_opportunity_source(
        db, org=org, body=_source_payload_from_body(body)
    )
    db.commit()
    db.refresh(row)
    return ods.opportunity_source_to_dict(row)


@real_discovery_router.post("/{org_id}/discovery/sources/seed-catalog")
def real_seed_source_catalog(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    stats = ods.seed_opportunity_source_catalog(db, org=org)
    db.commit()
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    summary = ods.discovery_coverage_summary(rows)
    return {**stats, "coverage_summary": summary}


@real_discovery_router.get("/{org_id}/discovery/coverage-summary")
def real_discovery_coverage_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return ods.discovery_coverage_summary(rows)


@real_discovery_router.get("/{org_id}/discovery/sources/due")
def real_list_sources_due(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    now = datetime.now(UTC)
    out = sfs.filter_sources_due(rows, now=now)
    return [ods.opportunity_source_to_dict(r) for r in out]


@real_discovery_router.get("/{org_id}/discovery/sources/overdue")
def real_list_sources_overdue(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    now = datetime.now(UTC)
    out = sfs.filter_sources_overdue(rows, now=now)
    return [ods.opportunity_source_to_dict(r) for r in out]


@real_discovery_router.get("/{org_id}/discovery/sources/freshness-summary")
def real_discovery_sources_freshness_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return sfs.build_freshness_summary_payload(rows, now=datetime.now(UTC))


@real_discovery_router.get("/{org_id}/discovery/coverage-gap-intelligence")
def real_discovery_coverage_gap_intelligence(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    return _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )


@real_discovery_router.get("/{org_id}/discovery/coverage-gaps")
def real_discovery_coverage_gaps(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    filtered = _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )
    return {
        "schema_version": filtered["schema_version"],
        "organization_id": filtered["organization_id"],
        "is_demo": filtered["is_demo"],
        "generated_at": filtered["generated_at"],
        "coverage_gaps": filtered["coverage_gaps"],
    }


@real_discovery_router.get("/{org_id}/discovery/source-recommendations")
def real_discovery_source_recommendations(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    severity: str | None = Query(None),
    gap_type: str | None = Query(None),
    domain: str | None = Query(None),
    source_type: str | None = Query(None),
    priority_level: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    full = dcg_svc.build_coverage_gap_intelligence(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )
    filtered = _maybe_filter_coverage_intel(
        db,
        ctx,
        full,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )
    return {
        "schema_version": filtered["schema_version"],
        "organization_id": filtered["organization_id"],
        "is_demo": filtered["is_demo"],
        "generated_at": filtered["generated_at"],
        "source_recommendations": filtered["source_recommendations"],
    }


@real_discovery_router.get("/{org_id}/discovery/operator-decision-pack")
@real_discovery_router.get("/{org_id}/discovery/operator-workbench")
def real_operator_decision_pack(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    intake_run_limit: Annotated[int, Query(ge=1, le=200)] = 40,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    include_snapshots: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return op_wb.build_operator_decision_pack(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
        intake_run_limit=intake_run_limit,
        severity=severity,
        item_type=item_type,
        action=action,
        source_registry_id=source_registry_id,
        limit=limit,
        include_snapshots=include_snapshots,
    )


@real_discovery_router.get("/{org_id}/discovery/operator-actions")
def real_operator_actions(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    intake_run_limit: Annotated[int, Query(ge=1, le=200)] = 40,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    include_snapshots: Annotated[bool, Query()] = True,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return op_wb.build_operator_actions_pack(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
        intake_run_limit=intake_run_limit,
        severity=severity,
        item_type=item_type,
        action=action,
        source_registry_id=source_registry_id,
        limit=limit,
        include_snapshots=include_snapshots,
    )


@real_discovery_router.get("/{org_id}/discovery/operator-actions-ledger/summary")
def real_operator_actions_ledger_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return oa_svc.build_ledger_summary(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        now=datetime.now(UTC),
    )


@real_discovery_router.get("/{org_id}/discovery/operator-actions-ledger")
def real_list_operator_actions_ledger(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    status: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    item_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    assigned_to: Annotated[str | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    review_item_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_run_id: Annotated[uuid.UUID | None, Query()] = None,
    decision_id: Annotated[str | None, Query()] = None,
    open_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import operator_actions as oa_repo

    rows = oa_repo.list_operator_actions_for_org(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        status=status,
        severity=severity,
        item_type=item_type,
        action=action,
        assigned_to=assigned_to,
        source_registry_id=source_registry_id,
        review_item_id=review_item_id,
        intake_run_id=intake_run_id,
        decision_id=decision_id,
        open_only=open_only,
        limit=limit,
    )
    return {
        "schema_version": NF_OPERATOR_ACTIONS_LEDGER_LIST_SCHEMA_VERSION,
        "organization_id": str(ctx.org_id),
        "operator_actions": [oa_svc.operator_action_to_dict(r) for r in rows],
        "count": len(rows),
    }


@real_discovery_router.get(
    "/{org_id}/discovery/operator-actions-ledger/{operator_action_id}"
)
def real_get_operator_action_ledger_item(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    from nativeforge.repositories import operator_actions as oa_repo

    row = oa_repo.get_operator_action_scoped(
        db,
        action_id=operator_action_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="operator action not found")
    return oa_svc.operator_action_to_dict(row)


@real_discovery_router.post(
    "/{org_id}/discovery/operator-actions-ledger",
    status_code=status.HTTP_201_CREATED,
)
def real_create_operator_action_manual(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionCreateManualBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = oa_svc.create_operator_action_manual(
            db,
            org=org,
            org_type=ctx.org_type,
            decision_id=body.decision_id,
            action_title=body.action_title,
            operator_action=body.operator_action,
            item_type=body.item_type,
            severity=body.severity,
            action=body.action,
            assigned_to=body.assigned_to,
            due_at=body.due_at,
            operator_notes=body.operator_notes,
            action_summary=body.action_summary,
            source_registry_id=body.source_registry_id,
            review_item_id=body.review_item_id,
            intake_run_id=body.intake_run_id,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@real_discovery_router.post(
    "/{org_id}/discovery/operator-actions-ledger/from-decision",
    status_code=status.HTTP_201_CREATED,
)
def real_create_operator_action_from_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionFromDecisionBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out, outcome = oa_svc.create_operator_action_from_decision_item(
            db,
            org=org,
            org_type=ctx.org_type,
            decision_item=body.decision_item,
            assigned_to=body.assigned_to,
            due_at=body.due_at,
            operator_notes=body.operator_notes,
            force_new=body.force_new,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"outcome": outcome, "operator_action": out}


@real_discovery_router.patch(
    "/{org_id}/discovery/operator-actions-ledger/{operator_action_id}"
)
def real_patch_operator_action_ledger_item(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: OperatorActionLedgerPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    patch = body.model_dump(exclude_unset=True, mode="json")
    try:
        out = oa_svc.patch_operator_action(
            db,
            org=org,
            org_type=ctx.org_type,
            operator_action_id=operator_action_id,
            patch=patch,
        )
        if out is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="operator action not found")
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@real_discovery_router.get("/{org_id}/discovery/sources")
def real_list_sources(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [ods.opportunity_source_to_dict(r) for r in rows]


@real_discovery_router.get("/{org_id}/discovery/sources/{source_id}/freshness")
def real_get_source_freshness(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    return sfs.opportunity_source_freshness_detail(row, now=datetime.now(UTC))


@real_discovery_router.post(
    "/{org_id}/discovery/sources/{source_id}/check-runs",
    status_code=status.HTTP_201_CREATED,
)
def real_create_source_check_run(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: SourceCheckRunCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    row = scr_repo.create_source_check_run(
        db,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        source_registry_id=source_id,
        check_mode=body.check_mode.value,
        check_status=SourceCheckRunStatus.running.value,
        operator_notes=body.operator_notes,
        checked_for_period_start=body.checked_for_period_start,
        checked_for_period_end=body.checked_for_period_end,
    )
    audit_repo.append_org_audit_event(
        db,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.source_check_run_created,
        payload={
            "source_check_run_id": str(row.id),
            "source_registry_id": str(source_id),
            "check_mode": body.check_mode.value,
        },
        actor_id=None,
    )
    db.commit()
    db.refresh(row)
    return sfs.check_run_to_dict(row)


@real_discovery_router.get("/{org_id}/discovery/sources/{source_id}/check-runs")
def real_list_source_check_runs(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=source_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    rows = scr_repo.list_source_check_runs_for_source(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        source_registry_id=source_id,
    )
    return [sfs.check_run_to_dict(r) for r in rows]


@real_discovery_router.post(
    "/{org_id}/discovery/sparks",
    status_code=status.HTTP_201_CREATED,
)
def real_create_discovery_spark(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: DiscoverySparkCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    _validate_registry_id(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        registry_id=body.source_registry_id,
    )
    try:
        row = ods.create_spark_from_discovery(
            db, org=org, body=_body_to_discovery_seed(body)
        )
        db.commit()
        db.refresh(row)
    except DuplicateGrantSparkError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="grant spark already exists for this source and source_id",
        ) from None
    return gss.spark_to_dict(row)


@real_discovery_router.get("/{org_id}/discovery/sparks")
def real_list_discovery_sparks(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = gss.list_sparks(db, org_id=ctx.org_id, org_type=ctx.org_type)
    return [gss.spark_to_dict(r) for r in rows]


@real_discovery_router.get(
    "/{org_id}/grant-sparks/{spark_id}/discovery-intelligence",
)
def real_discovery_intelligence(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    spark = ods.get_spark_for_discovery_intel(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        spark_id=spark_id,
    )
    if spark is None:
        raise HTTPException(status_code=404, detail="grant spark not found")
    return ods.opportunity_intelligence_summary(spark)


@real_discovery_router.post(
    "/{org_id}/discovery/sources/{source_id}/intake-runs",
    status_code=status.HTTP_201_CREATED,
)
def real_start_intake_run(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: DiscoveryIntakeRunCreateBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = d_intake.start_intake_run(
            db,
            org=org,
            source_registry_id=source_id,
            intake_mode=body.intake_mode,
            operator_note=body.operator_note,
        )
        db.commit()
        db.refresh(row)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return d_intake.intake_run_to_dict(row)


@real_discovery_router.get("/{org_id}/discovery/sources/{source_id}/intake-runs")
def real_list_intake_runs_for_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    rows = intake_repo.list_discovery_intake_runs_for_org_source(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        source_registry_id=source_id,
    )
    return [d_intake.intake_run_to_dict(r) for r in rows]


@real_discovery_router.get("/{org_id}/discovery/intake-runs/{run_id}")
def real_get_intake_run(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = intake_repo.get_discovery_intake_run_scoped(
        session=db,
        run_id=run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="intake run not found")
    return d_intake.intake_run_to_dict(row)


@real_discovery_router.post("/{org_id}/discovery/intake-runs/{run_id}/candidates")
def real_process_intake_candidates(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: StructuredCandidatesBatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        result = d_intake.process_structured_candidates(
            db,
            org=org,
            org_type=ctx.org_type,
            run_id=run_id,
            candidates=body.candidates,
        )
        db.commit()
    except d_intake.IntakeRunStateError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@real_discovery_router.get("/{org_id}/discovery/intake-runs/{run_id}/candidates")
def real_list_intake_candidates(
    org_id: uuid.UUID,
    run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    run = intake_repo.get_discovery_intake_run_scoped(
        session=db,
        run_id=run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="intake run not found")
    rows = intake_repo.list_discovery_intake_candidates_for_run(
        session=db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        intake_run_id=run_id,
    )
    return [d_intake.intake_candidate_to_dict(r) for r in rows]


@demo_discovery_router.patch("/{org_id}/discovery/source-check-runs/{check_run_id}")
def demo_patch_source_check_run(
    org_id: uuid.UUID,
    check_run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: SourceCheckRunPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    run = scr_repo.get_source_check_run_scoped(
        db,
        check_run_id=check_run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="source check run not found")
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=run.source_registry_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    patch = body.model_dump(mode="json")
    try:
        sfs.finalize_completed_source_check(
            db,
            org=org,
            org_type=ctx.org_type,
            run=run,
            source=src,
            patch=patch,
        )
        db.commit()
        db.refresh(run)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sfs.check_run_to_dict(run)


@demo_discovery_router.get("/{org_id}/discovery/review-items")
def demo_list_discovery_review_items(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    review_status: Annotated[
        DiscoveryReviewQueueStatus | None,
        Query(),
    ] = None,
    review_item_type: Annotated[
        DiscoveryReviewItemType | None,
        Query(),
    ] = None,
    priority: Annotated[int | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_run_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_candidate_id: Annotated[uuid.UUID | None, Query()] = None,
    grant_spark_id: Annotated[uuid.UUID | None, Query()] = None,
    open_queue_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    return d_review.list_review_items(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        review_status=review_status.value if review_status else None,
        review_item_type=review_item_type.value if review_item_type else None,
        priority=priority,
        source_registry_id=source_registry_id,
        intake_run_id=intake_run_id,
        intake_candidate_id=intake_candidate_id,
        grant_spark_id=grant_spark_id,
        open_queue_only=open_queue_only,
        limit=limit,
    )


@demo_discovery_router.get("/{org_id}/discovery/review-items/{review_item_id}")
def demo_get_discovery_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = d_review.get_review_item(
        db,
        review_item_id=review_item_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="discovery review item not found")
    return row


@demo_discovery_router.patch("/{org_id}/discovery/review-items/{review_item_id}")
def demo_patch_discovery_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: ReviewItemPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    patch = body.model_dump(exclude_unset=True, mode="json")
    try:
        out = d_review.patch_review_item(
            db,
            org=org,
            org_type=ctx.org_type,
            review_item_id=review_item_id,
            patch=patch,
        )
        if out is None:
            db.rollback()
            raise HTTPException(
                status_code=404, detail="discovery review item not found"
            )
        db.commit()
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@real_discovery_router.patch("/{org_id}/discovery/source-check-runs/{check_run_id}")
def real_patch_source_check_run(
    org_id: uuid.UUID,
    check_run_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: SourceCheckRunPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    run = scr_repo.get_source_check_run_scoped(
        db,
        check_run_id=check_run_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if run is None:
        raise HTTPException(status_code=404, detail="source check run not found")
    src = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=run.source_registry_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if src is None:
        raise HTTPException(status_code=404, detail="opportunity source not found")
    patch = body.model_dump(mode="json")
    try:
        sfs.finalize_completed_source_check(
            db,
            org=org,
            org_type=ctx.org_type,
            run=run,
            source=src,
            patch=patch,
        )
        db.commit()
        db.refresh(run)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return sfs.check_run_to_dict(run)


@real_discovery_router.get("/{org_id}/discovery/review-items")
def real_list_discovery_review_items(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    review_status: Annotated[
        DiscoveryReviewQueueStatus | None,
        Query(),
    ] = None,
    review_item_type: Annotated[
        DiscoveryReviewItemType | None,
        Query(),
    ] = None,
    priority: Annotated[int | None, Query()] = None,
    source_registry_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_run_id: Annotated[uuid.UUID | None, Query()] = None,
    intake_candidate_id: Annotated[uuid.UUID | None, Query()] = None,
    grant_spark_id: Annotated[uuid.UUID | None, Query()] = None,
    open_queue_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[dict[str, Any]]:
    _same_org(org_id, ctx)
    return d_review.list_review_items(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        review_status=review_status.value if review_status else None,
        review_item_type=review_item_type.value if review_item_type else None,
        priority=priority,
        source_registry_id=source_registry_id,
        intake_run_id=intake_run_id,
        intake_candidate_id=intake_candidate_id,
        grant_spark_id=grant_spark_id,
        open_queue_only=open_queue_only,
        limit=limit,
    )


@real_discovery_router.get("/{org_id}/discovery/review-items/{review_item_id}")
def real_get_discovery_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = d_review.get_review_item(
        db,
        review_item_id=review_item_id,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="discovery review item not found")
    return row


@real_discovery_router.patch("/{org_id}/discovery/review-items/{review_item_id}")
def real_patch_discovery_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: ReviewItemPatchBody,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    patch = body.model_dump(exclude_unset=True, mode="json")
    try:
        out = d_review.patch_review_item(
            db,
            org=org,
            org_type=ctx.org_type,
            review_item_id=review_item_id,
            patch=patch,
        )
        if out is None:
            db.rollback()
            raise HTTPException(
                status_code=404, detail="discovery review item not found"
            )
        db.commit()
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    return out


@demo_discovery_router.get(
    "/{org_id}/discovery/intake-candidates/{candidate_id}/quality",
)
def demo_get_intake_candidate_quality(
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    create_review_item: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = d_review.get_intake_candidate_quality_bundle(
            db,
            org,
            ctx.org_type,
            candidate_id,
            create_review_item=create_review_item,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    return out


@demo_discovery_router.get("/{org_id}/grant-sparks/{spark_id}/discovery-quality")
def demo_get_grant_spark_discovery_quality(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    create_review_item: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = d_review.get_grant_spark_quality_bundle(
            db,
            org,
            ctx.org_type,
            spark_id,
            create_review_item=create_review_item,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    return out


@real_discovery_router.get(
    "/{org_id}/discovery/intake-candidates/{candidate_id}/quality",
)
def real_get_intake_candidate_quality(
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    create_review_item: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = d_review.get_intake_candidate_quality_bundle(
            db,
            org,
            ctx.org_type,
            candidate_id,
            create_review_item=create_review_item,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    return out


@real_discovery_router.get("/{org_id}/grant-sparks/{spark_id}/discovery-quality")
def real_get_grant_spark_discovery_quality(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    create_review_item: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        out = d_review.get_grant_spark_quality_bundle(
            db,
            org,
            ctx.org_type,
            spark_id,
            create_review_item=create_review_item,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    return out


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/sources/{source_id}",
)
def demo_get_evidence_pack_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.opportunity_source,
        source_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/intake-candidates/{candidate_id}",
)
def demo_get_evidence_pack_intake_candidate(
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.intake_candidate,
        candidate_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/grant-sparks/{spark_id}",
)
def demo_get_evidence_pack_grant_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.grant_spark,
        spark_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/review-items/{review_item_id}",
)
def demo_get_evidence_pack_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.discovery_review_item,
        review_item_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/operator-actions/{operator_action_id}",
)
def demo_get_evidence_pack_operator_action(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.operator_action,
        operator_action_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@demo_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/{subject_path}/{subject_id}",
)
def demo_get_evidence_pack_generic(
    org_id: uuid.UUID,
    subject_path: str,
    subject_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    st = ev_pack_svc.subject_path_to_type(subject_path)
    if st is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown evidence-pack subject_path: {subject_path}",
        )
    return _discovery_evidence_pack_handler(
        org_id,
        st,
        subject_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/sources/{source_id}",
)
def real_get_evidence_pack_source(
    org_id: uuid.UUID,
    source_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.opportunity_source,
        source_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/intake-candidates/{candidate_id}",
)
def real_get_evidence_pack_intake_candidate(
    org_id: uuid.UUID,
    candidate_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.intake_candidate,
        candidate_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/grant-sparks/{spark_id}",
)
def real_get_evidence_pack_grant_spark(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.grant_spark,
        spark_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/review-items/{review_item_id}",
)
def real_get_evidence_pack_review_item(
    org_id: uuid.UUID,
    review_item_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.discovery_review_item,
        review_item_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/operator-actions/{operator_action_id}",
)
def real_get_evidence_pack_operator_action(
    org_id: uuid.UUID,
    operator_action_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    return _discovery_evidence_pack_handler(
        org_id,
        EvidencePackSubjectType.operator_action,
        operator_action_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )


@real_discovery_router.get(
    "/{org_id}/discovery/evidence-pack/{subject_path}/{subject_id}",
)
def real_get_evidence_pack_generic(
    org_id: uuid.UUID,
    subject_path: str,
    subject_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    include_audit_trail: Annotated[bool, Query()] = True,
    include_linked_records: Annotated[bool, Query()] = True,
    include_sections: Annotated[bool, Query()] = True,
    audit_limit: Annotated[int, Query(ge=0, le=200)] = 50,
) -> dict[str, Any]:
    st = ev_pack_svc.subject_path_to_type(subject_path)
    if st is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown evidence-pack subject_path: {subject_path}",
        )
    return _discovery_evidence_pack_handler(
        org_id,
        st,
        subject_id,
        ctx,
        db,
        include_audit_trail=include_audit_trail,
        include_linked_records=include_linked_records,
        include_sections=include_sections,
        audit_limit=audit_limit,
    )
