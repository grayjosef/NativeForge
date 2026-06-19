"""Sprint 188: synthetic demo fixture corpus."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    SCHEMA_VERSION,
    build_demo_fixture_catalog,
    load_demo_classification_fixtures,
)


def test_load_demo_fixtures() -> None:
    fixtures = load_demo_classification_fixtures()
    assert len(fixtures) >= 8
    keys = {f["fixture_key"] for f in fixtures}
    assert "nrc_demo_native_specific" in keys
    assert "nrc_demo_irrelevant" in keys


def test_build_catalog() -> None:
    catalog = build_demo_fixture_catalog()
    assert catalog["schema_version"] == SCHEMA_VERSION
    assert catalog["synthetic_only"] is True
    assert catalog["fixture_count"] == len(load_demo_classification_fixtures())
