"""Sprint 268: orchestrator."""

from __future__ import annotations

from nativeforge.services.source_ingestion_orchestrator_service import (
    run_source_seed_ingestion_preview,
)
from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
)


def test_ingestion_preview() -> None:
    preview = run_source_seed_ingestion_preview()
    assert preview["all_candidates_inactive"] is True
    assert preview["seed_bundle"]["seed_row_count"] == EXPECTED_ROW_COUNT
