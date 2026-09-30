"""Commercial intent and operator provisioning (no payment checkout)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import get_db_session
from nativeforge.services.customer_commercial_provisioning_service import (
    OPERATOR_APPROVAL_ENV,
    commercial_entitlement_granted_contract,
    create_commercial_intent,
    load_status_for_identity,
    operator_fulfill_provisioning_request,
    verify_operator_approval,
)
from nativeforge.services.customer_session_verifier_service import verify_session_cookie
from nativeforge.services.customer_workspace_lane_service import resolve_workspace_lane
from nativeforge.services.identity_org_session_resolution_service import (
    resolve_session_organization,
)

router = APIRouter(prefix="/api/commercial-provisioning", tags=["commercial-provisioning"])

SESSION_COOKIE_NAME = "nf_session"


def _session_identity(
    db: Annotated[Session, Depends(get_db_session)],
    nf_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, Any]:
    parsed = verify_session_cookie(cookie_value=nf_session, membership_verified=False)
    if not parsed.get("session_cookie_valid") or not parsed.get("principal_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "authentication_required"},
        )
    membership_verified = False
    if parsed.get("principal_id"):
        try:
            resolution = resolve_session_organization(
                connection=db.connection(),
                identity_id=str(parsed["principal_id"]),
            )
            membership_verified = bool(
                resolution.get("organization_id_resolved")
                and resolution.get("organization_id") == parsed.get("organization_id")
            )
        except Exception:
            db.rollback()
            membership_verified = False
    lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=parsed.get("principal_id"),
        organization_id=parsed.get("organization_id"),
        membership_verified=membership_verified,
    )
    return {"parsed": parsed, "lane": lane, "membership_verified": membership_verified}


def require_demo_lane_session(
    ctx: Annotated[dict[str, Any], Depends(_session_identity)],
) -> dict[str, Any]:
    if ctx["lane"]["workspace_lane"] != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "demo_lane_required_for_commercial_intent",
                "workspace_lane": ctx["lane"]["workspace_lane"],
            },
        )
    return ctx


class CommercialIntentBody(BaseModel):
    requested_org_display_name: str = Field(min_length=2, max_length=255)
    requested_org_hint: str | None = Field(default=None, max_length=512)
    product_code: str = Field(default="nativeforge_pro", max_length=64)


class OperatorFulfillBody(BaseModel):
    request_id: str = Field(min_length=8, max_length=64)
    operator_actor: str = Field(min_length=8, max_length=128)
    existing_organization_id: str | None = Field(default=None, max_length=64)


@router.get("/contract")
def future_payment_contract() -> dict[str, Any]:
    return commercial_entitlement_granted_contract()


@router.get("/status")
def provisioning_status(
    session: Annotated[dict[str, Any], Depends(_session_identity)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    identity_id = str(session["parsed"]["principal_id"])
    status_payload = load_status_for_identity(db.connection(), identity_id=identity_id)
    status_payload["workspace_lane"] = session["lane"]["workspace_lane"]
    status_payload["authenticated"] = True
    return status_payload


@router.post("/intent")
def submit_commercial_intent(
    body: CommercialIntentBody,
    _demo: Annotated[dict[str, Any], Depends(require_demo_lane_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    identity_id = str(_demo["parsed"]["principal_id"])
    result = create_commercial_intent(
        db.connection(),
        identity_id=identity_id,
        requested_org_display_name=body.requested_org_display_name,
        requested_org_hint=body.requested_org_hint,
        product_code=body.product_code,
        is_demo=False,
    )
    if result.get("blocked_reasons") and not result.get("request_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "commercial_intent_refused", **result},
        )
    db.commit()
    return result


@router.post("/operator/fulfill")
def operator_fulfill(
    body: OperatorFulfillBody,
    db: Annotated[Session, Depends(get_db_session)],
    x_nf_commercial_operator_approval: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    if not verify_operator_approval(approval_value=x_nf_commercial_operator_approval):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "operator_approval_required",
                "env_var": OPERATOR_APPROVAL_ENV,
            },
        )
    result = operator_fulfill_provisioning_request(
        db.connection(),
        request_id=body.request_id,
        operator_actor=body.operator_actor,
        operator_approval=x_nf_commercial_operator_approval,
        existing_organization_id=body.existing_organization_id,
    )
    if result.get("blocked_reasons") and not result.get("has_request"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result,
        )
    db.commit()
    return result
