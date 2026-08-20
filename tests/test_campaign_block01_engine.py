"""Tests for Campaign Block 01 product surface + smoke."""

from __future__ import annotations

from nativeforge.services.campaign_block01_smoke_runner_service import (
    run_campaign_block01_smoke,
)
from nativeforge.services.opportunity_engine_product_surface_service import (
    build_opportunity_engine_product_surface,
    opportunity_engine_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_product_surface_invariants() -> None:
    surface = build_opportunity_engine_product_surface(write_config=True)
    assert opportunity_engine_surface_invariant_failures(surface) == []
    assert surface["campaign_block"] >= 1


def test_bridge_includes_opportunity_engine() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["opportunity_engine"]["combined_workflow"]["counts"]["sc_state"] >= 1
    assert payload["opportunity_engine"]["combined_workflow"]["counts"]["federal"] >= 1


def test_campaign_block01_smoke_pass() -> None:
    result = run_campaign_block01_smoke()
    assert result["status"] == "PASS"
    assert result["failed_surfaces"] == []
