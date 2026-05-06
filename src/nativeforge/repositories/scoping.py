"""Query scoping: org tenant + demo/real alignment."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, or_, select

from nativeforge.db.models import (
    NfAuditEvent,
    NfDiscoveryIntakeCandidate,
    NfDiscoveryIntakeRun,
    NfDiscoveryReviewItem,
    NfFormPackage,
    NfGrantPursuit,
    NfGrantSpark,
    NfNofoExtractionRun,
    NfOperatorAction,
    NfOpportunitySource,
    NfPursuitBrief,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    NfReviewArtifact,
    NfSourceCheckRun,
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


def nf_source_check_run_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfSourceCheckRun.organization_id == org_id,
        NfSourceCheckRun.is_demo.is_(is_demo),
    )


def select_source_check_runs_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_source_check_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfSourceCheckRun)
        .where(*scope)
        .order_by(NfSourceCheckRun.started_at.desc())
    )


def select_source_check_runs_for_source(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
) -> Select:
    scope = nf_source_check_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfSourceCheckRun)
        .where(
            NfSourceCheckRun.source_registry_id == source_registry_id,
            *scope,
        )
        .order_by(NfSourceCheckRun.started_at.desc())
    )


def select_source_check_run_scoped(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    check_run_id: uuid.UUID,
) -> Select:
    scope = nf_source_check_run_scope(org_id=org_id, org_type=org_type)
    return select(NfSourceCheckRun).where(
        NfSourceCheckRun.id == check_run_id,
        *scope,
    )


def nf_discovery_intake_run_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfDiscoveryIntakeRun.organization_id == org_id,
        NfDiscoveryIntakeRun.is_demo.is_(is_demo),
    )


def nf_discovery_intake_candidate_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfDiscoveryIntakeCandidate.organization_id == org_id,
        NfDiscoveryIntakeCandidate.is_demo.is_(is_demo),
    )


def select_discovery_intake_runs_for_org_source(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
) -> Select:
    scope = nf_discovery_intake_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfDiscoveryIntakeRun)
        .where(
            NfDiscoveryIntakeRun.source_registry_id == source_registry_id,
            *scope,
        )
        .order_by(NfDiscoveryIntakeRun.started_at.desc())
    )


def select_discovery_intake_runs_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_discovery_intake_run_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfDiscoveryIntakeRun)
        .where(*scope)
        .order_by(NfDiscoveryIntakeRun.started_at.desc())
    )


def select_discovery_intake_candidates_for_run(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_run_id: uuid.UUID,
) -> Select:
    scope = nf_discovery_intake_candidate_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfDiscoveryIntakeCandidate)
        .where(
            NfDiscoveryIntakeCandidate.intake_run_id == intake_run_id,
            *scope,
        )
        .order_by(NfDiscoveryIntakeCandidate.created_at.asc())
    )


def select_discovery_intake_candidate_scoped(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    candidate_id: uuid.UUID,
) -> Select:
    scope = nf_discovery_intake_candidate_scope(org_id=org_id, org_type=org_type)
    return select(NfDiscoveryIntakeCandidate).where(
        NfDiscoveryIntakeCandidate.id == candidate_id,
        *scope,
    )


def nf_discovery_review_item_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfDiscoveryReviewItem.organization_id == org_id,
        NfDiscoveryReviewItem.is_demo.is_(is_demo),
    )


def select_discovery_review_items_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfDiscoveryReviewItem)
        .where(*scope)
        .order_by(
            NfDiscoveryReviewItem.priority.desc(),
            NfDiscoveryReviewItem.created_at.asc(),
        )
    )


def select_discovery_review_item_scoped(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    review_item_id: uuid.UUID,
) -> Select:
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    return select(NfDiscoveryReviewItem).where(
        NfDiscoveryReviewItem.id == review_item_id,
        *scope,
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


def nf_operator_action_scope(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> tuple:
    is_demo = org_type == "demo"
    return (
        NfOperatorAction.organization_id == org_id,
        NfOperatorAction.is_demo.is_(is_demo),
    )


def select_operator_actions_for_org(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> Select:
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    return (
        select(NfOperatorAction)
        .where(*scope)
        .order_by(NfOperatorAction.updated_at.desc())
    )


def select_operator_action_scoped(
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    operator_action_id: uuid.UUID,
) -> Select:
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    return select(NfOperatorAction).where(
        NfOperatorAction.id == operator_action_id,
        *scope,
    )
