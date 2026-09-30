"""Public and operator opportunity value intelligence (HABEAS DATA V1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import get_db_session
from nativeforge.services.opportunity_value_intelligence_service import (
    compute_active_opportunity_value_aggregate,
    compute_operator_diagnostics,
    provenance_detail_for_opportunity,
    public_aggregate_view,
)

public_router = APIRouter(
    prefix="/api/public/opportunity-value",
    tags=["opportunity-value-public"],
)
operator_router = APIRouter(
    prefix="/backend/opportunity-value",
    tags=["opportunity-value-operator"],
)


@public_router.get("/active")
def public_active_opportunity_value(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Public-safe aggregate; no tenant or raw payload bytes."""
    full = compute_active_opportunity_value_aggregate(session.connection())
    return public_aggregate_view(full)


@operator_router.get("/diagnostics")
def operator_opportunity_value_diagnostics(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return compute_operator_diagnostics(session.connection())


@operator_router.get("/provenance/{canonical_id}")
def operator_provenance_trace(
    canonical_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    if not canonical_id or len(canonical_id) > 256:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_id")
    return provenance_detail_for_opportunity(
        session.connection(), canonical_id=canonical_id
    )
