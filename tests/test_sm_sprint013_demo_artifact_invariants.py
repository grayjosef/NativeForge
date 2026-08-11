"""Sprint 013: demo artifact hard invariant checks."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
    demo_artifact_invariant_failures,
)


def test_demo_artifact_invariants_pass() -> None:
    a = build_demo_artifact()
    assert demo_artifact_invariant_failures(a) == []


def test_hidden_missing_data_fails() -> None:
    a = build_demo_artifact()
    a["missing_data_summary"]["hidden_missing_data"] = True
    assert "missing_data_must_not_be_hidden" in demo_artifact_invariant_failures(a)
