"""Sprint 012: bridge payload hard invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_browser_demo_bridge_payload,
)


def test_bridge_invariants_pass() -> None:
    assert bridge_payload_invariant_failures(build_browser_demo_bridge_payload()) == []


def test_hidden_missing_fails() -> None:
    p = build_browser_demo_bridge_payload()
    p["missing_data_summary"]["hidden_missing_data"] = True
    assert "missing_data_must_not_be_hidden" in bridge_payload_invariant_failures(p)
