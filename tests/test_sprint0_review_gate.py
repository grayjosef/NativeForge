"""Sprint 0 — review-gate transitions and auditable blocked finalization."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

import nativeforge.services.review_gate_service as rg
from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, ReviewStatus
from nativeforge.repositories import review_artifacts as ra_repo


@pytest.fixture
def db() -> Session:
    with SessionLocal() as s:
        yield s
        s.rollback()


def _org_demo(db: Session) -> Organization:
    o = Organization(id=uuid.uuid4(), org_type="demo")
    db.add(o)
    db.commit()
    return o


def test_finalize_blocked_from_draft_audit(db: Session) -> None:
    org = _org_demo(db)
    art = ra_repo.create_review_artifact(db, org=org, actor_id=None)
    db.commit()
    actor = uuid.uuid4()

    with pytest.raises(rg.ReviewGateError):
        rg.finalize(
            db,
            org_id=org.id,
            org_type="demo",
            artifact_id=art.id,
            actor_id=actor,
        )

    evs = ra_repo.list_audit_events_for_artifact(
        db,
        artifact_id=art.id,
        org_id=org.id,
        org_type="demo",
    )
    blocked = [e for e in evs if e.action == AuditAction.transition_rejected.value]
    assert len(blocked) == 1
    assert blocked[0].payload.get("reason") == "finalize_requires_approved"


def test_finalize_allowed_after_approve(db: Session) -> None:
    org = _org_demo(db)
    art = ra_repo.create_review_artifact(db, org=org, actor_id=None)
    db.commit()

    rg.request_review(
        db,
        org_id=org.id,
        org_type="demo",
        artifact_id=art.id,
        actor_id=None,
    )
    rg.approve(
        db,
        org_id=org.id,
        org_type="demo",
        artifact_id=art.id,
        actor_id=None,
    )
    db.commit()

    rg.finalize(
        db,
        org_id=org.id,
        org_type="demo",
        artifact_id=art.id,
        actor_id=None,
    )
    db.commit()

    db.refresh(art)
    assert art.review_status == ReviewStatus.finalized.value


def test_finalize_rejected_fails(db: Session) -> None:
    org = _org_demo(db)
    art = ra_repo.create_review_artifact(db, org=org, actor_id=None)
    db.commit()
    rg.request_review(
        db,
        org_id=org.id,
        org_type="demo",
        artifact_id=art.id,
        actor_id=None,
    )
    rg.reject(
        db,
        org_id=org.id,
        org_type="demo",
        artifact_id=art.id,
        actor_id=None,
    )
    db.commit()

    with pytest.raises(rg.ReviewGateError):
        rg.finalize(
            db,
            org_id=org.id,
            org_type="demo",
            artifact_id=art.id,
            actor_id=None,
        )


def test_invalid_transitions(db: Session) -> None:
    org = _org_demo(db)
    art = ra_repo.create_review_artifact(db, org=org, actor_id=None)
    db.commit()

    with pytest.raises(rg.ReviewGateError):
        rg.approve(
            db,
            org_id=org.id,
            org_type="demo",
            artifact_id=art.id,
            actor_id=None,
        )

    with pytest.raises(rg.ReviewGateError):
        rg.finalize(
            db,
            org_id=org.id,
            org_type="demo",
            artifact_id=art.id,
            actor_id=None,
        )
