"""Block 69 assembler."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate31_pilot_onboarding_service import (
    pilot_onboarding_invariant_failures,
    resolve_invite_readiness,
)

SCHEMA_VERSION = "nf_gate31_onboarding_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pilot_onboarding_demo_surface() -> dict[str, Any]:
    result = resolve_invite_readiness()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 69,
            "title": "Pilot org onboarding + invite readiness",
            "pilot_org_onboarding_contract": True,
            "pilot_org_readiness_profile": True,
            "invite_readiness_resolver": True,
            "invite_send_gate": False,
            "invite_sent_claimed": False,
            "customer_role_model": "customer",
            "allowed_route_set": result.get("allowed_route_set"),
            "blocked_route_set": result.get("blocked_route_set"),
            "operator_approval_gate": False,
            "customer_access_claim": False,
            "pilot_org_status": result.get("pilot_org_status"),
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": "Do not send invites until login_live and remaining gates pass",
            "buyer_summary": [
                "Onboarding workflow exists; invite send remains blocked",
                "Customer roles cannot access operator surfaces; submit routes blocked",
            ],
            "next_safe_actions": ["Keep customer access claim freeze"],
            "result": result,
        }
    )


def pilot_onboarding_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in ("invite_send_gate", "invite_sent_claimed", "customer_access_claim"):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(pilot_onboarding_invariant_failures(surface.get("result") or {}))
    return fails
