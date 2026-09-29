"""Gate 178: demo M0 bypass is allowlist-only."""

from __future__ import annotations

import uuid

from nativeforge.api.commercial_entitlement_dependency import _check_workflow

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
RANDOM_DEMO = uuid.UUID("11111111-2222-3333-4444-555555555555")


def _empty_ledger(*_a, **_k):
    return {"ledger": {}, "ledger_events": [], "extensions": []}


def test_allowlisted_demo_org_without_ledger_may_mutate(monkeypatch):
    monkeypatch.setenv("NF_DEMO_ORG_IDS", str(DEMO_ORG))
    monkeypatch.setattr(
        "nativeforge.api.commercial_entitlement_dependency.load_entitlement_material",
        _empty_ledger,
    )
    verdict = _check_workflow(
        connection=object(),
        organization_id=str(DEMO_ORG),
        workflow="OPEN_PURSUIT",
        org_type="demo",
    )
    assert verdict.get("allowed") is True
    assert verdict.get("demo_m0_allowlisted_bypass") is True


def test_non_allowlisted_demo_org_denied_without_ledger(monkeypatch):
    monkeypatch.setenv("NF_DEMO_ORG_IDS", str(DEMO_ORG))
    monkeypatch.setattr(
        "nativeforge.api.commercial_entitlement_dependency.load_entitlement_material",
        _empty_ledger,
    )
    verdict = _check_workflow(
        connection=object(),
        organization_id=str(RANDOM_DEMO),
        workflow="OPEN_PURSUIT",
        org_type="demo",
    )
    assert verdict.get("allowed") is False


def test_real_org_never_gets_demo_bypass(monkeypatch):
    monkeypatch.setenv("NF_DEMO_ORG_IDS", str(DEMO_ORG))
    monkeypatch.setattr(
        "nativeforge.api.commercial_entitlement_dependency.load_entitlement_material",
        _empty_ledger,
    )
    verdict = _check_workflow(
        connection=object(),
        organization_id=str(DEMO_ORG),
        workflow="OPEN_PURSUIT",
        org_type="real",
    )
    assert verdict.get("allowed") is False
