"""Server-enforced review gate (Sprint 0)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from nativeforge.db.models import NfReviewArtifact
from nativeforge.domain.enums import AuditAction, ReviewStatus
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import organizations as org_repo
from nativeforge.repositories import review_artifacts as ra_repo


class ReviewGateError(ValueError):
    """Invalid review state transition."""


@dataclass(frozen=True, slots=True)
class TransitionResult:
    artifact: NfReviewArtifact
    audit_action: AuditAction


def _emit_transition(
    session: Session,
    *,
    artifact: NfReviewArtifact,
    to_status: ReviewStatus,
    action: AuditAction,
    actor_id: uuid.UUID | None,
    note: str | None = None,
) -> None:
    artifact.review_status = to_status.value
    ra_repo.append_audit(
        session,
        artifact=artifact,
        action=action,
        payload=(
            {"to": to_status.value, "note": note} if note else {"to": to_status.value}
        ),
        actor_id=actor_id,
    )


def request_review(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> TransitionResult:
    art = ra_repo.get_review_artifact_scoped(
        session,
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    if art is None:
        raise ReviewGateError("artifact not found")
    current = ReviewStatus(art.review_status)
    if current is not ReviewStatus.draft:
        raise ReviewGateError("only draft artifacts can move to pending_review")
    _emit_transition(
        session,
        artifact=art,
        to_status=ReviewStatus.pending_review,
        action=AuditAction.review_requested,
        actor_id=actor_id,
    )
    return TransitionResult(artifact=art, audit_action=AuditAction.review_requested)


def approve(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    note: str | None = None,
) -> TransitionResult:
    art = ra_repo.get_review_artifact_scoped(
        session,
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    if art is None:
        raise ReviewGateError("artifact not found")
    current = ReviewStatus(art.review_status)
    if current is not ReviewStatus.pending_review:
        raise ReviewGateError("only pending_review artifacts can be approved")
    _emit_transition(
        session,
        artifact=art,
        to_status=ReviewStatus.approved,
        action=AuditAction.approved,
        actor_id=actor_id,
        note=note,
    )
    return TransitionResult(artifact=art, audit_action=AuditAction.approved)


def reject(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    note: str | None = None,
) -> TransitionResult:
    art = ra_repo.get_review_artifact_scoped(
        session,
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    if art is None:
        raise ReviewGateError("artifact not found")
    current = ReviewStatus(art.review_status)
    if current is not ReviewStatus.pending_review:
        raise ReviewGateError("only pending_review artifacts can be rejected")
    _emit_transition(
        session,
        artifact=art,
        to_status=ReviewStatus.rejected,
        action=AuditAction.rejected,
        actor_id=actor_id,
        note=note,
    )
    return TransitionResult(artifact=art, audit_action=AuditAction.rejected)


def reset_to_draft(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> TransitionResult:
    art = ra_repo.get_review_artifact_scoped(
        session,
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    if art is None:
        raise ReviewGateError("artifact not found")
    current = ReviewStatus(art.review_status)
    if current is not ReviewStatus.rejected:
        raise ReviewGateError("only rejected artifacts can reset to draft")
    _emit_transition(
        session,
        artifact=art,
        to_status=ReviewStatus.draft,
        action=AuditAction.reset_to_draft,
        actor_id=actor_id,
    )
    return TransitionResult(artifact=art, audit_action=AuditAction.reset_to_draft)


def finalize(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    artifact_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> TransitionResult:
    art = ra_repo.get_review_artifact_scoped(
        session,
        artifact_id=artifact_id,
        org_id=org_id,
        org_type=org_type,
    )
    if art is None:
        raise ReviewGateError("artifact not found")
    current = ReviewStatus(art.review_status)
    if current is ReviewStatus.finalized:
        raise ReviewGateError("artifact already finalized")
    if current is not ReviewStatus.approved:
        ra_repo.append_audit(
            session,
            artifact=art,
            action=AuditAction.transition_rejected,
            payload={
                "reason": "finalize_requires_approved",
                "current": current.value,
            },
            actor_id=actor_id,
        )
        session.commit()
        raise ReviewGateError("finalization requires approved status")
    _emit_transition(
        session,
        artifact=art,
        to_status=ReviewStatus.finalized,
        action=AuditAction.finalized,
        actor_id=actor_id,
    )
    return TransitionResult(artifact=art, audit_action=AuditAction.finalized)


def load_org(session: Session, org_id: uuid.UUID):
    return org_repo.get_organization(session, org_id)
