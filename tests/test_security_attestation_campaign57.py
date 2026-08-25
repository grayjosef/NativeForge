"""Tests: Campaign Block 57 security attestation / pen-test gate."""

from __future__ import annotations

from nativeforge.services.gate26_security_attestation_assembler_service import (
    build_security_attestation_demo_surface,
    security_attestation_demo_surface_invariant_failures,
)
from nativeforge.services.gate26_security_attestation_service import (
    build_security_attestation_contract,
    security_attestation_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_no_report_and_unknown_scope_block_pass() -> None:
    none = build_security_attestation_contract()
    assert none["evidence_status"] == "no_report"
    assert none["pen_test_passed"] is False
    assert none["prompt_alone_is_not_evidence"] is True
    assert security_attestation_invariant_failures(none) == []

    unclear = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="artifacts/pen_test/report.pdf",
        scope="unknown",
    )
    assert unclear["evidence_status"] == "scope_unclear"
    assert unclear["pen_test_passed"] is False


def test_open_critical_high_and_accepted_risk() -> None:
    crit = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api+auth",
        findings=[{"severity": "critical", "status": "open"}],
    )
    assert crit["pen_test_passed"] is False
    assert crit["open_critical"] == 1

    high = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api+auth",
        findings=[{"severity": "high", "status": "open"}],
    )
    assert high["pen_test_passed"] is False

    medium = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api+auth",
        findings=[{"severity": "medium", "status": "open"}],
    )
    assert medium["medium_needs_owner_decision"] is True
    assert medium["pen_test_passed"] is False

    accepted = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api+auth",
        findings=[
            {"severity": "high", "status": "accepted_risk_pending_owner_approval"}
        ],
        owner_accepted_risk=True,
    )
    assert accepted["pen_test_passed"] is False
    assert accepted["accepted_risk_cannot_silently_pass"] is True


def test_remediation_and_retest_block() -> None:
    rem = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api",
        findings=[{"severity": "high", "status": "remediation_in_progress"}],
    )
    assert rem["remediation_status"] == "required"
    assert rem["pen_test_passed"] is False

    retest = build_security_attestation_contract(
        report_present=True,
        report_artifact_ref="ref",
        scope="api",
        findings=[{"severity": "high", "status": "remediated_pending_retest"}],
    )
    assert retest["retest_status"] == "required"
    assert retest["pen_test_passed"] is False


def test_demo_and_bridge() -> None:
    surface = build_security_attestation_demo_surface()
    assert security_attestation_demo_surface_invariant_failures(surface) == []
    assert surface["production_rollout_status"] == "NO_GO"
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["security_attestation"]["pen_test_passed"] is False
    assert payload["security_attestation"]["fake_secure_badge"] is False
