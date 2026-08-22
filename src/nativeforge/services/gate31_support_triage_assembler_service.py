"""Block 70 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate31_support_triage_service import (
    resolve_support_triage,
    support_triage_invariant_failures,
)

SCHEMA_VERSION = "nf_gate31_support_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_support_triage_demo_surface() -> dict[str, Any]:
    result = resolve_support_triage()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 70,
            "title": "Customer support / feedback / incident triage",
            "feedback_intake_contract": True,
            "issue_triage_contract": True,
            "severity_model": result.get("severity_model"),
            "customer_impact_model": True,
            "owner_assignment": False,
            "support_readiness_resolver": True,
            "support_ready": False,
            "slack_operator_alert_model": True,
            "slack_sent_claimed": False,
            "incident_audit_events": True,
            "pilot_impact_resolver": True,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Assign incident owners; do not claim Slack sent unless sent",
            "buyer_summary": [
                "Triage workflow exists; Sev0/Sev1 block pilot expansion/GO until resolved",
                "Support readiness is false until owner assignment",
            ],
            "next_safe_actions": ["Staff support owners before any invite send"],
            "result": result,
        }
    )


def support_triage_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("slack_sent_claimed") is True:
        fails.append("slack_sent")
    if surface.get("support_ready") is True:
        fails.append("support_ready_mode_a")
    fails.extend(support_triage_invariant_failures(surface.get("result") or {}))
    return fails
