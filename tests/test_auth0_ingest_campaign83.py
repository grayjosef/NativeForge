"""Tests: Campaign Block 83 Auth0 ingest."""

from nativeforge.services.gate35_auth0_ingest_service import run_auth0_real_ingest
from nativeforge.services.gate35_ingest_assembler_service import (
    auth0_ingest_demo_surface_invariant_failures,
    build_auth0_ingest_demo_surface,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_auth0_ingest_gates() -> None:
    missing = run_auth0_real_ingest()
    assert missing["wait_state"] == "blocked_owner_input"
    assert missing["login_live_claim"] is False
    synth = run_auth0_real_ingest(
        owner_payload={"fixture_kind": "synthetic_non_secret"},
        force_real_artifacts=True,
        live_validation_enabled=True,
    )
    assert synth["synthetic_artifacts_ignored"] is True
    assert synth["login_live_claim"] is False
    secret = run_auth0_real_ingest(
        owner_payload={"client_secret": "nope"},
        force_real_artifacts=True,
        live_validation_enabled=True,
    )
    assert secret["secrets_in_payload_rejected"] is True
    unval = run_auth0_real_ingest(
        force_real_artifacts=True,
        live_validation_enabled=True,
        present_unvalidated=True,
        callback_ok=True,
        session_ok=True,
    )
    assert unval["login_live_claim"] is False
    disabled = run_auth0_real_ingest(
        force_real_artifacts=True, live_validation_enabled=False
    )
    assert disabled["live_validation_attempted"] is False
    cb = run_auth0_real_ingest(
        force_real_artifacts=True,
        live_validation_enabled=True,
        callback_ok=False,
        session_ok=False,
    )
    assert cb["login_live_claim"] is False
    org = run_auth0_real_ingest(
        force_real_artifacts=True,
        live_validation_enabled=True,
        callback_ok=True,
        session_ok=True,
        org_ok=False,
        role_ok=False,
        audit_ok=True,
    )
    assert org["controlled_pilot_auth_ready"] is False
    audit = run_auth0_real_ingest(
        force_real_artifacts=True,
        live_validation_enabled=True,
        callback_ok=True,
        session_ok=True,
        org_ok=True,
        role_ok=True,
        audit_ok=False,
    )
    assert audit["production_auth_claim"] is False


def test_demo_bridge() -> None:
    surface = build_auth0_ingest_demo_surface()
    assert auth0_ingest_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_ingest"]["login_live_claim"] is False
