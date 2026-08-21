"""Tests: Campaign Block 39 Auth0/OIDC live-path."""

from __future__ import annotations

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
from nativeforge.services.oidc_live_path_assembler_service import (
    build_oidc_live_path_demo_surface,
    oidc_live_path_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_missing_config_cannot_claim_login_live() -> None:
    cfg = build_oidc_config_schema(force_unconfigured=True)
    assert cfg["configured_status"] is False
    assert cfg["login_live_claimed"] is False
    assert cfg["client_secret_value"] is None
    assert oidc_config_schema_invariant_failures(cfg) == []


def test_mapper_and_harness() -> None:
    mapped = map_oidc_claims_to_auth_context(
        subject="s1",
        email="a@example.com",
        email_verified=False,
        organization_claim="org_a",
        allowed_org_binding="org_b",
        invite_id=None,
        provider_validated=False,
    )
    assert mapped["login_live_claimed"] is False
    assert "email_not_verified" in mapped["denial_reasons"]
    assert "org_mismatch" in mapped["denial_reasons"]
    assert oidc_identity_mapper_invariant_failures(mapped) == []
    harness = run_oidc_callback_validation_harness()
    assert harness["overall_status"] == "PASS"
    assert oidc_callback_harness_invariant_failures(harness) == []


def test_demo_and_bridge() -> None:
    surface = build_oidc_live_path_demo_surface()
    assert oidc_live_path_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["oidc_live_path"]["login_live_claimed"] is False
