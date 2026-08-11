"""Sprint 032: evaluate expected smoke surfaces."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_smoke_runner_service import evaluate_surfaces
from nativeforge.services.nm_wa_smoke_validation_contract_service import EXPECTED_SURFACES


def test_evaluate_surfaces_all_pass() -> None:
    surfaces = evaluate_surfaces(build_demo_artifact())
    assert set(surfaces) == set(EXPECTED_SURFACES)
    assert all(s["status"] == "PASS" for s in surfaces.values())
