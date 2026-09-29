"""Gate 177: organization profile and tribal authority evidence (HTTP)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    SESSION_COOKIE_NAME,
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services.customer_session_verifier_service import (
    verify_session_cookie,
)
from nativeforge.services.organization_onboarding_repository_service import (
    build_authority_dimension_status,
    list_profile_versions,
    load_latest_profile,
    persist_evidence,
    submit_profile_revision,
)
from nativeforge.services.tribal_authority_evidence_service import (
    DECISION_ACCEPTED,
    DECISION_PENDING,
    DECISION_REJECTED,
    build_evidence,
)

demo_onboarding_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["customer-onboarding-demo"],
)
real_onboarding_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["customer-onboarding-real"],
)


class ProfileRevisionBody(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=4096)


class AuthorityEvidenceBody(BaseModel):
    evidence_type: str = Field(min_length=3, max_length=64)
    source_ref: str | None = Field(default=None, max_length=2048)
    artifact_ref: str | None = Field(default=None, max_length=2048)
    issuer: str | None = Field(default=None, max_length=512)
    subject_identity_id: str | None = Field(default=None, max_length=128)


def _subject_id(cookie: str | None, body_subject: str | None) -> str:
    parsed = verify_session_cookie(cookie_value=cookie, membership_verified=False)
    principal = parsed.get("principal_id")
    if body_subject and principal and str(body_subject) != str(principal):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "subject_identity_mismatch"},
        )
    if body_subject:
        return str(body_subject)
    if principal:
        return str(principal)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "no_verified_session"},
    )


def _profile_get(org_id: uuid.UUID, ctx: OrgContext, session: Session) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    profile = load_latest_profile(
        session.connection(), organization_id=str(ctx.org_id)
    )
    return {"profile": profile, "has_profile": profile is not None}


def _profile_history(
    org_id: uuid.UUID, ctx: OrgContext, session: Session
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    versions = list_profile_versions(
        session.connection(), organization_id=str(ctx.org_id)
    )
    return {"versions": versions}


def _profile_revise(
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
    cookie: str | None,
    body: ProfileRevisionBody,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    actor = _subject_id(cookie, None)
    result = submit_profile_revision(
        session.connection(),
        organization_id=str(ctx.org_id),
        changes=body.values,
        changed_by=actor,
        reason=body.reason,
        is_demo=ctx.org_type == "demo",
    )
    if not result.get("accepted"):
        raise HTTPException(status_code=400, detail=result)
    session.commit()
    return result


def _authority_status(
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
    cookie: str | None,
    subject: str | None,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    sub = _subject_id(cookie, subject)
    return build_authority_dimension_status(
        session.connection(),
        organization_id=str(ctx.org_id),
        subject_identity_id=sub,
    )


def _submit_evidence(
    org_id: uuid.UUID,
    ctx: OrgContext,
    session: Session,
    cookie: str | None,
    body: AuthorityEvidenceBody,
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    sub = _subject_id(cookie, body.subject_identity_id)
    evidence = build_evidence(
        evidence_type=body.evidence_type.strip().upper(),
        organization_id=str(ctx.org_id),
        subject_identity_id=sub,
        source_ref=body.source_ref,
        artifact_ref=body.artifact_ref,
        issuer=body.issuer,
        decision=DECISION_PENDING,
        is_demo=ctx.org_type == "demo",
    )
    if evidence.get("decision") in (DECISION_ACCEPTED, DECISION_REJECTED):
        raise HTTPException(status_code=400, detail="customer_cannot_self_judge")
    result = persist_evidence(session.connection(), evidence=evidence)
    if not result.get("persisted"):
        raise HTTPException(status_code=400, detail=result)
    session.commit()
    return {"submitted": True, "evidence": evidence, "decision": DECISION_PENDING}


@demo_onboarding_router.get("/{org_id}/onboarding/organization-profile")
def demo_get_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _profile_get(org_id, ctx, session)


@real_onboarding_router.get("/{org_id}/onboarding/organization-profile")
def real_get_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _profile_get(org_id, ctx, session)


@demo_onboarding_router.get("/{org_id}/onboarding/organization-profile/history")
def demo_profile_history(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _profile_history(org_id, ctx, session)


@real_onboarding_router.get("/{org_id}/onboarding/organization-profile/history")
def real_profile_history(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _profile_history(org_id, ctx, session)


@demo_onboarding_router.post("/{org_id}/onboarding/organization-profile")
def demo_revise_profile(
    org_id: uuid.UUID,
    body: ProfileRevisionBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _profile_revise(org_id, ctx, session, nf_session, body)


@real_onboarding_router.post("/{org_id}/onboarding/organization-profile")
def real_revise_profile(
    org_id: uuid.UUID,
    body: ProfileRevisionBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _profile_revise(org_id, ctx, session, nf_session, body)


@demo_onboarding_router.get("/{org_id}/authority/identity-state")
def demo_identity_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "identity_status": status_payload["identity_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@real_onboarding_router.get("/{org_id}/authority/identity-state")
def real_identity_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "identity_status": status_payload["identity_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@demo_onboarding_router.get("/{org_id}/authority/affiliation-state")
def demo_affiliation_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "affiliation_status": status_payload["affiliation_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@real_onboarding_router.get("/{org_id}/authority/affiliation-state")
def real_affiliation_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "affiliation_status": status_payload["affiliation_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@demo_onboarding_router.get("/{org_id}/authority/authority-state")
def demo_authority_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "authority_status": status_payload["authority_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@real_onboarding_router.get("/{org_id}/authority/authority-state")
def real_authority_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    return {
        "authority_status": status_payload["authority_status"],
        "subject_identity_id": status_payload["subject_identity_id"],
    }


@demo_onboarding_router.get("/{org_id}/authority/review-state")
def demo_review_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    grade = status_payload.get("evidence_grade") or {}
    return {
        "review_pending": status_payload.get("review_pending"),
        "pending_evidence_count": grade.get("pending_count", 0),
        "conflicting_evidence": grade.get("conflicting_evidence"),
    }


@real_onboarding_router.get("/{org_id}/authority/review-state")
def real_review_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    subject_identity_id: str | None = None,
) -> dict[str, Any]:
    status_payload = _authority_status(
        org_id, ctx, session, nf_session, subject_identity_id
    )
    grade = status_payload.get("evidence_grade") or {}
    return {
        "review_pending": status_payload.get("review_pending"),
        "pending_evidence_count": grade.get("pending_count", 0),
        "conflicting_evidence": grade.get("conflicting_evidence"),
    }


@demo_onboarding_router.post("/{org_id}/authority/evidence")
def demo_submit_evidence(
    org_id: uuid.UUID,
    body: AuthorityEvidenceBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _submit_evidence(org_id, ctx, session, nf_session, body)


@real_onboarding_router.post("/{org_id}/authority/evidence")
def real_submit_evidence(
    org_id: uuid.UUID,
    body: AuthorityEvidenceBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    session: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    return _submit_evidence(org_id, ctx, session, nf_session, body)
