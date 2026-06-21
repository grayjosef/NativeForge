"""Sprint 315: seed catalog URL corrections."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)
from nativeforge.services.source_seed_url_correction_service import (
    SEED_URL_CORRECTIONS,
    build_seed_url_correction_report,
)


def test_correction_count_matches_catalog_fixes() -> None:
    rows = load_source_seed_rows()
    report = build_seed_url_correction_report(rows)
    assert report["correction_count"] == len(SEED_URL_CORRECTIONS)
    assert report["prior_dead_catalog_count"] == 48


def test_fed050_points_to_imls_not_bia() -> None:
    rows = {r["seed_id"]: r for r in load_source_seed_rows()}
    url = rows["nf-seed-2026-fed-050"]["source_url"]
    assert "imls.gov" in url
    assert "bia.gov" not in url


def test_fed022_acl_path_corrected() -> None:
    rows = {r["seed_id"]: r for r in load_source_seed_rows()}
    url = rows["nf-seed-2026-fed-022"]["source_url"]
    assert "title-vi" not in url
    assert "nutrition-services" in url
