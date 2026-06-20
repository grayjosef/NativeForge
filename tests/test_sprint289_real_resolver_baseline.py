"""Sprint 289: synthetic vs real baseline comparison."""

from __future__ import annotations

from nativeforge.services.real_resolver_baseline_comparison_service import (
    build_real_vs_synthetic_baseline_comparison,
)


def test_baseline_comparison_deltas() -> None:
    comparison = build_real_vs_synthetic_baseline_comparison(
        real_quality_summary={
            "posture_counts": {"public": 150, "members": 5, "login": 20},
            "dead_url_count": 2,
        },
    )
    assert comparison["synthetic_baseline"]["public"] == 156
    assert comparison["deltas"]["public"] == -6
    assert comparison["deltas"]["dead"] == 2
