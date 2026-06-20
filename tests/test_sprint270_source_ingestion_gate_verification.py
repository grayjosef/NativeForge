"""Sprint 270: gate verification."""

from __future__ import annotations

from nativeforge.services.source_ingestion_gate_verification_service import (
    verify_source_ingestion_gates,
)


def test_gates_pass() -> None:
    result = verify_source_ingestion_gates()
    assert result["verification_passed"] is True
