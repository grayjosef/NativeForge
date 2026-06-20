"""Sprint 274-275: staging seed preview report."""

from __future__ import annotations

from nativeforge.services.staging_seed_preview_report_service import (
    build_staging_seed_preview_report,
)


def test_seed_preview_report_177_candidates() -> None:
    report = build_staging_seed_preview_report()
    assert report["seed_row_count"] == 177
    assert report["candidate_count"] == 177
    assert report["all_candidates_inactive"] is True
    assert report["no_activation_performed"] is True


def test_dead_and_blocked_flagged() -> None:
    report = build_staging_seed_preview_report()
    summary = report["quality_summary"]
    assert summary["blocked_posture_count"] >= 1
    assert summary["posture_counts"]["public"] >= 1
    for row in report["candidates"]:
        assert row["is_active"] is False
        assert row["url_status"] in {"resolved", "dead"}
