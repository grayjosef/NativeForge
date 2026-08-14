"""Sprint 035: fail when demo page source missing for hard-stop screens."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    evaluate_browser_screens,
)


def test_missing_page_fails_screens() -> None:
    payload = build_browser_demo_bridge_payload()
    screens = evaluate_browser_screens(payload, page_source="", static_html="")
    assert screens["combined_review_queue_report"]["status"] == "FAIL"
