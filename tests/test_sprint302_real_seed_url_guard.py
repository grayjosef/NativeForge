"""Sprint 302: real seed URL guard — zero synthetic placeholders."""

from __future__ import annotations

from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)
from nativeforge.services.source_seed_real_url_guard_service import (
    assert_real_seed_urls,
    build_real_seed_url_guard_report,
    is_synthetic_seed_url,
)


def test_no_synthetic_placeholder_urls_in_seed() -> None:
    rows = load_source_seed_rows()
    assert len(rows) == 177
    assert_real_seed_urls(rows)
    report = build_real_seed_url_guard_report(rows)
    assert report["synthetic_url_count"] == 0
    assert report["real_seed_only"] is True


def test_is_synthetic_seed_url_detects_placeholders() -> None:
    assert is_synthetic_seed_url("https://example-state-1.gov/grants/tribal")
    assert is_synthetic_seed_url("https://foundation-example-2.org/grants")
    assert not is_synthetic_seed_url("https://www.bia.gov/topic/grants")
