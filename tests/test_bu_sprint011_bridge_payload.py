"""Sprint 011: browser demo bridge payload."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_bridge_payload() -> None:
    p = build_browser_demo_bridge_payload()
    assert p["demo_dev_only"] is True
    assert p["auth_required"] is False
    assert p["nm_summary"]["profile_count"] == 22
    assert p["wa_summary"]["profile_count"] == 29
    assert p["combined_summary"]["combined_profile_count"] == 51
    assert len(p["rows"]) == 51
