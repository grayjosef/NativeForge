"""Sprint 019: bridge forbids activation controls and auth requirement."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_no_activation_auth() -> None:
    p = build_browser_demo_bridge_payload()
    assert p["auth_required"] is False
    assert p["ui_flags"]["show_activation_controls"] is False
    assert p["ui_flags"]["show_submit_controls"] is False
    assert p["source_activation"] is False
