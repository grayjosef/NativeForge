"""Sprint 019: demo artifact offline / no-activation flags."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_offline_flags() -> None:
    a = build_demo_artifact()
    assert a["live_ingestion"] is False
    assert a["source_activation"] is False
    assert a["external_urls_used"] is False
    assert a["mode"] == "offline_synthetic"
