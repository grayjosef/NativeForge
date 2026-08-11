"""Sprint 015: demo artifact content digest is deterministic."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_demo_artifact_deterministic() -> None:
    a1 = build_demo_artifact()
    a2 = build_demo_artifact()
    assert a1["content_digest"] == a2["content_digest"]
