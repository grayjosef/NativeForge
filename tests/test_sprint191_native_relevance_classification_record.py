"""Sprint 191: hardened classification record assembler."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_record_service import (
    SCHEMA_VERSION,
    build_native_relevance_classification_record,
)


def test_record_assembles_classification_and_explanation() -> None:
    raw = next(f for f in load_demo_classification_fixtures() if f["fixture_key"] == "nrc_demo_tribal_government")
    record = build_native_relevance_classification_record(raw)
    assert record["schema_version"] == SCHEMA_VERSION
    assert "classification" in record
    assert "explanation" in record
    assert record["classification"]["classification_label"] == record["explanation"]["classification_label"]


def test_record_flags_preview_only() -> None:
    raw = load_demo_classification_fixtures()[0]
    record = build_native_relevance_classification_record(raw)
    assert record["preview_only"] is True
    assert record["no_live_ingestion"] is True
