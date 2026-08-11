"""Sprint 016: bridge preserves human-review and next-check."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_review_and_next_check() -> None:
    p = build_browser_demo_bridge_payload()
    assert all(r.get("human_review_required") for r in p["rows"])
    assert all(r.get("operator_next_check") for r in p["rows"])
    assert p["operator_next_check_summary"]["rows_with_next_checks"] == 51
