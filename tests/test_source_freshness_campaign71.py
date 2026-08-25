"""Tests: Campaign Block 71 source freshness."""

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
)
from nativeforge.services.gate32_source_freshness_assembler_service import (
    build_source_freshness_demo_surface,
    source_freshness_demo_surface_invariant_failures,
)
from nativeforge.services.gate32_source_freshness_service import (
    resolve_source_health,
    run_source_freshness_bundle,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_freshness_gates() -> None:
    # One request: these calls share an audit trail explicitly rather than
    # through module-level state.
    collector = AuditEventCollector()
    packet = resolve_source_health(
        collector=collector,
        source_id="1", state="SC", source_name="sc", packet_only=True, evidence_ref="p"
    )
    assert packet["live_coverage_claimed"] is False
    err = resolve_source_health(
        collector=collector,
        source_id="2",
        state="OK",
        source_name="ok",
        packet_only=False,
        probe_attempted=True,
        error="timeout",
        evidence_ref="e",
    )
    assert err["live_coverage_claimed"] is False
    stale = resolve_source_health(
        collector=collector,
        source_id="3",
        state="AZ",
        source_name="az",
        packet_only=False,
        probe_attempted=True,
        reachable=True,
        stale=True,
        evidence_ref="e",
    )
    assert stale["freshness_status"] == "stale"
    assert stale["live_coverage_claimed"] is False
    missing = resolve_source_health(
        collector=collector,
        source_id="4",
        state="NM",
        source_name="nm",
        packet_only=False,
        probe_attempted=True,
        reachable=True,
        stale=False,
        evidence_ref=None,
    )
    assert "evidence_ref" in missing["missing_gates"]
    one = run_source_freshness_bundle(
        collector=collector,
        rows=[
            resolve_source_health(
                collector=collector,
                source_id="sc",
                state="SC",
                source_name="sc",
                packet_only=False,
                probe_attempted=True,
                reachable=True,
                stale=False,
                evidence_ref="e",
            )
        ],
        opportunity_fixtures=[
            {"opportunity_id": "a"},
            {"opportunity_id": "a"},
            {"opportunity_id": "b"},
        ],
    )
    assert one["duplicate_ids"] == ["a"]
    assert one["top15_live_claimed"] is False
    assert one["broad_coverage_claimed"] is False
    assert one["audit_refs"]


def test_demo_bridge() -> None:
    surface = build_source_freshness_demo_surface()
    assert source_freshness_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["source_freshness"]["live_source_claim"] is False
