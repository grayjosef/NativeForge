"""Sprint 012: write demo artifact to local path."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    write_demo_artifact,
)


def test_write_demo_artifact(tmp_path: Path) -> None:
    path = tmp_path / "demo.json"
    a = write_demo_artifact(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["content_digest"] == a["content_digest"]
    assert loaded["schema_version"] == a["schema_version"]
