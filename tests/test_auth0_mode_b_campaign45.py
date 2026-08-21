"""Tests: Campaign Block 45 Auth0 Mode A/B detector and pilot auth resolver."""

from __future__ import annotations

from nativeforge.services.auth0_mode_b_assembler_service import (
    auth0_mode_b_demo_surface_invariant_failures,
    build_auth0_mode_b_demo_surface,
)
from nativeforge.services.auth0_mode_b_execution_service import (
    auth0_mode_b_execution_invariant_failures,
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.auth0_mode_detector_service import (
    auth0_mode_detector_invariant_failures,
    detect_auth0_execution_mode,
)
from nativeforge.services.pilot_auth_readiness_resolver_service import (
    pilot_auth_readiness_resolver_invariant_failures,
    resolve_pilot_auth_readiness,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_mode_a_when_config_absent(monkeypatch) -> None:
    for key in (
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_CALLBACK_URL",
        "NF_AUTH0_LIVE_VALIDATION_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    mode = detect_auth0_execution_mode()
    assert mode["mode_a"] is True
    assert mode["mode_b_auth_possible"] is False
    assert mode["login_live_claimed"] is False
    assert mode["secret_value_printed"] is False
    assert auth0_mode_detector_invariant_failures(mode) == []


def test_execution_and_pilot_auth_keep_claims_false() -> None:
    execution = run_auth0_mode_b_execution_path()
    assert execution["mode_detected"] == "mode_a"
    assert execution["live_validation_attempted"] is False
    assert auth0_mode_b_execution_invariant_failures(execution) == []
    ready = resolve_pilot_auth_readiness(execution=execution)
    assert ready["login_live_claimed"] is False
    assert ready["controlled_pilot_auth_ready"] is False
    assert pilot_auth_readiness_resolver_invariant_failures(ready) == []


def test_demo_and_bridge() -> None:
    surface = build_auth0_mode_b_demo_surface()
    assert auth0_mode_b_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_mode_b"]["mode_detected"] == "mode_a"
    assert payload["auth0_mode_b"]["login_live_claimed"] is False
