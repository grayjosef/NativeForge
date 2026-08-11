"""Sprint 015: bridge preserves missing-data visibility."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_missing_data_visible() -> None:
    p = build_browser_demo_bridge_payload()
    assert p["missing_data_summary"]["hidden_missing_data"] is False
    assert any(r.get("missing_data") for r in p["rows"])
