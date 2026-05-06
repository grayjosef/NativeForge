from nativeforge.services.discovery_coverage_gap_ids import (
    gap_id,
    recommendation_id,
    severity_rank,
)


def test_gap_id_stable() -> None:
    assert gap_id("a", "b") == gap_id("a", "b")
    assert gap_id("a", "b") != gap_id("a", "c")


def test_recommendation_id_derived_from_gap() -> None:
    g = gap_id("x")
    assert recommendation_id(g) == recommendation_id(g)


def test_severity_rank_order() -> None:
    assert severity_rank("critical") < severity_rank("low")
