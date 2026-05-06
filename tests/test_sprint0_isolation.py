"""Sprint 0 — demo/real query isolation on nf_* rows."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nativeforge.db.models import NfReviewArtifact, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import ReviewArtifactType, ReviewStatus
from nativeforge.repositories import review_artifacts as ra_repo


@pytest.fixture
def db() -> Session:
    with SessionLocal() as s:
        yield s
        s.rollback()


def _seed_orgs(session: Session) -> tuple[Organization, Organization]:
    real = Organization(id=uuid.uuid4(), org_type="real")
    demo = Organization(id=uuid.uuid4(), org_type="demo")
    session.add_all([real, demo])
    session.commit()
    return real, demo


def test_list_scoped_real_does_not_see_demo_artifact(db: Session) -> None:
    real_org, demo_org = _seed_orgs(db)
    demo_art = ra_repo.create_review_artifact(
        db,
        org=demo_org,
        actor_id=None,
        artifact_type=ReviewArtifactType.sprint0_placeholder,
    )
    db.commit()
    assert demo_art.is_demo is True

    visible = ra_repo.list_review_artifacts(db, org_id=real_org.id, org_type="real")
    assert visible == []

    demo_visible = ra_repo.list_review_artifacts(
        db, org_id=demo_org.id, org_type="demo"
    )
    assert len(demo_visible) == 1
    assert demo_visible[0].id == demo_art.id


def test_list_scoped_demo_does_not_see_real_artifact(db: Session) -> None:
    real_org, demo_org = _seed_orgs(db)
    ra_repo.create_review_artifact(db, org=real_org, actor_id=None)
    db.commit()

    demo_visible = ra_repo.list_review_artifacts(
        db, org_id=demo_org.id, org_type="demo"
    )
    assert demo_visible == []

    real_visible = ra_repo.list_review_artifacts(
        db, org_id=real_org.id, org_type="real"
    )
    assert len(real_visible) == 1


def test_trigger_rejects_is_demo_mismatch(db: Session) -> None:
    real_org, _ = _seed_orgs(db)
    bad = NfReviewArtifact(
        id=uuid.uuid4(),
        organization_id=real_org.id,
        is_demo=True,
        artifact_type=ReviewArtifactType.sprint0_placeholder.value,
        review_status=ReviewStatus.draft.value,
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cross_tenant_no_leakage_fuzz(db: Session) -> None:
    orgs: list[Organization] = []
    for _ in range(5):
        o = Organization(id=uuid.uuid4(), org_type="demo" if len(orgs) % 2 else "real")
        orgs.append(o)
        db.add(o)
    db.commit()

    for org in orgs:
        ra_repo.create_review_artifact(db, org=org, actor_id=None)
    db.commit()

    for org in orgs:
        expected_demo = org.org_type == "demo"
        ot: str = "demo" if expected_demo else "real"
        rows = ra_repo.list_review_artifacts(db, org_id=org.id, org_type=ot)
        assert len(rows) == 1
        assert rows[0].organization_id == org.id
        assert rows[0].is_demo == expected_demo
