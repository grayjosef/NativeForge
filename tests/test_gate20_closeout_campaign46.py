"""Tests: Campaign Block 46 storage Mode B, pen-test evidence, Gate 20 closeout."""

from __future__ import annotations

from nativeforge.services.gate20_closeout_assembler_service import (
    build_gate20_closeout_demo_surface,
    gate20_closeout_demo_surface_invariant_failures,
)
from nativeforge.services.gate20_final_pilot_closeout_service import (
    build_gate20_final_pilot_closeout,
    gate20_final_pilot_closeout_invariant_failures,
)
from nativeforge.services.pen_test_evidence_capture_service import (
    capture_pen_test_evidence,
    pen_test_evidence_capture_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.storage_mode_b_execution_service import (
    detect_and_run_storage_mode_b,
    storage_mode_b_execution_invariant_failures,
)


def test_storage_mode_b_blocked() -> None:
    result = detect_and_run_storage_mode_b()
    assert result["storage_mode_b_possible"] is False
    assert result["production_storage_claimed"] is False
    assert result["customer_data_persistence_claimed"] is False
    assert storage_mode_b_execution_invariant_failures(result) == []


def test_pen_test_no_report_keeps_pass_false() -> None:
    pen = capture_pen_test_evidence(report_received=False)
    assert pen["pen_test_passed"] is False
    assert pen["pass_claimed"] is False
    assert pen["evidence_captured"] is False
    assert pen_test_evidence_capture_invariant_failures(pen) == []


def test_final_closeout_not_go() -> None:
    closeout = build_gate20_final_pilot_closeout()
    assert closeout["mode"] == "mode_a"
    assert closeout["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert closeout["pen_test_passed"] is False
    assert gate20_final_pilot_closeout_invariant_failures(closeout) == []


def test_demo_and_bridge() -> None:
    surface = build_gate20_closeout_demo_surface()
    assert gate20_closeout_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["gate20_closeout"]["pen_test_passed_claim"] is False
    assert payload["gate20_closeout"]["production_storage_claimed"] is False
