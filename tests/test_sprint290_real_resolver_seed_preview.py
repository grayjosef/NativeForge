"""Sprint 290: real-resolver seed preview report."""

from __future__ import annotations

from nativeforge.services.real_resolver_seed_preview_report_service import (
    build_real_resolver_seed_preview_report,
)


def _mock_fetch(url: str, method: str) -> dict[str, object]:
    return {"http_status": 200, "body_snippet": "public listing", "final_url": url}


def test_real_seed_preview_177() -> None:
    report = build_real_resolver_seed_preview_report(
        fetcher=_mock_fetch,
        min_interval_seconds=0,
    )
    assert report["seed_row_count"] == 177
    assert "baseline_comparison" in report
    assert report["real_resolver"] is True
