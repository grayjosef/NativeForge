"""Tests for NOFO showcase demo surface + offline smoke."""

from __future__ import annotations

from nativeforge.services.nofo_showcase_demo_surface_service import (
    build_nofo_showcase_demo_surface,
    nofo_showcase_surface_invariant_failures,
)
from nativeforge.services.nofo_showcase_smoke_runner_service import (
    run_nofo_showcase_offline_smoke,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_nofo_showcase_surface_has_sc_and_federal() -> None:
    surface = build_nofo_showcase_demo_surface(write_fixtures=True)
    assert nofo_showcase_surface_invariant_failures(surface) == []
    assert surface["sc_selected_count"] >= 1
    assert surface["federal_selected_count"] >= 1
    assert surface["nofo_pdf_extraction_claimed"] is False
    assert surface["proposal_drafting_claimed"] is False


def test_bridge_includes_nofo_showcase() -> None:
    payload = build_sc_customer_demo_bridge_payload()
    assert "nofo_showcase" in payload
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["nofo_showcase"]["selected_count"] >= 2


def test_offline_smoke_pass() -> None:
    result = run_nofo_showcase_offline_smoke()
    assert result["status"] == "PASS"
    assert result["failed_surfaces"] == []
    assert result["run_id"].startswith("nf_nofo_showcase_smoke_")
