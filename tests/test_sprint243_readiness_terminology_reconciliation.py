"""Sprint 243: readiness terminology reconciliation."""

from __future__ import annotations

from nativeforge.services.readiness_terminology_reconciliation_service import (
    build_readiness_terminology_reconciliation,
    build_terminology_reconciliation_contract,
    canonical_readiness_label,
)


def test_incomplete_maps_to_not_ready_missing_documents() -> None:
    assert canonical_readiness_label("incomplete") == "not_ready_missing_documents"


def test_needs_operator_review_maps_to_ready_with_review() -> None:
    assert canonical_readiness_label("needs_operator_review") == "ready_with_review"


def test_reconciliation_payload_shape() -> None:
    rec = build_readiness_terminology_reconciliation(application_readiness="incomplete")
    assert rec["readiness_label_canonical"] == "not_ready_missing_documents"
    assert rec["reconciliation_status"] == "complete"


def test_terminology_contract() -> None:
    contract = build_terminology_reconciliation_contract()
    assert contract["reconciliation_status"] == "complete"
    assert "incomplete" in contract["application_readiness_to_readiness_label"]
