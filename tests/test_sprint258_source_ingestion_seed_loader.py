"""Sprint 258: source seed loader."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
    load_source_seed_rows,
)
from nativeforge.services.source_ingestion_seed_schema_service import (
    EXPECTED_ROW_COUNT,
)


def test_load_every_seed_row() -> None:
    rows = load_source_seed_rows()
    assert len(rows) == EXPECTED_ROW_COUNT


def test_all_candidates_inactive() -> None:
    bundle = build_source_seed_candidate_bundle()
    assert bundle["all_candidates_inactive"] is True
    # 61 -> 62 -> 63: Gate 163's Grants.gov API row and Gate 171's Federal
    # Register row are both tier 1. The corpus gained tier-1 sources, which is
    # a real property of the corpus and not a drift.
    assert bundle["tier_counts"][1] == 63
