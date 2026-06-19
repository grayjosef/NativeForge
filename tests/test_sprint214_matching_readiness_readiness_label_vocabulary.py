"""Sprint 214: readiness labels."""

from __future__ import annotations

from nativeforge.services.matching_readiness_readiness_label_vocabulary_service import (
    READINESS_APPLICATION_READY,
    READINESS_LABELS,
    SCHEMA_VERSION,
    build_readiness_label_contract,
    is_valid_readiness_label,
)


def test_seven_readiness_labels() -> None:
    assert len(READINESS_LABELS) == 7
    assert READINESS_APPLICATION_READY in READINESS_LABELS


def test_build_contract() -> None:
    contract = build_readiness_label_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_label_rejected() -> None:
    assert is_valid_readiness_label(READINESS_APPLICATION_READY)
    assert not is_valid_readiness_label("bogus")
