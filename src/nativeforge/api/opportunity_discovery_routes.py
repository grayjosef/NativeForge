"""Discovery Engine routes — source registry and Grant Spark discovery intake."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.db.models import is_demo_for_org_type
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryIntakeMode,
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    ExpectedOpportunityFrequency,
    FundingInstrument,
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceCheckMethod,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourcePriorityLevel,
    SourceReliabilityRating,
)
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.repositories import organizations as org_repo
from nativeforge.repositories import source_check_runs as scr_repo
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import discovery_intake_service as d_intake
from nativeforge.services import discovery_operator_workbench_service as op_wb
from nativeforge.services import discovery_review_service as d_review
from nativeforge.services import grant_spark_service as gss
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.grant_spark_service import DuplicateGrantSparkError
from nativeforge.services.opportunity_discovery_service import (
    DiscoverySparkSeedPayload,
    OpportunitySourcePayload,
)


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _maybe_filter_coverage_intel(
    db: Session,
    ctx: OrgContext,
    full: dict[str, Any],
    *,
    severity: str | None,
    gap_type: str | None,
    domain: str | None,
    source_type: str | None,
    priority_level: str | None,
    limit: int | None,
) -> dict[str, Any]:
    rows = ods.list_sources(db, org_id=ctx.org_id, org_type=ctx.org_type)
    by_id = {str(r.id): r for r in rows}
    if (
        severity is None
        and gap_type is None
        and domain is None
        and source_type is None
        and priority_level is None
        and limit is None
    ):
        return full
    return dcg_svc.filter_coverage_gap_payload(
        full,
        rows_by_id=by_id,
        severity=severity,
        gap_type=gap_type,
        domain=domain,
        source_type=source_type,
        priority_level=priority_level,
        limit=limit,
    )


class OpportunitySourceCreateBody(BaseModel):
    source_name: str = Field(min_length=1, max_length=512)
    source_type: OpportunitySourceType
    source_url: str | None = Field(default=None, max_length=2048)
    publisher_name: str | None = Field(default=None, max_length=512)
    description: str | None = None
    geographic_scope_json: dict | list | None = None
    native_relevance_notes: str | None = None
    reliability_rating: SourceReliabilityRating = SourceReliabilityRating.unknown
    freshness_interval_days: int | None = Field(default=None, ge=1, le=3650)
    verification_status: OpportunityVerificationStatus = (
        OpportunityVerificationStatus.unverified
    )
    is_active: bool = True
    scope_global: bool = False
    funding_domains_json: list[str] | None = None
    applicant_types_json: list | dict | None = None
    covered_states_json: list[str] | None = None
    covered_regions_json: list | None = None
    covered_tribal_groups_json: list[str] | None = None
    coverage_notes: str | None = None
    check_method: SourceCheckMethod = SourceCheckMethod.unknown
    expected_opportunity_frequency: ExpectedOpportunityFrequency = (
        ExpectedOpportunityFrequency.unknown
    )
    priority_level: SourcePriorityLevel = SourcePriorityLevel.medium


def _source_payload_from_body(
    body: OpportunitySourceCreateBody,
) -> OpportunitySourcePayload:
    return OpportunitySourcePayload(
        source_name=body.source_name,
        source_type=body.source_type,
        source_url=body.source_url,
        publisher_name=body.publisher_name,
        description=body.description,
        geographic_scope_json=body.geographic_scope_json,
        native_relevance_notes=body.native_relevance_notes,
        reliability_rating=body.reliability_rating,
        freshness_interval_days=body.freshness_interval_days,
        verification_status=body.verification_status,
        is_active=body.is_active,
        scope_global=body.scope_global,
        funding_domains_json=body.funding_domains_json,
        applicant_types_json=body.applicant_types_json,
        covered_states_json=body.covered_states_json,
        covered_regions_json=body.covered_regions_json,
        covered_tribal_groups_json=body.covered_tribal_groups_json,
        coverage_notes=body.coverage_notes,
        check_method=body.check_method,
        expected_opportunity_frequency=body.expected_opportunity_frequency,
        priority_level=body.priority_level,
    )


class DiscoverySparkCreateBody(BaseModel):
    source: GrantSparkSource
    source_id: str = Field(min_length=1, max_length=256)
    agency: str = Field(min_length=1, max_length=512)
    opportunity_title: str = Field(min_length=1, max_length=512)
    award_type: GrantAwardType
    opportunity_source_type: OpportunitySourceType
    sub_agency: str | None = Field(default=None, max_length=512)
    program_name: str | None = Field(default=None, max_length=512)
    opportunity_number: str | None = Field(default=None, max_length=128)
    cfda_assistance_listing: str | None = Field(default=None, max_length=64)
    url: str | None = Field(default=None, max_length=2048)
    source_url: str | None = Field(default=None, max_length=2048)
    publisher_name: str | None = Field(default=None, max_length=512)
    posted_date: date | None = None
    loi_deadline: datetime | None = None
    application_deadline: datetime | None = None
    performance_period_start: date | None = None
    performance_period_end: date | None = None
    raw_nofo_text: str | None = None
    raw_nofo_url: str | None = Field(default=None, max_length=2048)
    eligibility_tags: list[str] | None = None
    eligibility_tags_json: dict | list | None = None
    geographic_scope_json: dict | list | None = None
    applicant_types_json: list | dict | None = None
    funding_instrument: FundingInstrument | None = None
    tribal_eligible: bool = False
    pipeline_stage: GrantPipelineStage = GrantPipelineStage.new
    source_registry_id: uuid.UUID | None = None
    verification_status: OpportunityVerificationStatus | None = None
    discovered_at: datetime | None = None
    last_verified_at: datetime | None = None
    duplicate_cluster_id: uuid.UUID | None = None
    stale_after_days: int = Field(default=90, ge=1, le=3650)


def _body_to_discovery_seed(
    body: DiscoverySparkCreateBody,
) -> DiscoverySparkSeedPayload:
    return DiscoverySparkSeedPayload(
        source=body.source,
        source_id=body.source_id,
        agency=body.agency,
        opportunity_title=body.opportunity_title,
        award_type=body.award_type,
        opportunity_source_type=body.opportunity_source_type,
        sub_agency=body.sub_agency,
        program_name=body.program_name,
        opportunity_number=body.opportunity_number,
        cfda_assistance_listing=body.cfda_assistance_listing,
        url=body.url,
        source_url=body.source_url,
        publisher_name=body.publisher_name,
        posted_date=body.posted_date,
        loi_deadline=body.loi_deadline,
        application_deadline=body.application_deadline,
        performance_period_start=body.performance_period_start,
        performance_period_end=body.performance_period_end,
        raw_nofo_text=body.raw_nofo_text,
        raw_nofo_url=body.raw_nofo_url,
        eligibility_tags=body.eligibility_tags,
        eligibility_tags_json=body.eligibility_tags_json,
        geographic_scope_json=body.geographic_scope_json,
        applicant_types_json=body.applicant_types_json,
        funding_instrument=body.funding_instrument,
        tribal_eligible=body.tribal_eligible,
        pipeline_stage=body.pipeline_stage,
        source_registry_id=body.source_registry_id,
        verification_status=body.verification_status,
        discovered_at=body.discovered_at,
        last_verified_at=body.last_verified_at,
        duplicate_cluster_id=body.duplicate_cluster_id,
        stale_after_days=body.stale_after_days,
    )


class DiscoveryIntakeRunCreateBody(BaseModel):
    intake_mode: DiscoveryIntakeMode
    operator_note: str | None = Field(default=None, max_length=4096)


class StructuredCandidatesBatchBody(BaseModel):
    candidates: list[dict[str, Any]]


class ReviewItemPatchBody(BaseModel):
    review_status: DiscoveryReviewQueueStatus | None = None
    review_notes: str | None = Field(default=None, max_length=65536)
    assigned_to: str | None = Field(default=None, max_length=512)
    recommended_action: DiscoveryRecommendedAction | None = None
    priority: int | None = Field(default=None, ge=-(10**9), le=10**9)


class SourceCheckRunCreateBody(BaseModel):
    check_mode: SourceCheckMode
    operator_notes: str | None = Field(default=None, max_length=65536)
    checked_for_period_start: datetime | None = None
    checked_for_period_end: datetime | None = None


class SourceCheckRunPatchBody(BaseModel):
    check_status: SourceCheckRunStatus
    opportunities_seen_count: int = 0
    new_candidates_count: int = 0
    accepted_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    review_items_created_count: int = 0
    error_code: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    operator_notes: str | None = Field(default=None, max_length=65536)
    result_summary: dict[str, Any] | None = None


def _validate_registry_id(
    db: Session,
    *,
    org_id: uuid.UUID,
    org_type: str,
    registry_id: uuid.UUID | None,
) -> None:
    if registry_id is None:
        return
    row = os_repo.get_opportunity_source_scoped(
        session=db,
        source_id=registry_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_registry_id not found in this organization Discovery scope",
        )


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
