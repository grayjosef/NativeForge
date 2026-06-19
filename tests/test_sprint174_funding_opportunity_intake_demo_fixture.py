"""Sprint 174: synthetic demo fixtures."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    build_demo_fixture_manifest,
    load_demo_fixture_corpus,
)


def test_demo_fixture_corpus_loads() -> None:
    rows = load_demo_fixture_corpus()
    assert len(rows) >= 2
    assert all("fixture_key" in r for r in rows)


def test_demo_fixture_manifest_synthetic_only() -> None:
    m = build_demo_fixture_manifest()
    assert m["synthetic_only"] is True
    assert m["no_live_ingestion"] is True
