"""Tests: Campaign Block 22 operator readiness."""

from __future__ import annotations

from nativeforge.services.operator_readiness_assembler_service import (
    build_operator_readiness_demo_surface,
    operator_readiness_demo_surface_invariant_failures,
)
from nativeforge.services.operator_readiness_contract_service import (
    build_go_no_go_matrix,
    build_operator_readiness_contract,
    operator_readiness_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_operator_contract_claims_false() -> None:
    c = build_operator_readiness_contract(current_head="deadbeef")
    assert c["production_ready_claimed"] is False
    assert c["pen_test_passed_claimed"] is False
    assert c["upload_persistence_claimed"] is False
    assert operator_readiness_invariant_failures(c) == []


def test_go_no_go_production_and_upload_not_go() -> None:
    matrix = build_go_no_go_matrix()
    by = {r["target"]: r for r in matrix}
    assert by["monday_demo"]["status"] == "GO"
    assert by["production_rollout"]["status"] == "NO_GO"
    assert by["upload_persistence_rollout"]["status"] == "NO_GO"
    assert by["collaboration_rollout"]["status"] == "NO_GO"


def test_demo_surface_and_bridge() -> None:
    surface = build_operator_readiness_demo_surface()
    assert operator_readiness_demo_surface_invariant_failures(surface) == []
    assert surface["monday_demo_status"] == "GO"
    assert surface["production_rollout_status"] == "NO_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["operator_readiness"]["production_ready_claimed"] is False
    assert payload["operator_readiness"]["pen_test_passed_claimed"] is False
