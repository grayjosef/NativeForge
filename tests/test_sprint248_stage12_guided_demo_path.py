"""Sprint 248: Stage 12 guided demo path service."""

from __future__ import annotations

import json

from nativeforge.services.stage12_guided_demo_path_service import (
    build_stage12_guided_demo_path,
)


def test_guided_path_has_eight_steps() -> None:
    path = build_stage12_guided_demo_path()
    assert len(path["steps"]) == 8
    assert path["isolated"] is True
    assert path["no_source_activation_execution"] is True


def test_activation_preview_blocks_execution() -> None:
    path = build_stage12_guided_demo_path()
    activation = next(
        s for s in path["steps"] if s["step_id"] == "activation-readiness-preview"
    )
    payload = activation["payload"]
    assert payload["no_source_activation_execution"] is True
    assert all(not p["may_activate_now"] for p in payload["source_previews"])


def test_stale_opportunity_surfaced_in_intake() -> None:
    path = build_stage12_guided_demo_path()
    intake = next(s for s in path["steps"] if s["step_id"] == "opportunity-intake")
    assert intake["payload"]["stale_opportunities_shown"]
    json.dumps(path)
