"""Tests for Monday buyer demo polish smoke + bridge attachment."""

from __future__ import annotations

from nativeforge.services.monday_buyer_demo_smoke_runner_service import (
    run_monday_buyer_demo_smoke,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_bridge_includes_buyer_demo_polish() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["buyer_demo"]["opening_line"]
    assert payload["buyer_demo"]["closing_line"]
    assert payload.get("why_this_matters")
    assert payload.get("workload_reduction_statement")
    assert (
        "NOFO" in " ".join(payload["what_nativeforge_did"])
        or "synopsis" in " ".join(payload["what_nativeforge_did"]).lower()
    )


def test_monday_buyer_smoke_pass() -> None:
    result = run_monday_buyer_demo_smoke()
    assert result["status"] == "PASS"
    assert result["failed_surfaces"] == []
