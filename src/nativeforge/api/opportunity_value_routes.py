"""Public and operator opportunity value intelligence (HABEAS DATA V1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import get_db_session
from nativeforge.services.grants_gov_active_funding_enrichment_service import (
    run_bounded_active_funding_enrichment,
    source_priority_policy,
)
from nativeforge.services.opportunity_value_funnel_service import (
    compute_corpus_funnel_aggregate,
    public_corpus_funnel_view,
)
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


@public_router.get("/funnel")
def public_opportunity_value_funnel_corpus(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Public-safe corpus funnel slices (active + native-relevant)."""
    full = compute_corpus_funnel_aggregate(session.connection())
    return public_corpus_funnel_view(full)


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


@operator_router.get("/enrichment/policy")
def operator_enrichment_policy() -> dict[str, Any]:
    return source_priority_policy()


@operator_router.post("/enrichment/grants-gov-active")
def operator_run_grants_gov_active_enrichment(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 50,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Bounded detail enrichment; default dry_run avoids accidental live fetch from UI."""
    lim = max(1, min(int(limit), 200))
    return run_bounded_active_funding_enrichment(
        session.connection(),
        limit=lim,
        dry_run=dry_run,
    )


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
