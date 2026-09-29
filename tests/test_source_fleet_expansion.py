"""Source fleet expansion: inventory, gates, L1 shell purge order."""

from __future__ import annotations

import uuid

from nativeforge.db.session import SessionLocal
from nativeforge.services.grants_gov_spark_graph_reconciliation_service import (
    _purge_spark_reconcile_l1_shell_observations,
)
from nativeforge.services.source_collector_gate_evidence_service import (
    measure_source_collector_gates,
)
from nativeforge.services.source_fleet_expansion_inventory_service import (
    ADAPTER_SUPPORTED,
    AUTHORIZATION_REQUIRED,
    LIVE,
    build_source_fleet_inventory,
)
from nativeforge.services.south_carolina_grant_listing_research_service import (
    build_south_carolina_listing_research,
)
from tests import session_org_helper as soh

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
GRANTS = "nf-seed-2026-api-grants-gov-search2"
FR = "nf-seed-2026-api-federal-register-documents"


def test_fleet_inventory_classifies_grants_gov_live() -> None:
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    inv = build_source_fleet_inventory(
        session.connection(),
        organization_id=DEMO,
        live_source_ids=[GRANTS],
    )
    session.close()
    by_id = {e["source_id"]: e for e in inv["entries"]}
    assert by_id[GRANTS]["classification"] == LIVE
    assert by_id[FR]["classification"] in (
        AUTHORIZATION_REQUIRED,
        ADAPTER_SUPPORTED,
        "RESEARCH_REQUIRED",
    )
    assert inv["seed_count"] >= 179
    assert inv["priority_shortlist"]


def test_south_carolina_research_has_findings() -> None:
    out = build_south_carolina_listing_research()
    assert len(out["findings"]) >= 7
    assert all("classification" in row for row in out["findings"])


def test_l1_shell_purge_idempotent_noop() -> None:
    """Purge helper runs without error when no L1: shells are present."""
    session = SessionLocal()
    conn = session.connection()
    removed = _purge_spark_reconcile_l1_shell_observations(conn, source_id=GRANTS)
    session.rollback()
    assert removed >= 0
    session.close()


def test_measure_collector_gates_shape() -> None:
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    measured = measure_source_collector_gates(
        session, organization_id=DEMO, source_id=GRANTS
    )
    session.close()
    assert set(measured["gates"]) == {
        "registered",
        "enabled",
        "authorized",
        "warrant_valid",
        "terms_satisfied",
        "transport_healthy",
        "parser_healthy",
        "normalization_healthy",
        "persistence_healthy",
    }
