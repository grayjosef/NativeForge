"""Tests: Campaign Block 63 Auth0 real-input ingest."""

from __future__ import annotations

import json

from nativeforge.services.gate28_mode_b_rehearsal_service import (
    build_synthetic_non_secret_fixture,
)
from nativeforge.services.gate29_auth0_real_input_assembler_service import (
    auth0_real_input_demo_surface_invariant_failures,
    build_auth0_real_input_demo_surface,
)
from nativeforge.services.gate29_auth0_real_input_service import (
    auth0_real_input_invariant_failures,
    run_auth0_real_input_ingest,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

_ALL_LIVE = {
    "issuer_validated": True,
    "jwks_validated": True,
    "audience_validated": True,
    "callback_validated": True,
    "session_validated": True,
    "logout_validated": True,
    "invite_binding_passed": True,
    "org_binding_passed": True,
    "role_mapping_passed": True,
    "rbac_handoff_passed": True,
    "tenant_boundary_passed": True,
    "audit_event_emitted": True,
}


def test_synthetic_fixture_cannot_unlock_mode_b() -> None:
    fixture = build_synthetic_non_secret_fixture()
    result = run_auth0_real_input_ingest(
        owner_inputs=fixture,
        live_validation_enabled=True,
        **_ALL_LIVE,
    )
    assert result["synthetic_rehearsal_artifacts_ignored"] is True
    assert result["real_owner_auth0_inputs_present"] is False
    assert result["login_live_claimed"] is False
    assert result["mode_b_executed_claimed"] is False
    assert result["live_validation_attempted"] is False
    dumped = json.dumps(result)
    assert "sk_live_" not in dumped
    assert "begin rsa private" not in dumped.lower()


def test_missing_oidc_core_blocks_live_validation() -> None:
    result = run_auth0_real_input_ingest(live_validation_enabled=True)
    assert result["live_validation_attempted"] is False
    assert result["login_live_claimed"] is False
    assert "real_owner_auth0_oob" in result["missing_gates"]


def test_secret_present_alone_cannot_unlock() -> None:
    result = run_auth0_real_input_ingest(
        owner_inputs={
            "real_owner_auth0_inputs_present": True,
            "secret_present_redacted": True,
        }
    )
    assert result["login_live_claimed"] is False
    assert result["production_auth_claimed"] is False


def test_live_validation_flag_alone_cannot_unlock() -> None:
    result = run_auth0_real_input_ingest(live_validation_enabled=True)
    assert result["login_live_claimed"] is False


def test_missing_callback_blocks_login_live() -> None:
    kwargs = dict(_ALL_LIVE)
    kwargs["callback_validated"] = False
    result = run_auth0_real_input_ingest(
        owner_inputs={
            "real_owner_auth0_inputs_present": True,
            "secret_present_redacted": True,
        },
        live_validation_enabled=True,
        **kwargs,
    )
    assert result["login_live_claimed"] is False
    assert "callback_validated" in result["missing_gates"]


def test_missing_invite_org_role_blocks_pilot_auth() -> None:
    kwargs = dict(_ALL_LIVE)
    kwargs["invite_binding_passed"] = False
    kwargs["org_binding_passed"] = False
    kwargs["role_mapping_passed"] = False
    result = run_auth0_real_input_ingest(
        owner_inputs={
            "real_owner_auth0_inputs_present": True,
            "secret_present_redacted": True,
        },
        live_validation_enabled=True,
        **kwargs,
    )
    assert result["login_live_claimed"] is True
    assert result["controlled_pilot_auth_ready"] is False
    assert result["production_auth_claimed"] is False


def test_rbac_tenant_audit_block_login_live() -> None:
    for fail_key in (
        "rbac_handoff_passed",
        "tenant_boundary_passed",
        "audit_event_emitted",
    ):
        kwargs = dict(_ALL_LIVE)
        kwargs[fail_key] = False
        result = run_auth0_real_input_ingest(
            owner_inputs={
                "real_owner_auth0_inputs_present": True,
                "secret_present_redacted": True,
            },
            live_validation_enabled=True,
            **kwargs,
        )
        assert result["login_live_claimed"] is False, fail_key


def test_secret_like_keys_rejected() -> None:
    result = run_auth0_real_input_ingest(
        owner_inputs={
            "client_secret": "NOPE",
            "real_owner_auth0_inputs_present": True,
        },
        live_validation_enabled=True,
    )
    assert "client_secret" in result["rejected_secret_keys"]
    assert result["login_live_claimed"] is False
    assert "sk_live_" not in json.dumps(result)


def test_mode_a_demo_and_bridge() -> None:
    surface = build_auth0_real_input_demo_surface()
    assert auth0_real_input_demo_surface_invariant_failures(surface) == []
    assert auth0_real_input_invariant_failures(surface["result"]) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_real_input"]["login_live_claimed"] is False
    assert payload["auth0_real_input"]["synthetic_rehearsal_artifacts_ignored"] is True
