"""Query scoping: org tenant + demo/real alignment."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select

from nativeforge.db.models import (
    NfAuditEvent,
    NfGrantSpark,
    NfReviewArtifact,
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
