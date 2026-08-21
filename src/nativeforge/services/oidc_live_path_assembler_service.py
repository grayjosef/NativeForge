"""Block 39 assembler: Auth0/OIDC live-path validation surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.oidc_callback_validation_harness_service import (
    oidc_callback_harness_invariant_failures,
    run_oidc_callback_validation_harness,
)
from nativeforge.services.oidc_config_schema_service import (
    build_oidc_config_schema,
    oidc_config_schema_invariant_failures,
)
from nativeforge.services.oidc_identity_mapper_service import (
    map_oidc_claims_to_auth_context,
    oidc_identity_mapper_invariant_failures,
)

SCHEMA_VERSION = "nf_oidc_live_path_assembler_v1"
OWNER_DOC = "docs/operations/212_AUTH0_OIDC_OWNER_SETUP_CHECKLIST.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_oidc_live_path_demo_surface() -> dict[str, Any]:
    cfg = build_oidc_config_schema(force_unconfigured=True)
    harness = run_oidc_callback_validation_harness()
    mapped = map_oidc_claims_to_auth_context(
        subject="oidc_sub_demo",
        email="pilot@example.com",
        email_verified=True,
        organization_claim="org_demo_sc",
        allowed_org_binding="org_demo_sc",
        invite_id="pi_demo",
        roles_or_groups=["grant_manager"],
        provider_validated=False,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 39,
            "title": "Auth0/OIDC live-path validation checklist",
            "oidc_config": cfg,
            "provider_configured": False,
            "provider_validated": False,
            "login_live_claimed": False,
            "callback_harness": harness,
            "identity_mapper_sample": mapped,
            "invite_allowlist_binding": True,
            "org_binding_behavior": "deny_on_mismatch",
            "role_mapping_behavior": "groups_to_rbac_role_or_unknown",
            "rbac_handoff": True,
            "audit_events": True,
            "owner_setup_checklist": OWNER_DOC,
            "fake_login_ui_exposed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "buyer_summary": [
                "Auth0/OIDC config schema ready — secrets never stored as values",
                "Callback/session validation harness passes dry-run scenarios",
                "OIDC identity maps to RBAC/tenant context only after validation",
                "Login is not live; controlled customer pilot remains NO_GO",
            ],
            "next_safe_actions": [
                "Owner completes 212_AUTH0_OIDC_OWNER_SETUP_CHECKLIST.md",
                "Set OIDC_* env vars outside git; run harness dry-run",
                "Do not claim login_live until callback + session validated",
            ],
            "human_review_required": True,
        }
    )


def oidc_live_path_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "provider_configured",
        "provider_validated",
        "login_live_claimed",
        "fake_login_ui_exposed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        oidc_config_schema_invariant_failures(surface.get("oidc_config") or {})
    )
    fails.extend(
        oidc_callback_harness_invariant_failures(surface.get("callback_harness") or {})
    )
    fails.extend(
        oidc_identity_mapper_invariant_failures(
            surface.get("identity_mapper_sample") or {}
        )
    )
    return fails
