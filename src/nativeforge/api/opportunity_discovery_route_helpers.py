"""Shared helpers for Discovery Engine HTTP routes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.opportunity_discovery_schemas import (
    DiscoverySparkCreateBody,
    OpportunitySourceCreateBody,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.domain.enums import EvidencePackSubjectType
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import discovery_evidence_pack_service as ev_pack_svc
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.opportunity_discovery_service import (
    DiscoverySparkSeedPayload,
    OpportunitySourcePayload,
)


def same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def maybe_filter_coverage_intel(
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


def source_payload_from_body(
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


def body_to_discovery_seed(
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


def validate_registry_id(
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


def discovery_evidence_pack_handler(
    org_id: uuid.UUID,
    subject_type: EvidencePackSubjectType,
    subject_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
    *,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        return ev_pack_svc.build_discovery_evidence_pack(
            db,
            org,
            ctx.org_type,
            subject_type,
            subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
