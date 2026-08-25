"""Tests: Campaign Block 61 Mode B rehearsal."""

from __future__ import annotations

import json

from nativeforge.services.gate28_mode_b_rehearsal_assembler_service import (
    build_mode_b_rehearsal_demo_surface,
    mode_b_rehearsal_demo_surface_invariant_failures,
)
from nativeforge.services.gate28_mode_b_rehearsal_service import (
    mode_b_rehearsal_invariant_failures,
    run_mode_b_rehearsal,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_synthetic_does_not_unlock_live_claims() -> None:
    result = run_mode_b_rehearsal(use_synthetic=True)
    assert result["synthetic_fixture_used"] is True
    assert result["real_owner_inputs_present"] is False
    assert result["mode_b_executed_claimed"] is False
    assert result["login_live_claimed"] is False
    assert result["production_storage_claimed"] is False
    assert result["pen_test_passed_claimed"] is False
    assert result["controlled_customer_pilot_go_claimed"] is False
    assert result["claim_freeze_verified"] is True
    assert "real_auth0_oidc_oob" in result["missing_real_inputs"]
    assert mode_b_rehearsal_invariant_failures(result) == []
    dumped = json.dumps(result)
    assert "sk_live_" not in dumped
    assert "begin rsa private" not in dumped.lower()


def test_secret_fixture_rejected() -> None:
    result = run_mode_b_rehearsal(
        use_synthetic=False,
        repo_safe_fixture={"client_secret": "NOPE", "approval_present": True},
    )
    assert "client_secret" in result["rejected_secret_keys"]
    assert result["mode_b_executed_claimed"] is False


def test_demo_and_bridge() -> None:
    surface = build_mode_b_rehearsal_demo_surface()
    assert mode_b_rehearsal_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["mode_b_rehearsal"]["mode_b_executed_claimed"] is False
    assert payload["mode_b_rehearsal"]["fake_mode_b"] is False
