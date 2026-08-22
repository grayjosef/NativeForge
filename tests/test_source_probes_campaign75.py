"""Tests: Campaign Block 75 source probes."""

from nativeforge.services.gate33_source_probe_assembler_service import (
    build_source_probe_demo_surface,
    source_probe_demo_surface_invariant_failures,
)
from nativeforge.services.gate33_source_probe_service import (
    clear_source_probe_audit_for_tests,
    run_safe_probe,
    run_source_probe_bundle,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_source_probe_gates() -> None:
    clear_source_probe_audit_for_tests()
    denied = run_safe_probe(
        source_id="pkt-OK",
        state="OK",
        source_name="ok",
        attempt=True,
    )
    assert denied["probe_allowed"] is False
    assert denied["probe_attempted"] is False
    failed = run_safe_probe(
        source_id="pkt-SC",
        state="SC",
        source_name="sc",
        attempt=True,
        fail=True,
        evidence_ref="e1",
    )
    assert failed["live_coverage_claimed"] is False
    stale = run_safe_probe(
        source_id="pkt-SC",
        state="SC",
        source_name="sc",
        attempt=True,
        reachable=True,
        stale=True,
        evidence_ref="e2",
    )
    assert stale["freshness_status"] == "stale"
    assert stale["live_coverage_claimed"] is False
    missing = run_safe_probe(
        source_id="pkt-SC",
        state="SC",
        source_name="sc",
        attempt=True,
        reachable=True,
        stale=False,
        evidence_ref=None,
    )
    assert "evidence_ref" in missing["missing_gates"]
    bundle = run_source_probe_bundle(
        opportunity_fixtures=[
            {"opportunity_id": "a"},
            {"opportunity_id": "a"},
            {"opportunity_id": "b"},
        ]
    )
    assert bundle["duplicate_ids"] == ["a"]
    assert bundle["canonical_ids"][0] == "a"
    assert bundle["top15_live_claimed"] is False
    assert bundle["broad_coverage_claimed"] is False
    assert bundle["live_source_claim"] is False


def test_demo_bridge() -> None:
    surface = build_source_probe_demo_surface()
    assert source_probe_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["source_probes"]["live_source_claim"] is False
