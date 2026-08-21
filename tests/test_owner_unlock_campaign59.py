"""Tests: Campaign Block 59 owner Mode B unlock packet."""

from __future__ import annotations

from nativeforge.services.gate27_owner_unlock_assembler_service import (
    build_owner_unlock_demo_surface,
    owner_unlock_demo_surface_invariant_failures,
)
from nativeforge.services.gate27_owner_unlock_packet_service import (
    build_owner_unlock_packet,
    clear_owner_unlock_audit_for_tests,
    owner_unlock_packet_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_prompt_and_secrets_rejected() -> None:
    clear_owner_unlock_audit_for_tests()
    packet = build_owner_unlock_packet()
    assert packet["prompt_alone_is_not_approval"] is True
    assert packet["mode"] == "A"
    assert packet["login_live_claimed"] is False
    assert packet["production_storage_claimed"] is False
    assert packet["pen_test_passed_claimed"] is False
    assert packet["no_secret_validation"] is True
    assert "auth0:issuer_domain" in packet["missing_owner_inputs"]
    assert owner_unlock_packet_invariant_failures(packet) == []

    bad = build_owner_unlock_packet(
        repo_safe_artifact={"client_secret": "SHOULD_NOT", "approval_present": True}
    )
    assert bad["artifact_rejected_for_secrets"] is True
    assert bad["mode"] == "A"


def test_missing_gates_and_complete_packet_mode_b_ready_not_go() -> None:
    incomplete = build_owner_unlock_packet(
        auth0_inputs={"issuer_domain": True},
        storage_inputs={},
        security_inputs={},
    )
    assert incomplete["mode"] == "A"
    assert incomplete["auth0_complete"] is False

    complete = build_owner_unlock_packet(
        auth0_inputs={
            "issuer_domain": True,
            "audience": True,
            "client_id": True,
            "client_secret_present_oob": True,
            "callback_url": True,
            "logout_url": True,
            "allowed_origins": True,
            "live_validation_enable_flag": True,
            "invite_allowlist": True,
            "org_binding": True,
            "role_mapping": True,
        },
        storage_inputs={
            "repo_safe_owner_approval_token": True,
            "metadata_backend_config_oob": True,
            "object_storage_config_oob": True,
            "bucket_key_policy_confirmation": True,
            "signed_url_config": True,
            "sse_kms_confirmation": True,
            "malware_scan_config": True,
            "backup_restore_config": True,
            "retention_delete_config": True,
        },
        security_inputs={
            "pen_test_provider_report_ref": True,
            "test_window": True,
            "scope": True,
            "findings_summary": True,
            "remediation_status": True,
            "retest_status": True,
            "pass_evidence_if_applicable": True,
        },
    )
    assert complete["mode_b_ready"] is True
    assert complete["mode"] == "B_ready_incomplete"
    assert complete["mode_b_executed"] is False
    assert complete["login_live_claimed"] is False
    assert complete["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    dumped = json_dumps_safe(complete)
    assert "SHOULD_NOT" not in dumped
    assert "sk_live_" not in dumped
    assert complete["no_secret_validation"] is True
    assert complete["secrets_in_output"] is False


def json_dumps_safe(obj: dict) -> str:
    import json

    return json.dumps(obj)


def test_demo_and_bridge() -> None:
    surface = build_owner_unlock_demo_surface()
    assert owner_unlock_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["owner_unlock_packet"]["fake_mode_b"] is False
    assert payload["owner_unlock_packet"]["login_live_claimed"] is False
