"""Sprint 028: confidence/readiness labels in demo payload."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    build_demo_visibility_payload,
)


def test_confidence_distribution_present() -> None:
    p = build_demo_visibility_payload()
    assert isinstance(p["confidence_distribution"], dict)
    assert p["confidence_distribution"]
