"""Query scoping: org tenant + demo/real alignment."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, or_, select

from nativeforge.db.models import (
    NfAuditEvent,
    NfFormPackage,
    NfGrantPursuit,
    NfGrantSpark,
    NfNofoExtractionRun,
    NfOpportunitySource,
    NfPursuitBrief,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    NfReviewArtifact,
    NfSparkRequirement,
    NfSparkScore,
    NfTribalProfile,
)
from nativeforge.lib.demo_isolation import OrgType


def nf_artifact_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    """AND filters for NF review artifact rows visible in reader context."""
    is_demo = org_type == "demo"
    return (
        NfReviewArtifact.organization_id == org_id,
        NfReviewArtifact.is_demo.is_(is_demo),
    )


def nf_audit_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfAuditEvent.organization_id == org_id,
        NfAuditEvent.is_demo.is_(is_demo),
    )


def nf_tribal_profile_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfTribalProfile.organization_id == org_id,
        NfTribalProfile.is_demo.is_(is_demo),
    )


def select_tribal_profile_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_tribal_profile_scope(org_id=org_id, org_type=org_type)
    return select(NfTribalProfile).where(*scope)


def nf_grant_spark_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfGrantSpark.organization_id == org_id,
        NfGrantSpark.is_demo.is_(is_demo),
    )


def nf_opportunity_source_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
):
    """Rows visible to an org: tenant-owned plus global (NULL org_id) for this plane."""
    is_demo = org_type == "demo"
    tenant_match = and_(
        NfOpportunitySource.organization_id == org_id,
        NfOpportunitySource.is_demo.is_(is_demo),
    )
    global_match = and_(
        NfOpportunitySource.organization_id.is_(None),
        NfOpportunitySource.is_demo.is_(is_demo),
    )
    return (or_(tenant_match, global_match),)


def select_opportunity_sources_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_opportunity_source_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfOpportunitySource)
        .where(*scope)
        .order_by(NfOpportunitySource.source_name.asc())
    )


def nf_nofo_extraction_run_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfNofoExtractionRun.organization_id == org_id,
        NfNofoExtractionRun.is_demo.is_(is_demo),
    )


def nf_spark_requirement_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfSparkRequirement.organization_id == org_id,
        NfSparkRequirement.is_demo.is_(is_demo),
    )


def select_latest_nofo_run_for_spark(
    *,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_nofo_extraction_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfNofoExtractionRun)
        .where(NfNofoExtractionRun.grant_spark_id == spark_id)
        .where(*scope)
        .order_by(NfNofoExtractionRun.created_at.desc())
        .limit(1)
    )


def select_nofo_extraction_runs_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_nofo_extraction_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfNofoExtractionRun)
        .where(*scope)
        .order_by(NfNofoExtractionRun.created_at.desc())
    )


def select_requirements_for_extraction_run(
    *,
    extraction_run_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_spark_requirement_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfSparkRequirement)
        .where(NfSparkRequirement.extraction_run_id == extraction_run_id)
        .where(*scope)
        .order_by(NfSparkRequirement.sort_order.asc())
    )


def nf_spark_score_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfSparkScore.organization_id == org_id,
        NfSparkScore.is_demo.is_(is_demo),
    )


def select_latest_spark_score_for_spark(
    *,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_spark_score_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfSparkScore)
        .where(NfSparkScore.grant_spark_id == spark_id)
        .where(*scope)
        .order_by(NfSparkScore.created_at.desc())
        .limit(1)
    )


def select_spark_scores_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_spark_score_scope(org_id=org_id, org_type=org_type)
    return select(NfSparkScore).where(*scope).order_by(NfSparkScore.created_at.desc())


def select_grant_sparks_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_grant_spark_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfGrantSpark)
        .where(*scope)
        .order_by(
            NfGrantSpark.application_deadline.asc().nulls_last(),
        )
    )


def select_review_artifacts_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_artifact_scope(org_id=org_id, org_type=org_type)
    return select(NfReviewArtifact).where(*scope)


def select_audit_events_for_artifact(
    *,
    artifact_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_audit_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfAuditEvent)
        .where(NfAuditEvent.review_artifact_id == artifact_id)
        .where(*scope)
        .order_by(NfAuditEvent.created_at.asc())
    )


def select_audit_events_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    limit: int,
) -> Select:
    scope = nf_audit_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfAuditEvent)
        .where(*scope)
        .order_by(NfAuditEvent.created_at.desc())
        .limit(limit)
    )


def nf_grant_pursuit_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfGrantPursuit.organization_id == org_id,
        NfGrantPursuit.is_demo.is_(is_demo),
    )


def nf_pursuit_task_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfPursuitTask.organization_id == org_id,
        NfPursuitTask.is_demo.is_(is_demo),
    )


def nf_pursuit_calendar_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfPursuitCalendarEvent.organization_id == org_id,
        NfPursuitCalendarEvent.is_demo.is_(is_demo),
    )


def select_grant_pursuits_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_grant_pursuit_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfGrantPursuit).where(*scope).order_by(NfGrantPursuit.updated_at.desc())
    )


def nf_form_package_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfFormPackage.organization_id == org_id,
        NfFormPackage.is_demo.is_(is_demo),
    )


def nf_pursuit_brief_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfPursuitBrief.organization_id == org_id,
        NfPursuitBrief.is_demo.is_(is_demo),
    )


def select_latest_pursuit_brief_for_spark(
    *,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_pursuit_brief_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfPursuitBrief)
        .where(NfPursuitBrief.grant_spark_id == spark_id)
        .where(*scope)
        .order_by(NfPursuitBrief.created_at.desc())
        .limit(1)
    )


def select_latest_pursuit_brief_for_pursuit(
    *,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_pursuit_brief_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfPursuitBrief)
        .where(NfPursuitBrief.pursuit_id == pursuit_id)
        .where(*scope)
        .order_by(NfPursuitBrief.created_at.desc())
        .limit(1)
    )


def select_form_package_for_pursuit(
    *,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_form_package_scope(org_id=org_id, org_type=org_type)
    return select(NfFormPackage).where(
        NfFormPackage.grant_pursuit_id == pursuit_id,
        *scope,
    )


def select_form_packages_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_form_package_scope(org_id=org_id, org_type=org_type)
    return select(NfFormPackage).where(*scope).order_by(NfFormPackage.created_at.desc())


def select_calendar_events_for_org_between(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    start_at: datetime,
    end_at: datetime,
) -> Select:
    scope = nf_pursuit_calendar_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfPursuitCalendarEvent)
        .where(*scope)
        .where(NfPursuitCalendarEvent.occurs_at >= start_at)
        .where(NfPursuitCalendarEvent.occurs_at <= end_at)
        .order_by(NfPursuitCalendarEvent.occurs_at.asc())
    )
