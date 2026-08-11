"""Sprint 006: browser/demo UI manifest."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import EXPECTED_SCREENS
from nativeforge.services.nm_wa_browser_demo_manifest_service import (
    build_browser_demo_manifest,
)


def test_browser_manifest() -> None:
    m = build_browser_demo_manifest()
    assert m["demo_view_query"] == "view=nm_wa_operator_demo"
    assert m["expected_screens"] == list(EXPECTED_SCREENS)
    assert "activation_or_submission_controls" in m["hard_stops"]
