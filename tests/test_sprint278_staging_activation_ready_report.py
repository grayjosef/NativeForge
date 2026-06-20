"""Sprint 278: activation-ready report."""

from __future__ import annotations

from nativeforge.services.staging_activation_ready_report_service import (
    build_staging_activation_ready_report,
)


def test_activation_ready_report_never_activates() -> None:
    report = build_staging_activation_ready_report()
    assert report["stop_before_activation"] is True
    assert report["no_source_set_active"] is True
    assert report["all_sources_remain_inactive"] is True
    for row in report["green_to_activate_first"]:
        assert row["is_active"] is False
        assert row["activation_performed"] is False
    for row in report["blocked_sources"]:
        assert row["readiness_status"] == "BLOCKED"
