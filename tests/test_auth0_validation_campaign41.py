"""Tests: Campaign Block 41 Auth0 validation + login claim resolver."""

from __future__ import annotations

from nativeforge.services.auth0_validation_assembler_service import (
    auth0_validation_demo_surface_invariant_failures,
    build_auth0_validation_demo_surface,
)
from nativeforge.services.auth0_validation_smoke_service import (
    run_auth0_validation_smoke,
)
from nativeforge.services.auth_validation_run_service import (
    REQUIRED_GATES,
    auth_validation_run_invariant_failures,
    build_auth_validation_run,
)
from nativeforge.services.login_claim_resolver_service import (
    login_claim_resolver_invariant_failures,
    resolve_login_claims,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_login_live_requires_all_gates() -> None:
    run = build_auth_validation_run(mode="dry_run")
    assert run["login_live_claimed"] is False
    assert len(run["validation_errors"]) == len(REQUIRED_GATES)
    assert auth_validation_run_invariant_failures(run) == []

    # Secret alone insufficient
    partial = build_auth_validation_run(
        mode="real_config", gates={"secret_present": True}
    )
    assert partial["all_gates_passed"] is False
    assert partial["login_live_claimed"] is False


def test_resolver_blocks_dry_run_and_fixture() -> None:
    for mode in ("dry_run", "fixture_internal"):
        run = build_auth_validation_run(mode=mode)
        resolved = resolve_login_claims(validation_run=run)
        assert resolved["login_live_claimed"] is False
        assert resolved["controlled_pilot_auth_ready"] is False
        assert login_claim_resolver_invariant_failures(resolved) == []


def test_smoke_and_bridge() -> None:
    smoke = run_auth0_validation_smoke()
    assert smoke["overall_status"] == "PASS"
    assert smoke["secret_value_printed"] is False
    assert smoke["login_live_claimed"] is False
    surface = build_auth0_validation_demo_surface()
    assert auth0_validation_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["auth0_validation"]["login_live_claimed"] is False
