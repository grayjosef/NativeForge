"""Operator affiliation/authority evidence review seam (Gate 177)."""

from __future__ import annotations

import pytest

from nativeforge.services.organization_onboarding_repository_service import (
    build_authority_dimension_status,
    persist_evidence,
)
from nativeforge.services.tribal_authority_evidence_service import (
    DECISION_PENDING,
    IDENTITY_PROVIDER_ASSERTION,
    ORGANIZATION_EMAIL_DOMAIN,
    TRIBAL_RESOLUTION,
    build_evidence,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_VERIFIED,
    AUTHORITY_DOCUMENT_VERIFIED,
    AUTHORITY_UNVERIFIED,
    IDENTITY_UNVERIFIED,
)
from nativeforge.services.tribal_authority_operator_review_service import (
    OPERATOR_APPROVAL_TOKEN,
    operator_decide_evidence,
    operator_list_pending,
    operator_verify_authority_manually,
)

ORG = "cccccccc-dddd-eeee-ffff-111111111111"
SUBJECT = "subject-member-77"
REVIEWER = "controlling-company:reviewer-1"


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def operator_env(monkeypatch):
    monkeypatch.setenv(
        "NF_AUTHORITY_REVIEW_OPERATOR_APPROVAL", OPERATOR_APPROVAL_TOKEN
    )


def test_operator_pending_requires_approval(db):
    out = operator_list_pending(db.connection(), operator_approval=None)
    assert out["accepted"] is False


def test_affiliation_review_updates_grant_without_self_approval(
    db, operator_env
):
    conn = db.connection()
    pending = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id=ORG,
        subject_identity_id=SUBJECT,
        source_ref="nation.example.test",
        decision=DECISION_PENDING,
        is_demo=True,
    )
    persist_evidence(conn, evidence=pending)

    refused = operator_decide_evidence(
        conn,
        evidence_id=pending["evidence_id"],
        decision="ACCEPTED",
        reviewer=SUBJECT,
        reason="self",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    assert refused["accepted"] is False
    assert refused["why"] == "self_approval_forbidden"

    accepted = operator_decide_evidence(
        conn,
        evidence_id=pending["evidence_id"],
        decision="ACCEPTED",
        reviewer=REVIEWER,
        reason="domain roster matches council list",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    assert accepted["accepted"] is True

    status_payload = build_authority_dimension_status(
        conn, organization_id=ORG, subject_identity_id=SUBJECT
    )
    assert status_payload["affiliation_status"] == AFFILIATION_VERIFIED
    assert status_payload["authority_status"] == AUTHORITY_UNVERIFIED
    assert status_payload["identity_status"] == IDENTITY_UNVERIFIED
    assert status_payload["review_pending"] is False


def test_authority_evidence_review_can_reach_document_verified(db, operator_env):
    conn = db.connection()
    pending = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id=ORG,
        subject_identity_id=SUBJECT,
        source_ref="doc:council-resolution-2026",
        decision=DECISION_PENDING,
        is_demo=True,
    )
    persist_evidence(conn, evidence=pending)

    identity_pending = build_evidence(
        evidence_type=IDENTITY_PROVIDER_ASSERTION,
        organization_id=ORG,
        subject_identity_id=SUBJECT,
        source_ref="oidc:accounts.google.com",
        decision=DECISION_PENDING,
        is_demo=True,
    )
    persist_evidence(conn, evidence=identity_pending)
    identity_decision = operator_decide_evidence(
        conn,
        evidence_id=identity_pending["evidence_id"],
        decision="ACCEPTED",
        reviewer=REVIEWER,
        reason="IdP assertion matches council roster",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    assert identity_decision["accepted"] is True

    affiliation_pending = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id=ORG,
        subject_identity_id=SUBJECT,
        source_ref="nation.example.test",
        decision=DECISION_PENDING,
        is_demo=True,
    )
    persist_evidence(conn, evidence=affiliation_pending)
    operator_decide_evidence(
        conn,
        evidence_id=affiliation_pending["evidence_id"],
        decision="ACCEPTED",
        reviewer=REVIEWER,
        reason="domain control verified",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )

    result = operator_decide_evidence(
        conn,
        evidence_id=pending["evidence_id"],
        decision="ACCEPTED",
        reviewer=REVIEWER,
        reason="resolution verified against official record",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    assert result["accepted"] is True
    status_payload = build_authority_dimension_status(
        conn, organization_id=ORG, subject_identity_id=SUBJECT
    )
    assert status_payload["authority_status"] == AUTHORITY_DOCUMENT_VERIFIED
    assert status_payload["affiliation_status"] == AFFILIATION_VERIFIED


def test_manual_verify_persists_controlling_company_grant(db, operator_env):
    conn = db.connection()
    result = operator_verify_authority_manually(
        conn,
        organization_id=ORG,
        identity_id=SUBJECT,
        verified_by=REVIEWER,
        reason="chair confirmed for first customer onboarding",
        operator_actor="op-1",
        operator_approval=OPERATOR_APPROVAL_TOKEN,
        is_demo=True,
    )
    assert result["accepted"] is True
    status_payload = build_authority_dimension_status(
        conn, organization_id=ORG, subject_identity_id=SUBJECT
    )
    assert status_payload["authority_status"] == "MANUALLY_VERIFIED"
