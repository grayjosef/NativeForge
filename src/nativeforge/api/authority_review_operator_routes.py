"""Operator HTTP seam for tribal affiliation/authority evidence review."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import get_db_session
from nativeforge.services.tribal_authority_operator_review_service import (
    OPERATOR_APPROVAL_ENV,
    operator_decide_evidence,
    operator_list_pending,
    operator_verify_authority_manually,
)

router = APIRouter(
    prefix="/api/authority-review/operator",
    tags=["authority-review-operator"],
)

APPROVAL_HEADER = "X-NF-Authority-Review-Operator-Approval"


class EvidenceDecisionBody(BaseModel):
    evidence_id: str = Field(min_length=8, max_length=64)
    decision: str = Field(min_length=4, max_length=16)
    reviewer: str = Field(min_length=2, max_length=128)
    reason: str = Field(min_length=3, max_length=4096)
    operator_actor: str = Field(min_length=2, max_length=128)


class ManualAuthorityBody(BaseModel):
    organization_id: str = Field(min_length=8, max_length=64)
    identity_id: str = Field(min_length=2, max_length=128)
    verified_by: str = Field(min_length=2, max_length=128)
    reason: str = Field(min_length=3, max_length=4096)
    operator_actor: str = Field(min_length=2, max_length=128)
    customer_relationship_ref: str | None = Field(default=None, max_length=512)
    is_demo: bool = False


def _approval(
    x_nf_authority_review_operator_approval: Annotated[
        str | None, Header(alias=APPROVAL_HEADER)
    ] = None,
) -> str | None:
    return x_nf_authority_review_operator_approval


@router.get("/pending-evidence")
def list_pending(
    db: Annotated[Session, Depends(get_db_session)],
    approval: Annotated[str | None, Depends(_approval)],
    organization_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    result = operator_list_pending(
        db.connection(),
        organization_id=organization_id,
        limit=limit,
        operator_approval=approval,
    )
    if not result.get("accepted"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": result.get("why"),
                "env_var": result.get("env_var", OPERATOR_APPROVAL_ENV),
                "header": APPROVAL_HEADER,
            },
        )
    return result


@router.post("/evidence/decide")
def decide_evidence(
    body: EvidenceDecisionBody,
    db: Annotated[Session, Depends(get_db_session)],
    approval: Annotated[str | None, Depends(_approval)],
) -> dict[str, Any]:
    result = operator_decide_evidence(
        db.connection(),
        evidence_id=body.evidence_id,
        decision=body.decision.strip().upper(),
        reviewer=body.reviewer.strip(),
        reason=body.reason.strip(),
        operator_actor=body.operator_actor.strip(),
        operator_approval=approval,
    )
    if not result.get("accepted"):
        code = (
            status.HTTP_403_FORBIDDEN
            if result.get("why") == "operator_approval_required"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=result)
    db.commit()
    return result


@router.post("/authority/manual-verify")
def manual_verify(
    body: ManualAuthorityBody,
    db: Annotated[Session, Depends(get_db_session)],
    approval: Annotated[str | None, Depends(_approval)],
) -> dict[str, Any]:
    result = operator_verify_authority_manually(
        db.connection(),
        organization_id=body.organization_id,
        identity_id=body.identity_id,
        verified_by=body.verified_by.strip(),
        reason=body.reason.strip(),
        operator_actor=body.operator_actor.strip(),
        operator_approval=approval,
        customer_relationship_ref=body.customer_relationship_ref,
        is_demo=body.is_demo,
    )
    if not result.get("accepted"):
        code = (
            status.HTTP_403_FORBIDDEN
            if result.get("why") == "operator_approval_required"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=result)
    db.commit()
    return result
