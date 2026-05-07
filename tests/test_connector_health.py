from nativeforge.services.source_connectors.connector_health import (
    intake_bridge_outcome_health,
)


def test_health_failed_on_norm_errors() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=1,
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
        )
        == "failed"
    )


def test_health_failed_on_intake_errors() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=2,
        )
        == "failed"
    )


def test_health_empty() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
        )
        == "empty"
    )


def test_health_stale_overlay_on_otherwise_healthy() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=2,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
            source_overdue_for_check=True,
        )
        == "stale"
    )


def test_health_overdue_does_not_override_degraded() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=0,
            rejected_count=1,
            duplicate_count=0,
            error_count=0,
            source_overdue_for_check=True,
        )
        == "degraded"
    )


def test_health_duplicate_dominance_degraded() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=1,
            rejected_count=0,
            duplicate_count=4,
            error_count=0,
        )
        == "degraded"
    )


def test_health_review_required_heavy_degraded() -> None:
    assert (
        intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=2,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
            review_required_count=8,
        )
        == "degraded"
    )
