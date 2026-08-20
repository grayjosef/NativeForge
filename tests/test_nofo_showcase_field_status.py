"""Tests: NOFO showcase field-status contract."""

from __future__ import annotations

from nativeforge.services.nofo_showcase_field_status_service import (
    ALLOWED_FIELD_STATUSES,
    STATUS_KNOWN,
    STATUS_MISSING,
    STATUS_NOT_SUPPORTED,
    assert_no_silent_fill,
    build_field_status_contract,
    field_status_invariant_failures,
    make_field,
)


def test_allowed_statuses_include_honesty_labels() -> None:
    for s in (
        "known",
        "extracted",
        "inferred",
        "missing",
        "needs_confirmation",
        "not_in_source",
        "not_supported",
    ):
        assert s in ALLOWED_FIELD_STATUSES


def test_missing_field_cannot_carry_invented_value() -> None:
    f = make_field(value="invented", status=STATUS_MISSING)
    assert "nonempty_value_for_missing" in field_status_invariant_failures(f)


def test_known_field_requires_value() -> None:
    f = make_field(value="", status=STATUS_KNOWN)
    assert "empty_value_for_known" in field_status_invariant_failures(f)


def test_protected_fields_cannot_be_silently_filled() -> None:
    fields = {
        "proposal_narrative": make_field(value="we are great", status=STATUS_KNOWN),
        "pdf_nofo_full_text": make_field(value="full text", status="extracted"),
        "deadline": make_field(
            value="2026-12-31", status=STATUS_KNOWN, evidence_note="pack"
        ),
    }
    fails = assert_no_silent_fill(fields)
    assert any("fabricated_or_overclaimed:proposal_narrative" in x for x in fails)
    assert any("fabricated_or_overclaimed:pdf_nofo_full_text" in x for x in fails)


def test_supported_unsupported_honesty() -> None:
    fields = {
        "proposal_narrative": make_field(value=None, status=STATUS_NOT_SUPPORTED),
        "pdf_nofo_full_text": make_field(value=None, status=STATUS_NOT_SUPPORTED),
    }
    assert assert_no_silent_fill(fields) == []


def test_contract_schema() -> None:
    c = build_field_status_contract()
    assert c["nofo_pdf_extraction"] == "NOT_SUPPORTED"
    assert c["proposal_drafting"] == "NOT_SUPPORTED"
    assert c["live_ingest_claimed_default"] is False
