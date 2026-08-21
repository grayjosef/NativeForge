"""External pilot auth spike (Campaign Block 26). Login remains not live."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_external_pilot_auth_spike_v1"

PILOT_AUTH_OPTIONS = (
    "demo_operator_view",
    "fixture_scoped_invite_allowlist",
    "oidc_external_not_enabled",
    "magic_link_external_not_enabled",
    "production_sso_not_supported",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_external_pilot_auth_spike() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 26,
            "title": "External pilot auth spike",
            "options": list(PILOT_AUTH_OPTIONS),
            "recommended_lowest_risk_path": "fixture_scoped_invite_allowlist",
            "customer_identity_assumptions": [
                "Named invitees only; no open registration",
                "Each invite maps to one organization_profile_id",
                "Operator review required before any invite activation",
            ],
            "org_scoping_requirements": [
                "Allowlists for packages/evidence/feedback contexts",
                "Cross-org reads blocked",
                "Collaboration remains OFF",
            ],
            "invite_allowlist_model": {
                "enabled": False,
                "status": "designed_not_live",
                "note": "Scaffold only — no invite tokens issued",
            },
            "route_restrictions": ["/?view=sc_customer_demo"],
            "data_isolation_requirements": [
                "organization_only data_scope",
                "local/dev storage does not imply customer persistence",
            ],
            "feedback_reporting_requirements": [
                "Fixture/operator feedback surfaces only",
                "No customer feedback persistence claim",
            ],
            "storage_requirement_dependency": (
                "local/dev validated_persistent exists; production storage still blocked"
            ),
            "pen_test_dependency": "External pen-test required before controlled customer pilot GO",
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "rbac_enforced_claimed": False,
            "production_multi_tenant_claimed": False,
            "customer_data_isolation_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "buyer_summary": [
                "External pilot auth path is scoped; login is not live",
                "Lowest-risk next step: invite allowlist (not enabled)",
                "Production auth / multi-tenant / RBAC claims remain false",
            ],
            "next_safe_actions": [
                "Keep fixture_scoped / demo_operator_view only",
                "Do not enable external invite tokens without pen-test packet review",
                "Do not claim controlled customer pilot GO",
            ],
        }
    )


def external_pilot_auth_spike_invariant_failures(spike: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "rbac_enforced_claimed",
        "production_multi_tenant_claimed",
        "customer_data_isolation_claimed",
    ):
        if spike.get(key) is True:
            fails.append(key)
    if spike.get("controlled_customer_pilot_status") == "GO":
        fails.append("customer_pilot_go")
    if (spike.get("invite_allowlist_model") or {}).get("enabled") is True:
        fails.append("invite_enabled")
    return fails
