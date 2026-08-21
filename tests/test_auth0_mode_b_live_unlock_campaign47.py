"""Tests: Campaign Block 47 Auth0 Mode B live unlock attempt."""

from __future__ import annotations

from nativeforge.services.auth0_mode_b_live_unlock_assembler_service import (
    auth0_mode_b_live_unlock_demo_surface_invariant_failures,
    build_auth0_mode_b_live_unlock_demo_surface,
)
from nativeforge.services.auth0_mode_b_live_unlock_service import (
    auth0_mode_b_live_unlock_invariant_failures,
    run_auth0_mode_b_live_unlock_attempt,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_unlock_stays_false_without_config(monkeypatch) -> None:
    for key in (
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_CALLBACK_URL",
        "NF_AUTH0_LIVE_VALIDATION_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    attempt = run_auth0_mode_b_live_unlock_attempt()
    assert attempt["mode_detected"] == "mode_a"
    assert attempt["owner_config_present"] is False
    assert attempt["login_live_claimed"] is False
    assert attempt["secret_value_printed"] is False
    assert auth0_mode_b_live_unlock_invariant_failures(attempt) == []


def test_demo_and_bridge() -> None:
    surface = build_auth0_mode_b_live_unlock_demo_surface()
    assert auth0_mode_b_live_unlock_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_mode_b_live_unlock"]["login_live_claimed"] is False
