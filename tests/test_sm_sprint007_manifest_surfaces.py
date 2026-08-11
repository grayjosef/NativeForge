"""Sprint 007: manifest surface name extraction."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_manifest_service import (
    build_smoke_manifest,
    manifest_surface_names,
)
from nativeforge.services.nm_wa_smoke_validation_contract_service import EXPECTED_SURFACES


def test_manifest_surface_names() -> None:
    names = manifest_surface_names(build_smoke_manifest())
    assert names == list(EXPECTED_SURFACES)
