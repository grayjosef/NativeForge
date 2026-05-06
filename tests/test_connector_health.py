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
