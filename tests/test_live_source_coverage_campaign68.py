"""Tests: Campaign Block 68 live source coverage."""

from nativeforge.services.gate31_live_source_coverage_assembler_service import (
    build_live_source_coverage_demo_surface,
    live_source_coverage_demo_surface_invariant_failures,
)
from nativeforge.services.gate31_live_source_coverage_service import (
    clear_source_coverage_audit_for_tests,
    detect_duplicate_opportunities,
    resolve_live_source_coverage,
    resolve_source_row,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_packet_stale_error_and_top15() -> None:
    clear_source_coverage_audit_for_tests()
    packet = resolve_source_row(
        state="SC", source_name="sc", packet_only=True, evidence_ref="p"
    )
    assert packet["live_coverage_claimed"] is False
    stale = resolve_source_row(
        state="OK",
        source_name="ok",
        packet_only=False,
        reachable=True,
        stale=True,
        evidence_ref="e",
    )
    assert stale["freshness_status"] == "stale"
    assert stale["live_coverage_claimed"] is False
    err = resolve_source_row(
        state="AZ", source_name="az", packet_only=False, error=True, evidence_ref="e"
    )
    assert err["live_coverage_claimed"] is False
    missing = resolve_source_row(
        state="NM", source_name="nm", packet_only=False, evidence_ref=None
    )
    assert "evidence_ref" in missing["missing_gates"]
    one = resolve_live_source_coverage(
        rows=[
            resolve_source_row(
                state="SC",
                source_name="sc",
                packet_only=False,
                reachable=True,
                stale=False,
                evidence_ref="e",
            )
        ]
    )
    assert one["top15_live_claimed"] is False
    assert one["broad_coverage_claimed"] is False
    dups = detect_duplicate_opportunities(
        [{"opportunity_id": "a"}, {"opportunity_id": "a"}, {"opportunity_id": "b"}]
    )
    assert dups == ["a"]
    assert one["audit_refs"]


def test_demo_bridge() -> None:
    surface = build_live_source_coverage_demo_surface()
    assert live_source_coverage_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["live_source_coverage"]["broad_coverage_claimed"] is False
    assert payload["live_source_coverage"]["top15_live_claimed"] is False
