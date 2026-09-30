"""Public and operator opportunity value intelligence (HABEAS DATA V1)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import get_db_session
from nativeforge.services.funding_landscape_composition_service import (
    compute_known_value_composition,
    public_composition_view,
)
from nativeforge.services.funding_landscape_velocity_service import (
    compute_partial_velocity,
)
from nativeforge.services.gate173_active_corpus_audit_service import (
    audit_active_corpus_native_signals,
    production_relevance_class_distribution,
)
from nativeforge.services.gate173_active_corpus_projection_service import (
    gate173_root_cause,
    run_bounded_active_relevance_projection,
)
from nativeforge.services.gate173_calibration_service import (
    build_gate173_calibration_report,
)
from nativeforge.services.grants_gov_active_funding_enrichment_service import (
    run_bounded_active_funding_enrichment,
    source_priority_policy,
)
from nativeforge.services.grants_gov_applicant_enrichment_diagnostics_service import (
    compute_applicant_enrichment_diagnostics,
)
from nativeforge.services.grants_gov_detail_enrichment_service import (
    run_bounded_active_applicant_enrichment,
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


@public_router.get("/composition")
def public_opportunity_value_composition(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Public-safe known-value concentration and semantic breakdown."""
    full = compute_known_value_composition(session.connection())
    return public_composition_view(full)


@operator_router.get("/diagnostics")
def operator_opportunity_value_diagnostics(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    conn = session.connection()
    base = compute_operator_diagnostics(conn)
    composition = compute_known_value_composition(conn)
    base["gate173"] = gate173_root_cause()
    base["gate173_calibration"] = build_gate173_calibration_report()
    base["gate173_production"] = {
        "relevance_class_distribution": production_relevance_class_distribution(
            conn
        ),
        "corpus_audit": audit_active_corpus_native_signals(conn),
    }
    base["composition"] = composition
    base["velocity"] = compute_partial_velocity(conn)
    base["applicant_enrichment"] = compute_applicant_enrichment_diagnostics(conn)
    return base


@operator_router.get("/gate173/calibration")
def operator_gate173_calibration() -> dict[str, Any]:
    return build_gate173_calibration_report()


@operator_router.get("/gate173/production-audit")
def operator_gate173_production_audit(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    conn = session.connection()
    return {
        "relevance_class_distribution": production_relevance_class_distribution(conn),
        "corpus_audit": audit_active_corpus_native_signals(conn),
    }


@operator_router.post("/gate173/active-projection")
def operator_gate173_active_projection(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 250,
    dry_run: bool = True,
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 500))
    stats = run_bounded_active_relevance_projection(
        session.connection(),
        limit=lim,
        dry_run=dry_run,
    )
    if not dry_run:
        session.commit()
    return stats


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
    stats = run_bounded_active_funding_enrichment(
        session.connection(),
        limit=lim,
        dry_run=dry_run,
    )
    if not dry_run:
        session.commit()
    return stats


@operator_router.get("/enrichment/applicant-diagnostics")
def operator_applicant_enrichment_diagnostics(
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return compute_applicant_enrichment_diagnostics(session.connection())


@operator_router.post("/enrichment/grants-gov-applicant")
def operator_run_grants_gov_applicant_enrichment(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int = 75,
    dry_run: bool = True,
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 250))
    stats = run_bounded_active_applicant_enrichment(
        session.connection(),
        limit=lim,
        dry_run=dry_run,
    )
    if not dry_run:
        session.commit()
    return stats


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
