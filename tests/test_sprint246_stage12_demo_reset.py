"""Sprint 246: Stage 12 demo reset."""

from __future__ import annotations

import json

from nativeforge.services.stage12_demo_reset_service import build_stage12_demo_reset_descriptor


def test_reset_descriptor_no_db_writes() -> None:
    reset = build_stage12_demo_reset_descriptor()
    assert reset["database_writes"] == 0
    assert reset["source_activation_executed"] is False
    json.dumps(reset)
