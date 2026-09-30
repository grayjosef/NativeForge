"""First controlled customer onboarding — hermetic rehearsal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nativeforge.services.controlled_customer_onboarding_rehearsal_service import (
    failure_rollback_matrix,
    human_review_handoffs,
    run_hermetic_rehearsal,
    write_evidence_json,
)
from nativeforge.services.customer_commercial_provisioning_service import (
    OPERATOR_APPROVAL_ENV,
    OPERATOR_APPROVAL_TOKEN,
)


@pytest.fixture
def operator_env(monkeypatch):
    monkeypatch.setenv(OPERATOR_APPROVAL_ENV, OPERATOR_APPROVAL_TOKEN)


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_dry_run_rehearsal_plan():
    out = run_hermetic_rehearsal(None, dry_run=True)
    assert out["passed"] is True
    assert out["rehearsal_mode"] == "dry_run"
    assert len(out["steps"]) >= 8


def test_hermetic_end_to_end_rehearsal(db, operator_env, monkeypatch):
    monkeypatch.setenv("NF_COMMERCIAL_OPERATOR_APPROVAL", OPERATOR_APPROVAL_TOKEN)
    out = run_hermetic_rehearsal(db.connection(), dry_run=False)
    db.commit()
    failed = [s for s in out["steps"] if s.get("status") != "pass"]
    assert not failed, failed
    assert out["organization_id"]
    assert out["provisioning_status"]["has_request"] is True
    step_names = {s["step"] for s in out["steps"]}
    assert "affiliation_authority_boundary" in step_names
    assert "ambiguous_org_fail_closed" in step_names
    assert "first_pursuit_decision_touch" in step_names


def test_human_handoffs_do_not_infer_authority():
    handoffs = human_review_handoffs()
    assert "UNKNOWN" in handoffs["authority_review"]["who_acts"]
    assert "commercial_entitlement" in handoffs["authority_review"]["software_must_not_infer"]


def test_failure_matrix_is_fail_closed_for_ambiguous_org():
    rows = {r["condition"]: r for r in failure_rollback_matrix()}
    assert rows["ambiguous_organization"]["fail_closed"] is True


def test_rehearsal_evidence_json_writes(tmp_path: Path):
    payload = run_hermetic_rehearsal(None, dry_run=True)
    target = tmp_path / "rehearsal_evidence.json"
    write_evidence_json(str(target), payload)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["schema_version"]
