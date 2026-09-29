"""Gate 177: HTTP onboarding routes registered + repository round-trip."""

from __future__ import annotations

import pytest

from nativeforge.api.customer_organization_onboarding_routes import (
    demo_onboarding_router,
    real_onboarding_router,
)
from nativeforge.services.organization_onboarding_repository_service import (
    build_authority_dimension_status,
    persist_evidence,
    submit_profile_revision,
)
from nativeforge.services.tribal_authority_evidence_service import (
    DECISION_PENDING,
    ORGANIZATION_EMAIL_DOMAIN,
    build_evidence,
)

ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
SUBJECT = "member-identity-1"


def _suffixes(router) -> set[str]:
    return {getattr(r, "path", "").split("/orgs/{org_id}", 1)[-1] for r in router.routes}


def test_onboarding_routers_expose_profile_and_authority_paths():
    demo_paths = _suffixes(demo_onboarding_router)
    assert any("organization-profile" in p for p in demo_paths)
    assert any("authority/evidence" in p for p in demo_paths)
    assert any("authority/identity-state" in p for p in demo_paths)
    assert _suffixes(real_onboarding_router) == demo_paths


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_profile_revision_and_authority_dimensions_are_separate(db):
    conn = db.connection()
    rev = submit_profile_revision(
        conn,
        organization_id=ORG,
        changes={"entity_type": "FEDERALLY_RECOGNIZED_TRIBE", "legal_name": "Demo Nation"},
        changed_by=SUBJECT,
        reason="initial",
        is_demo=True,
    )
    assert rev.get("accepted") is True

    evidence = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id=ORG,
        subject_identity_id=SUBJECT,
        source_ref="demo-nation.gov",
        decision=DECISION_PENDING,
        is_demo=True,
    )
    persist_evidence(conn, evidence=evidence)

    assert evidence["establishes_affiliation"] is True
    assert evidence["establishes_authority"] is False

    status_payload = build_authority_dimension_status(
        conn, organization_id=ORG, subject_identity_id=SUBJECT
    )
    assert status_payload.get("verified") is None
    grade = status_payload["evidence_grade"]
    assert grade["supports_affiliation"] is False
    assert grade["supports_authority"] is False
    assert grade["pending_count"] >= 1
