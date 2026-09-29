"""Gate 178: one dependency for substantive customer mutations."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.lib.demo_isolation import OrgType  # noqa: TC001 — literal alias
from nativeforge.services.commercial_entitlement_service import derive_entitlement
from nativeforge.services.commercial_license_model_service import (
    BENEFIT_WORKING,
    SUBSTANTIVE_WORKFLOWS,
)
from nativeforge.services.commercial_repository_service import (
    load_entitlement_material,
)

WorkflowName = str


def _check_workflow(
    *,
    connection: Any,
    organization_id: str,
    workflow: WorkflowName,
    org_type: OrgType,
) -> dict[str, Any]:
    if workflow not in SUBSTANTIVE_WORKFLOWS:
        raise ValueError(f"unknown workflow: {workflow}")

    material = load_entitlement_material(
        connection, organization_id=organization_id
    )
    entitlement = derive_entitlement(
        organization_id=organization_id,
        ledger=material.get("ledger") or {},
        extensions=material.get("extensions") or [],
        as_of=dt.date.today(),
    )
    benefit = str(entitlement.get("benefit_access") or "")
    working = benefit in BENEFIT_WORKING

    # Hermetic/demo tenants without a licence row: allow read paths elsewhere;
    # mutations still require an explicit licence unless demo plane (M0).
    if not working and org_type == "demo" and not material.get("ledger_events"):
        return {
            "allowed": True,
            "benefit_access": benefit,
            "demo_without_licence_row": True,
            "workflow": workflow,
        }

    return {
        "allowed": working,
        "benefit_access": benefit,
        "workflow": workflow,
        "entitlement": entitlement,
    }


def require_substantive_commercial_benefit(workflow: WorkflowName):
    """Factory: block substantive mutations when benefit is frozen/none."""

    def _demo(
        ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
        session: Annotated[Session, Depends(get_db_session)],
    ) -> dict[str, Any]:
        verdict = _check_workflow(
            connection=session.connection(),
            organization_id=str(ctx.org_id),
            workflow=workflow,
            org_type=ctx.org_type,
        )
        if not verdict.get("allowed"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "commercial_benefit_not_working",
                    "benefit_access": verdict.get("benefit_access"),
                    "workflow": workflow,
                },
            )
        return verdict

    def _real(
        ctx: Annotated[OrgContext, Depends(require_real_org_session)],
        session: Annotated[Session, Depends(get_db_session)],
    ) -> dict[str, Any]:
        verdict = _check_workflow(
            connection=session.connection(),
            organization_id=str(ctx.org_id),
            workflow=workflow,
            org_type=ctx.org_type,
        )
        if not verdict.get("allowed"):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "commercial_benefit_not_working",
                    "benefit_access": verdict.get("benefit_access"),
                    "workflow": workflow,
                },
            )
        return verdict

    return _demo, _real
