"""Sprint 258: source seed loader."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
    load_source_seed_rows,
)


def test_load_177_rows() -> None:
    rows = load_source_seed_rows()
    assert len(rows) == 177


def test_all_candidates_inactive() -> None:
    bundle = build_source_seed_candidate_bundle()
    assert bundle["all_candidates_inactive"] is True
    assert bundle["tier_counts"][1] == 61
