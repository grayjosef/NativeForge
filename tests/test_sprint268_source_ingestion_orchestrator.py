"""Sprint 268: orchestrator."""

from __future__ import annotations

from nativeforge.services.source_ingestion_orchestrator_service import (
    run_source_seed_ingestion_preview,
)


def test_ingestion_preview() -> None:
    preview = run_source_seed_ingestion_preview()
    assert preview["all_candidates_inactive"] is True
    assert preview["seed_bundle"]["seed_row_count"] == 177
