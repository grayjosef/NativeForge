"""Block 57 assembler: security attestation / pen-test surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate26_security_attestation_service import (
    build_security_attestation_contract,
    resolve_pen_test_pass,
    security_attestation_invariant_failures,
)

SCHEMA_VERSION = "nf_gate26_security_attestation_assembler_v1"
DOC = "docs/operations/266_GATE26_SECURITY_ATTESTATION_PEN_TEST.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_security_attestation_demo_surface() -> dict[str, Any]:
    attestation = build_security_attestation_contract()
    pass_res = resolve_pen_test_pass(attestation)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 57,
            "title": "Security attestation / pen-test evidence gate",
            "docs": [DOC],
            "security_attestation_contract": True,
            "pen_test_evidence_contract": True,
            "evidence_report_present": False,
            "test_scope": attestation.get("test_scope"),
            "evidence_status": attestation.get("evidence_status"),
            "finding_severities": attestation.get("finding_severities"),
            "critical_high_open": attestation.get("critical_high_open"),
            "remediation_status": attestation.get("remediation_status"),
            "retest_status": attestation.get("retest_status"),
            "security_exceptions": attestation.get("security_exceptions"),
            "pen_test_passed": False,
            "pass_claimed": False,
            "pilot_impact": attestation.get("pilot_impact"),
            "production_impact": attestation.get("production_impact"),
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_secure_badge": False,
            "fake_pen_test_passed_badge": False,
            "sca_gate16_preserved": True,
            "prompt_alone_is_not_evidence": True,
            "next_owner_action": attestation.get("next_owner_action"),
            "buyer_summary": [
                "Security attestation and pen-test evidence gate exist",
                "No report means pen_test_passed remains false",
                "Open critical/high, unclear scope, or pending remediations block pass",
                "Accepted risk cannot silently unlock a security pass",
            ],
            "next_safe_actions": [
                attestation.get("next_owner_action"),
                "No fake secure or pen-test-passed badges",
            ],
            "human_review_required": True,
            "attestation": attestation,
            "pass_resolver": pass_res,
        }
    )


def security_attestation_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "pen_test_passed",
        "pass_claimed",
        "fake_secure_badge",
        "fake_pen_test_passed_badge",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        security_attestation_invariant_failures(surface.get("attestation") or {})
    )
    return fails
