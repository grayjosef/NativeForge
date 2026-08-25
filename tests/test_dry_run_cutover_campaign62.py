"""Tests: Campaign Block 62 production dry-run cutover."""

from __future__ import annotations

from nativeforge.services.gate28_dry_run_cutover_assembler_service import (
    build_dry_run_cutover_demo_surface,
    dry_run_cutover_demo_surface_invariant_failures,
)
from nativeforge.services.gate28_dry_run_cutover_service import (
    dry_run_cutover_invariant_failures,
    run_production_dry_run_cutover,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_stops_at_auth0_and_skips_downstream() -> None:
    result = run_production_dry_run_cutover()
    assert result["first_hard_blocker"] == "auth0_oidc_preflight"
    assert result["skipped_after_blocker_count"] >= 1
    assert result["final_freeze_verified"] is True
    assert result["production_cutover_executed"] is False
    assert result["customer_data_mutated"] is False
    assert result["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert result["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"
    assert dry_run_cutover_invariant_failures(result) == []
    for s in result["steps"]:
        if s["status"].startswith("blocked_"):
            assert s["owner_action"]


def test_storage_and_pen_test_blockers() -> None:
    storage = run_production_dry_run_cutover(
        login_live=True, storage_approval_present=False
    )
    assert storage["first_hard_blocker"] == "storage_approval_token_validation"

    pentest = run_production_dry_run_cutover(
        login_live=True,
        storage_approval_present=True,
        pen_test_report_present=False,
    )
    assert pentest["first_hard_blocker"] == "pen_test_evidence_validation"
    assert pentest["skipped_after_blocker_count"] >= 1


def test_demo_and_bridge() -> None:
    surface = build_dry_run_cutover_demo_surface()
    assert dry_run_cutover_demo_surface_invariant_failures(surface) == []
    assert surface["fake_cutover_complete"] is False
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["dry_run_cutover"]["first_hard_blocker"] == "auth0_oidc_preflight"
    assert payload["dry_run_cutover"]["production_cutover_executed"] is False
