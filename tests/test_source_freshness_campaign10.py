"""Tests: Campaign Block 10 source freshness pilot."""

from __future__ import annotations

from datetime import date

from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.source_freshness_pilot_checker_service import (
    build_source_freshness_demo_surface,
    run_fixture_backed_source_checks,
    source_freshness_demo_surface_invariant_failures,
)
from nativeforge.services.source_freshness_pilot_contract_service import (
    build_source_freshness_record,
    source_freshness_invariant_failures,
)


def test_live_continuous_production_claims_remain_false() -> None:
    rec = build_source_freshness_record(
        source_id="s1",
        source_name="Test",
        source_layer="federal",
        source_type="fixture",
        source_url_or_reference="fixtures/x",
        data_mode="fixture_backed_read_only_pilot",
        read_mode="fixture_backed_read_only_pilot",
        freshness_status="read_only_checked",
        last_checked_at="2026-08-20T18:00:00Z",
        source_health="healthy",
    )
    assert rec["live_ingest_claimed"] is False
    assert rec["continuous_monitoring_claimed"] is False
    assert rec["production_activation_claimed"] is False
    assert rec["external_live_check_not_run"] is True
    assert source_freshness_invariant_failures(rec) == []


def test_deadline_staleness_and_change_detection() -> None:
    pack = run_fixture_backed_source_checks(reference_today=date(2026, 8, 20))
    assert pack["live_ingest_claimed"] is False
    assert pack["external_live_check_not_run"] is True
    by_id = {r["source_id"]: r for r in pack["records"]}
    tedc = by_id["grants_gov_tedc_362648_fixture"]
    assert tedc["freshness_status"] in {"read_only_checked", "curated_current", "stale"}
    assert tedc["change_status"] == "unchanged"
    assert tedc["known_deadline_risk"] in {
        "due_within_30_days",
        "due_within_7_days",
        "not_imminent",
        "expired_or_past",
        "needs_confirmation",
    }
    portal = by_id["sc_portal_live_monitor"]
    assert portal["freshness_status"] in {"unsupported", "not_checked"}
    assert portal["live_ingest_claimed"] is False


def test_demo_surface_and_bridge() -> None:
    surface = build_source_freshness_demo_surface(reference_today=date(2026, 8, 20))
    assert source_freshness_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    sf = payload["source_freshness_pilot"]
    assert sf["live_ingest_claimed"] is False
    assert sf["continuous_monitoring_claimed"] is False
    assert sf["production_activation_claimed"] is False
    assert sf["external_live_check_not_run"] is True
