"""Tests: Campaign Block 43 Auth0 live validation execution support."""

from __future__ import annotations

import json

from nativeforge.services.auth0_live_validation_assembler_service import (
    auth0_live_validation_demo_surface_invariant_failures,
    build_auth0_live_validation_demo_surface,
)
from nativeforge.services.auth0_live_validation_runner_service import (
    auth0_live_validation_runner_invariant_failures,
    run_auth0_live_validation,
)
from nativeforge.services.auth0_preflight_service import (
    auth0_preflight_invariant_failures,
    run_auth0_preflight,
)
from nativeforge.services.login_live_promotion_gate_service import (
    evaluate_login_live_promotion,
    login_live_promotion_gate_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_preflight_never_emits_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "super-secret-value-xyz-999")
    monkeypatch.setenv("OIDC_ISSUER", "https://example.auth0.com/")
    monkeypatch.setenv("OIDC_CLIENT_ID", "clientid123")
    monkeypatch.setenv("OIDC_CALLBACK_URL", "https://app.example/callback")
    preflight = run_auth0_preflight()
    blob = json.dumps(preflight)
    assert "super-secret-value-xyz-999" not in blob
    assert preflight["secret_value_emitted"] is False
    assert preflight["login_live_claimed"] is False
    assert auth0_preflight_invariant_failures(preflight) == []


def test_preflight_blocked_without_config(monkeypatch) -> None:
    for key in (
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_CALLBACK_URL",
        "OIDC_AUDIENCE",
        "OIDC_LOGOUT_URL",
        "OIDC_ALLOWED_ORIGIN",
    ):
        monkeypatch.delenv(key, raising=False)
    preflight = run_auth0_preflight()
    assert preflight["validation_possible"] is False
    assert preflight["auth0_preflight_status"] == "BLOCKED"


def test_runner_and_promotion_keep_login_false() -> None:
    validation = run_auth0_live_validation()
    assert validation["mode"] == "dry_run"
    assert validation["login_live_claimed"] is False
    assert auth0_live_validation_runner_invariant_failures(validation) == []
    promo = evaluate_login_live_promotion(validation_result=validation)
    assert promo["login_live_claimed"] is False
    assert promo["controlled_pilot_auth_ready"] is False
    assert "invite_binding_passed" in promo["missing_gates"]
    assert login_live_promotion_gate_invariant_failures(promo) == []


def test_demo_and_bridge() -> None:
    surface = build_auth0_live_validation_demo_surface()
    assert auth0_live_validation_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_live_validation"]["login_live_claimed"] is False
