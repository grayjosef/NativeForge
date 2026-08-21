"""Auth provider decision matrix for controlled customer pilot (Block 37)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_auth_provider_decision_matrix_v1"
DOC_ARTIFACT = "docs/operations/204_AUTH_PROVIDER_DECISION_MATRIX.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth_provider_decision_matrix() -> dict[str, Any]:
    options = [
        {
            "provider_id": "fixture_internal",
            "label": "Existing internal/fixture auth",
            "setup_complexity": "none",
            "security_posture": "demo_only",
            "rbac_compatibility": "high",
            "org_binding_support": "fixture",
            "invite_allowlist_support": "partial",
            "auditability": "model_level",
            "implementation_risk": "low",
            "sunday_feasibility": "already_in_place",
            "production_suitability": "not_suitable",
            "required_secrets_config": [],
            "no_go_risks": ["not_customer_facing", "no_real_identity"],
            "recommendation": "keep_for_demo_and_tests",
        },
        {
            "provider_id": "external_pilot_allowlist",
            "label": "External pilot allowlist (email allowlist + invite)",
            "setup_complexity": "medium",
            "security_posture": "controlled_pilot",
            "rbac_compatibility": "high",
            "org_binding_support": "required",
            "invite_allowlist_support": "high",
            "auditability": "high",
            "implementation_risk": "medium",
            "sunday_feasibility": "feasible_after_owner_auth_choice",
            "production_suitability": "pilot_only",
            "required_secrets_config": ["INVITE_SIGNING_SECRET"],
            "no_go_risks": ["needs_IdP_or_magic_link", "not_production_scale"],
            "recommendation": "pair_with_OIDC",
        },
        {
            "provider_id": "google_oauth_workspace",
            "label": "Google OAuth / Workspace-compatible",
            "setup_complexity": "medium",
            "security_posture": "strong_for_known_domains",
            "rbac_compatibility": "high_with_org_binding",
            "org_binding_support": "email_domain_plus_allowlist",
            "invite_allowlist_support": "high",
            "auditability": "high",
            "implementation_risk": "medium",
            "sunday_feasibility": "conditional",
            "production_suitability": "good_for_pilot",
            "required_secrets_config": [
                "GOOGLE_OAUTH_CLIENT_ID",
                "GOOGLE_OAUTH_CLIENT_SECRET",
            ],
            "no_go_risks": ["domain_assumption", "non_Google_users"],
            "recommendation": "strong_candidate_if_pilot_orgs_on_Google",
        },
        {
            "provider_id": "auth0_oidc",
            "label": "Auth0 / OIDC-compatible path",
            "setup_complexity": "medium_high",
            "security_posture": "strong",
            "rbac_compatibility": "high",
            "org_binding_support": "claims_mapping",
            "invite_allowlist_support": "high",
            "auditability": "high",
            "implementation_risk": "medium",
            "sunday_feasibility": "conditional",
            "production_suitability": "strong",
            "required_secrets_config": [
                "OIDC_ISSUER",
                "OIDC_CLIENT_ID",
                "OIDC_CLIENT_SECRET",
            ],
            "no_go_risks": ["vendor_setup_time", "claim_mapping_errors"],
            "recommendation": "recommended_default_for_controlled_pilot",
        },
        {
            "provider_id": "supabase_auth",
            "label": "Supabase Auth (if already in stack)",
            "setup_complexity": "low_if_present",
            "security_posture": "good",
            "rbac_compatibility": "medium",
            "org_binding_support": "custom_metadata",
            "invite_allowlist_support": "medium",
            "auditability": "medium",
            "implementation_risk": "medium",
            "sunday_feasibility": "low_not_in_stack",
            "production_suitability": "conditional",
            "required_secrets_config": ["SUPABASE_URL", "SUPABASE_ANON_KEY"],
            "no_go_risks": ["not_present_in_NativeForge_stack"],
            "recommendation": "reject_unless_already_adopted",
        },
        {
            "provider_id": "custom_auth",
            "label": "Custom auth",
            "setup_complexity": "very_high",
            "security_posture": "unknown_high_risk",
            "rbac_compatibility": "unknown",
            "org_binding_support": "custom",
            "invite_allowlist_support": "custom",
            "auditability": "unknown",
            "implementation_risk": "very_high",
            "sunday_feasibility": "not_feasible",
            "production_suitability": "not_recommended",
            "required_secrets_config": ["CUSTOM_AUTH_*"],
            "no_go_risks": ["security_debt", "time"],
            "recommendation": "reject",
        },
        {
            "provider_id": "production_not_supported",
            "label": "Production auth not supported yet",
            "setup_complexity": "n/a",
            "security_posture": "n/a",
            "rbac_compatibility": "n/a",
            "org_binding_support": "n/a",
            "invite_allowlist_support": "n/a",
            "auditability": "n/a",
            "implementation_risk": "n/a",
            "sunday_feasibility": "honest_status",
            "production_suitability": "not_supported",
            "required_secrets_config": [],
            "no_go_risks": ["must_not_claim_production_auth"],
            "recommendation": "keep_as_status_until_pilot_path_validated",
        },
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact": DOC_ARTIFACT,
            "options": options,
            "recommended_provider_id": "auth0_oidc",
            "recommended_path_summary": (
                "Auth0/OIDC + invite/allowlist org binding; keep fixture auth for "
                "demo/tests until secrets configured and owner approves"
            ),
            "external_auth_configured": False,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "owner_action_required": (
                "Owner selects Auth0/OIDC (or Google if pilot orgs are Workspace-only) "
                "and provisions secrets; do not claim login live until validated"
            ),
        }
    )


def auth_provider_decision_matrix_invariant_failures(
    matrix: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "external_auth_configured",
        "login_live_claimed",
        "production_auth_claimed",
    ):
        if matrix.get(key) is True:
            fails.append(key)
    if matrix.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if matrix.get("recommended_provider_id") != "auth0_oidc":
        fails.append("unexpected_recommendation")
    if len(matrix.get("options") or []) < 6:
        fails.append("too_few_options")
    return fails
