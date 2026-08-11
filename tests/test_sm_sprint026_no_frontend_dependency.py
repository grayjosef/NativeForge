"""Sprint 026: demo visibility layer does not require frontend."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services import nm_wa_operator_surfacing_demo_render_service as render


def test_demo_layer_is_cli_static_not_frontend() -> None:
    src = Path(render.__file__).read_text(encoding="utf-8")
    assert "frontend" not in src.lower()
    assert "auth" not in src.lower()
    assert render.SCHEMA_VERSION.endswith("_demo_render_v1")
