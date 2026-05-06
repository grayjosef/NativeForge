import uuid

from nativeforge.domain.enums import CoverageRecommendationAction
from nativeforge.services.discovery_operator_workbench_pure import (
    decision_id,
    map_coverage_action_to_operator,
)


def test_decision_id_stable() -> None:
    oid = uuid.uuid4()
    assert decision_id(oid, "a") == decision_id(oid, "a")


def test_map_coverage_action() -> None:
    raw = CoverageRecommendationAction.verify_source.value
    v = map_coverage_action_to_operator(raw)
    assert v
