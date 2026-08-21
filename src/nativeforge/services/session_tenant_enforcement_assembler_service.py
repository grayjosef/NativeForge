"""Block 54 assembler: session + tenant enforcement surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.session_tenant_enforcement_service import (
    build_session_context,
    resolve_controlled_pilot_access,
    run_session_tenant_enforcement_suite,
    session_tenant_enforcement_invariant_failures,
)

SCHEMA_VERSION = "nf_session_tenant_assembler_v1"
DOC = "docs/operations/254_GATE24_SESSION_TENANT_ENFORCEMENT.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_session_tenant_demo_surface() -> dict[str, Any]:
    suite = run_session_tenant_enforcement_suite()
    session = build_session_context(status="dry_run")
    pilot = resolve_controlled_pilot_access()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 54,
            "title": "Session + tenant enforcement (live or dry-run)",
            "docs": [DOC],
            "session_context_contract": True,
            "session_status": session.get("session_status"),
            "session_statuses": suite.get("session_statuses"),
            "protected_object_families": suite.get("protected_object_families"),
            "operator_only_route_protection": True,
            "customer_route_constraints": True,
            "cross_org_denial_behavior": "deny_with_audit",
            "denial_audit_events": suite.get("denial_audit_events_present"),
            "controlled_pilot_access_resolver": True,
            "production_multi_tenant_claimed": False,
            "external_users_can_access_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_customer_access_ui": False,
            "suite_status": suite.get("suite_status"),
            "buyer_summary": [
                "Session/tenant enforcement model covers dry-run and live statuses",
                "Expired/invalid sessions block access; dry-run cannot claim live",
                "Cross-org denial on evidence, policy, authority, export with audits",
                "Controlled pilot access remains blocked; no production multi-tenant claim",
            ],
            "next_safe_actions": [
                pilot.get("reason"),
                "No fake login or external customer access UI",
            ],
            "human_review_required": True,
            "suite": suite,
            "session": session,
            "pilot_access": pilot,
        }
    )


def session_tenant_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_multi_tenant_claimed",
        "external_users_can_access_claimed",
        "login_live_claimed",
        "fake_customer_access_ui",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        session_tenant_enforcement_invariant_failures(surface.get("suite") or {})
    )
    return fails
