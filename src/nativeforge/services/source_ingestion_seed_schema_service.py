"""Sprint 257: NF_SOURCE_SEED_2026.csv schema contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

SCHEMA_VERSION: Final[str] = "nf_source_seed_2026_csv_v1"
SEED_FILENAME: Final[str] = "NF_SOURCE_SEED_2026.csv"
EXPECTED_ROW_COUNT: Final[int] = 177

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "seed_id",
    "canonical_source_id",
    "source_name",
    "source_url",
    "tier",
    "adapter_key",
    "source_type",
    "publisher_name",
    "state_code",
    "access_posture_hint",
    "program_family",
    "native_relevance_notes",
)

_SEED_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "source_ingestion"
    / SEED_FILENAME
)


def seed_csv_path() -> Path:
    return _SEED_PATH


def build_seed_schema_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "seed_filename": SEED_FILENAME,
        "expected_row_count": EXPECTED_ROW_COUNT,
        "required_columns": list(REQUIRED_COLUMNS),
        "tier_values": ["1", "2", "3"],
        "access_posture_hints": ["public", "members", "login"],
        "preview_only": False,
        "candidates_not_active_by_default": True,
    }


def assert_seed_schema_contract() -> None:
    contract = build_seed_schema_contract()
    json.dumps(contract)
    assert contract["expected_row_count"] == EXPECTED_ROW_COUNT
