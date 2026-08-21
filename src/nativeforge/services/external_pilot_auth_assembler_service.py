"""Block 37 assembler: external pilot auth path + invite boundary."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth_provider_decision_matrix_service import (
    auth_provider_decision_matrix_invariant_failures,
    build_auth_provider_decision_matrix,
)
from nativeforge.services.external_auth_context_adapter_service import (
    adapt_external_auth_context,
    external_auth_adapter_invariant_failures,
)
from nativeforge.services.pilot_invite_allowlist_contract_service import (
    build_pilot_invite_contract,
    pilot_invite_contract_invariant_failures,
)

SCHEMA_VERSION = "nf_external_pilot_auth_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_external_pilot_auth_demo_surface() -> dict[str, Any]:
    matrix = build_auth_provider_decision_matrix()
    invite = build_pilot_invite_contract(
        organization_profile_id="org_demo_sc",
        invitee_email="pilot.user@example.com",
        invitee_role="grant_manager",
        invite_status="draft",
    )
    adapter = adapt_external_auth_context(
        organization_profile_id="org_demo_sc",
        email="pilot.user@example.com",
        role="grant_manager",
        invite_id=invite["pilot_invite_id"],
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 37,
            "title": "External pilot auth path + customer invite boundary",
            "auth_provider_matrix": matrix,
            "recommended_auth_path": matrix["recommended_provider_id"],
            "pilot_invite": invite,
            "invite_status": invite["invite_status"],
            "external_auth_adapter": adapter,
            "external_auth_configured": False,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "pilot_go_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_login_ui_exposed": False,
            "buyer_summary": [
                "Recommended path: Auth0/OIDC + invite/allowlist org binding",
                "Invite contract defaults to draft; send blocked without auth/storage/pen-test",
                "External auth not configured — fixture/internal auth remains active",
                "Login is not live; controlled customer pilot remains NO_GO",
            ],
            "next_safe_actions": [
                matrix.get("owner_action_required"),
                "Keep invites in draft until owner approves provider + storage + pen-test",
                "Do not expose fake login UI",
            ],
            "human_review_required": True,
            "docs": [matrix.get("artifact")],
        }
    )


def external_pilot_auth_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "external_auth_configured",
        "login_live_claimed",
        "production_auth_claimed",
        "pilot_go_claimed",
        "fake_login_ui_exposed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if surface.get("invite_status") == "sent":
        fails.append("invite_sent")
    fails.extend(
        auth_provider_decision_matrix_invariant_failures(
            surface.get("auth_provider_matrix") or {}
        )
    )
    fails.extend(
        pilot_invite_contract_invariant_failures(surface.get("pilot_invite") or {})
    )
    fails.extend(
        external_auth_adapter_invariant_failures(
            surface.get("external_auth_adapter") or {}
        )
    )
    return fails
