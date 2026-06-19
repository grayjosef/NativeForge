"""Sprint 177: confidence rollup."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_confidence_rollup_service import (
    build_field_confidence_rollup,
)
from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    load_demo_fixture_corpus,
)
from nativeforge.services.funding_opportunity_intake_hardened_record_service import (
    build_hardened_opportunity_record,
)


def test_confidence_rollup_from_hardened_record() -> None:
    raw = load_demo_fixture_corpus()[0]
    hardened = build_hardened_opportunity_record(raw, fixture_key=raw["fixture_key"])
    rollup = build_field_confidence_rollup(hardened)
    assert rollup["field_count"] >= 1
