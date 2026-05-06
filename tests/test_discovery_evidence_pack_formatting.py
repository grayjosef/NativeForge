"""Tests for extracted evidence pack formatting helpers."""

from nativeforge.domain.enums import (
    EvidencePackWarningSeverity,
    EvidencePackWarningType,
)
from nativeforge.services.discovery_evidence_pack_formatting import (
    digest_json_blob,
    evidence_dt,
    evidence_section,
    evidence_warn,
)


def test_digest_json_blob_stable() -> None:
    d = digest_json_blob({"b": 2, "a": 1})
    assert d == digest_json_blob({"a": 1, "b": 2})
    assert len(d or "") == 64


def test_evidence_warn_shape() -> None:
    w = evidence_warn(
        EvidencePackWarningType.duplicate_risk,
        EvidencePackWarningSeverity.medium,
        "t",
        "r",
        "a",
    )
    assert w["warning_type"] == EvidencePackWarningType.duplicate_risk.value


def test_evidence_section_shape() -> None:
    from nativeforge.domain.enums import EvidencePackSectionType

    s = evidence_section(
        EvidencePackSectionType.subject_summary,
        "x",
        "y",
        [],
        [],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    assert s["section_type"] == EvidencePackSectionType.subject_summary.value


def test_evidence_dt_datetime() -> None:
    from datetime import UTC, datetime

    t = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert evidence_dt(t) == t.isoformat()
