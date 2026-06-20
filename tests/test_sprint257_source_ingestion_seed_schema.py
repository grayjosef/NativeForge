"""Sprint 257: source seed CSV schema."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
    build_seed_schema_contract,
    seed_csv_path,
)


def test_seed_csv_exists() -> None:
    assert seed_csv_path().is_file()


def test_schema_contract() -> None:
    c = build_seed_schema_contract()
    assert c["expected_row_count"] == EXPECTED_ROW_COUNT
