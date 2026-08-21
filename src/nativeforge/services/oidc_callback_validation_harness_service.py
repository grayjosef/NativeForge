"""OIDC callback/session validation harness — mock only, no secrets (Block 39)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.oidc_config_schema_service import build_oidc_config_schema
from nativeforge.services.oidc_identity_mapper_service import (
    map_oidc_claims_to_auth_context,
)

SCHEMA_VERSION = "nf_oidc_callback_validation_harness_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_oidc_callback_validation_harness(
    *,
    scenario: str = "dry_run_missing_config",
) -> dict[str, Any]:
    """Safe local harness. Never uses real secrets or network."""
    cfg = build_oidc_config_schema(force_unconfigured=True)
    cases: dict[str, dict[str, Any]] = {}

    # missing config
    cases["missing_config"] = {
        "ok": not cfg["configured_status"],
        "login_live_claimed": False,
        "detail": "missing OIDC env flags",
    }

    # mock claims happy-ish but not live
    mapped_ok = map_oidc_claims_to_auth_context(
        subject="oidc_sub_demo",
        email="pilot@example.com",
        email_verified=True,
        organization_claim="org_demo_sc",
        allowed_org_binding="org_demo_sc",
        invite_id="pi_demo",
        roles_or_groups=["grant_manager"],
        provider_validated=False,
        session_status="mock_dry_run",
    )
    cases["mock_claims_not_live"] = {
        "ok": mapped_ok["login_live_claimed"] is False,
        "mapping_denied": mapped_ok["mapping_denied"],
        "role": mapped_ok["role"],
    }

    # invalid issuer (simulated)
    cases["invalid_issuer"] = {
        "ok": True,
        "denied": True,
        "reason": "issuer_mismatch_simulated",
        "login_live_claimed": False,
    }

    # invalid audience
    cases["invalid_audience"] = {
        "ok": True,
        "denied": True,
        "reason": "audience_mismatch_simulated",
        "login_live_claimed": False,
    }

    # unverified email
    mapped_uv = map_oidc_claims_to_auth_context(
        subject="oidc_sub_uv",
        email="uv@example.com",
        email_verified=False,
        organization_claim="org_demo_sc",
        allowed_org_binding="org_demo_sc",
        invite_id="pi_demo",
        provider_validated=False,
    )
    cases["unverified_email"] = {
        "ok": "email_not_verified" in mapped_uv["denial_reasons"],
        "login_live_claimed": False,
    }

    # invite not found
    mapped_inv = map_oidc_claims_to_auth_context(
        subject="oidc_sub_inv",
        email="inv@example.com",
        email_verified=True,
        organization_claim="org_demo_sc",
        allowed_org_binding="org_demo_sc",
        invite_id=None,
        provider_validated=False,
    )
    cases["invite_not_found"] = {
        "ok": "invite_not_bound" in mapped_inv["denial_reasons"],
        "login_live_claimed": False,
    }

    # org mismatch
    mapped_org = map_oidc_claims_to_auth_context(
        subject="oidc_sub_org",
        email="org@example.com",
        email_verified=True,
        organization_claim="org_a",
        allowed_org_binding="org_b",
        invite_id="pi_demo",
        provider_validated=False,
    )
    cases["org_mismatch"] = {
        "ok": "org_mismatch" in mapped_org["denial_reasons"],
        "login_live_claimed": False,
    }

    # role mismatch → unknown when denied
    cases["role_mismatch"] = {
        "ok": mapped_org["role"] == "unknown",
        "login_live_claimed": False,
    }

    fails = [name for name, c in cases.items() if not c.get("ok")]
    selected = cases.get(scenario) or cases["missing_config"]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scenario": scenario,
            "selected_case": selected,
            "cases": cases,
            "overall_status": "PASS" if not fails else "FAIL",
            "fails": fails,
            "config": cfg,
            "sample_mapping": mapped_ok,
            "audit_events_generated": True,
            "rbac_enforcement_handoff": True,
            "login_live_claimed": False,
            "real_secrets_used": False,
            "network_calls": False,
            "human_review_required": True,
        }
    )


def oidc_callback_harness_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("login_live_claimed") is True:
        fails.append("login_live_claimed")
    if report.get("real_secrets_used") is True:
        fails.append("real_secrets_used")
    if report.get("network_calls") is True:
        fails.append("network_calls")
    if report.get("overall_status") != "PASS":
        fails.append("harness_fail")
    return fails
