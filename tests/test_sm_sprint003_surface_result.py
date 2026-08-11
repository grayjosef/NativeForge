"""Sprint 003: smoke surface result model."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    empty_surface_result,
)


def test_empty_surface_result() -> None:
    row = empty_surface_result("nm_operator_report", status="NOT_RUN", detail="pending")
    assert row["status"] == "NOT_RUN"
    assert row["surface"] == "nm_operator_report"


def test_unknown_surface_rejected() -> None:
    with pytest.raises(ValueError):
        empty_surface_result("not_a_surface")
