"""Sprint 259: URL quality and access posture."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)
from nativeforge.services.source_ingestion_url_quality_service import (
    verify_seed_candidate_batch,
    verify_source_url_quality,
)


def test_members_posture_blocked() -> None:
    rows = load_source_seed_rows()
    row = next(r for r in rows if r["access_posture_hint"] == "members")
    cand = seed_row_to_discovery_candidate(row)
    result = verify_source_url_quality(cand)
    assert result["access_posture_blocked"] is True
    assert result["scrape_allowed_after_activation"] is False


def test_public_posture_resolves() -> None:
    rows = load_source_seed_rows()
    row = next(r for r in rows if r["access_posture_hint"] == "public")
    cand = seed_row_to_discovery_candidate(row)
    result = verify_source_url_quality(cand)
    assert result["url_resolved"] is True


def test_batch_quality() -> None:
    cands = [seed_row_to_discovery_candidate(r) for r in load_source_seed_rows()]
    batch = verify_seed_candidate_batch(cands)
    assert batch["result_count"] == 177
    assert batch["blocked_posture_count"] >= 1
