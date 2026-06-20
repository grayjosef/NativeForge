"""Sprint 260: plan gate."""

from __future__ import annotations

import pytest

from nativeforge.services.source_ingestion_plan_gate_service import (
    build_plan_gate_contract,
    is_live_source_ingestion_plan_approved,
    require_plan_gate,
)


def test_plan_gate_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", raising=False)
    assert is_live_source_ingestion_plan_approved() is False


def test_plan_gate_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    assert is_live_source_ingestion_plan_approved() is True
    require_plan_gate()


def test_plan_gate_contract() -> None:
    c = build_plan_gate_contract()
    assert c["human_activation_required_per_source"] is True
