"""nf_review_artifacts and nf_audit_events repository (scoped queries only)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfAuditEvent,
    NfReviewArtifact,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import AuditAction, ReviewArtifactType, ReviewStatus
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    select_audit_events_for_artifact,
    select_review_artifacts_for_org,
)


def create_review_artifact(
    session: Session,
    *,
    org: Organization,
    actor_id: uuid.UUID | None,
    artifact_type: ReviewArtifactType = ReviewArtifactType.sprint0_placeholder,
) -> NfReviewArtifact:
    """Create draft artifact with is_demo aligned to org.org_type."""
    is_demo = is_demo_for_org_type(org.org_type)
    art = NfReviewArtifact(
        id=uuid.uuid4(),
        organization_id=org.id,
        is_demo=is_demo,
        artifact_type=artifact_type.value,
        review_status=ReviewStatus.draft.value,
    )
    session.add(art)
    session.flush()
    session.add(
        NfAuditEvent(
            id=uuid.uuid4(),
            organization_id=org.id,
            is_demo=is_demo,
            review_artifact_id=art.id,
            action=AuditAction.artifact_created.value,
            payload={
                "artifact_type": artifact_type.value,
                "status": ReviewStatus.draft.value,
            },
            actor_id=actor_id,
        )
    )
    return art


def list_review_artifacts(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfReviewArtifact]:
    q = select_review_artifacts_for_org(org_id=org_id, org_type=org_type)
    return list(session.scalars(q))


def get_review_artifact_scoped(
    session: Session,
    *,
    artifact_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfReviewArtifact | None:
    q = select_review_artifacts_for_org(org_id=org_id, org_type=org_type).where(
        NfReviewArtifact.id == artifact_id,
    )
    return session.scalar(q)


def list_audit_events_for_artifact(
    session: Session,
    *,
    artifact_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfAuditEvent]:
    q = select_audit_events_for_artifact(
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    return list(session.scalars(q))


def append_audit(
    session: Session,
    *,
    artifact: NfReviewArtifact,
    action: AuditAction,
    payload: dict | None,
    actor_id: uuid.UUID | None,
) -> NfAuditEvent:
    ev = NfAuditEvent(
        id=uuid.uuid4(),
        organization_id=artifact.organization_id,
        is_demo=artifact.is_demo,
        review_artifact_id=artifact.id,
        action=action.value,
        payload=payload or {},
        actor_id=actor_id,
    )
    session.add(ev)
    return ev
