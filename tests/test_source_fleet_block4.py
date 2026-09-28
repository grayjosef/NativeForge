"""Source fleet backlog, live-gate derivation, and South Carolina candidates."""

from __future__ import annotations

from nativeforge.services.backend_health_readiness_service import (
    build_backend_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.source_fleet_live_readiness_service import (
    LIVE_GATES,
    derive_collectors_live,
)
from nativeforge.services.source_seed_backlog_service import classify_source_seed
from nativeforge.services.south_carolina_coverage_service import south_carolina_coverage


def _live_source(source_id: str, **overrides: bool) -> dict:
    gates = dict.fromkeys(LIVE_GATES, True)
    gates.update(overrides)
    return {"source_id": source_id, "gates": gates}


def test_an_unmeasured_fleet_is_not_live() -> None:
    derived = derive_collectors_live()
    assert derived["measured"] is False
    assert derived["collectors_live"] == 0
    assert derived["fleet_live_sources"] == []
    assert derived["live_fetch_performed"] is False


def test_one_missing_gate_is_not_a_live_collector() -> None:
    derived = derive_collectors_live(
        sources=[_live_source("grants_gov_search2", warrant_valid=False)]
    )
    assert derived["collectors_live"] == 0
    assert derived["measured"] is True


def test_every_gate_is_required_before_a_source_counts_as_live() -> None:
    derived = derive_collectors_live(sources=[_live_source("grants_gov_search2")])
    assert derived["collectors_live"] == 1
    assert derived["fleet_live_sources"] == ["grants_gov_search2"]


def test_readiness_reports_the_derived_zero_and_rejects_a_bare_claim() -> None:
    readiness = build_backend_readiness(database_ready=True)
    assert readiness["collectors_live"] == 0
    assert readiness["fleet_live_sources"] == []
    assert "readiness_claimed_live_collectors" not in readiness_invariant_failures(
        readiness
    )
    bare = dict(readiness, collectors_live=2)
    assert "readiness_claimed_live_collectors" in readiness_invariant_failures(bare)
    evidenced = dict(
        readiness,
        collectors_live=1,
        fleet_live_sources=["grants_gov_search2"],
    )
    assert "readiness_claimed_live_collectors" not in readiness_invariant_failures(
        evidenced
    )


def test_seed_classes_partition_the_loaded_corpus() -> None:
    backlog = classify_source_seed()
    counts = (
        backlog["verified"]
        + backlog["duplicate"]
        + backlog["stale"]
        + backlog["invalid"]
        + backlog["needs_research"]
        + backlog["adapter_supported"]
        + backlog["new_adapter_required"]
        + backlog["authorization_required"]
    )
    assert counts == backlog["candidate_count"]
    assert backlog["candidate_count"] >= 179
    assert backlog["verified"] == 0
    assert backlog["stale"] == 0
    assert backlog["invalid"] > 0
    assert backlog["adapter_supported"] > 0
    assert backlog["authorization_required"] > 0
    assert "structured_federal_api" in backlog["by_family"]
    assert "html_listing" in backlog["by_family"]


def test_south_carolina_candidates_are_not_enabled_or_ingested() -> None:
    coverage = south_carolina_coverage()
    assert coverage["enabled"] == 0
    assert coverage["active"] == 0
    assert coverage["ingested_opportunities"] == 0
    assert coverage["federal_artery_is_state_limited"] is False
    assert coverage["seed_backlog_class"] == "NEEDS_RESEARCH"
    assert coverage["candidates"]
    assert all(row["enabled"] is False for row in coverage["candidates"])
    assert all(
        row["grant_listing_confirmed"] is False for row in coverage["candidates"]
    )
    assert all(row["warrant_valid"] is False for row in coverage["candidates"])
