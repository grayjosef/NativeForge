"""Tests: Campaign Block 64 storage + pen-test real evidence ingest."""

from __future__ import annotations

from nativeforge.services.gate28_mode_b_rehearsal_service import (
    build_synthetic_non_secret_fixture,
)
from nativeforge.services.gate29_storage_security_assembler_service import (
    build_storage_security_real_input_demo_surface,
    storage_security_real_input_demo_surface_invariant_failures,
)
from nativeforge.services.gate29_storage_security_real_input_service import (
    run_storage_security_real_input_ingest,
    storage_security_real_input_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

_FULL_STORAGE = {
    "approval_token_present": True,
    "approval_token_valid": True,
    "metadata_config_present": True,
    "object_config_present": True,
    "signed_url_config_present": True,
    "sse_encryption_config_present": True,
    "malware_scan_config_present": True,
    "backup_restore_config_present": True,
    "retention_delete_config_present": True,
}


def test_synthetic_storage_cannot_unlock() -> None:
    fixture = build_synthetic_non_secret_fixture()
    result = run_storage_security_real_input_ingest(
        owner_storage=fixture,
        **_FULL_STORAGE,
    )
    assert result["synthetic_storage_artifacts_ignored"] is True
    assert result["production_storage_claimed"] is False
    assert result["approval_token_present"] is False


def test_missing_approval_and_config_split() -> None:
    missing_approval = run_storage_security_real_input_ingest(
        metadata_config_present=True,
        object_config_present=True,
        signed_url_config_present=True,
        sse_encryption_config_present=True,
        malware_scan_config_present=True,
        backup_restore_config_present=True,
        retention_delete_config_present=True,
    )
    assert missing_approval["production_storage_claimed"] is False
    assert "repo_safe_storage_approval" in missing_approval["missing_gates"]

    approval_only = run_storage_security_real_input_ingest(
        approval_token_present=True,
        approval_token_valid=True,
    )
    assert approval_only["production_storage_claimed"] is False
    assert "metadata_config_oob" in approval_only["missing_gates"]


def test_sse_and_malware_block_persistence() -> None:
    kwargs = dict(_FULL_STORAGE)
    kwargs["sse_encryption_config_present"] = False
    kwargs["login_live"] = True
    kwargs["customer_data_policy_approved"] = True
    kwargs["tenant_ok"] = True
    kwargs["audit_ok"] = True
    result = run_storage_security_real_input_ingest(**kwargs)
    assert result["customer_persistence_claimed"] is False
    assert "sse_kms_config" in result["missing_gates"]

    kwargs = dict(_FULL_STORAGE)
    kwargs["malware_scan_config_present"] = False
    kwargs["login_live"] = True
    kwargs["customer_data_policy_approved"] = True
    kwargs["tenant_ok"] = True
    kwargs["audit_ok"] = True
    result = run_storage_security_real_input_ingest(**kwargs)
    assert result["customer_persistence_claimed"] is False
    assert "malware_scan_config" in result["missing_gates"]


def test_customer_persistence_needs_auth_policy_tenant_audit() -> None:
    result = run_storage_security_real_input_ingest(**_FULL_STORAGE)
    assert result["customer_persistence_claimed"] is False
    assert "login_live" in result["missing_gates"]


def test_synthetic_pentest_and_open_findings() -> None:
    fixture = build_synthetic_non_secret_fixture()
    syn = run_storage_security_real_input_ingest(
        owner_pen_test=fixture,
        report_present=True,
        scope_validated=True,
        critical_high_open=False,
        remediation_required=False,
        retest_required=False,
        pass_evidence=True,
    )
    assert syn["pen_test_pass_claimed"] is False
    assert syn["synthetic_pen_test_artifacts_ignored"] is True

    missing = run_storage_security_real_input_ingest()
    assert missing["pen_test_pass_claimed"] is False
    assert "pen_test_report" in missing["missing_gates"]

    open_high = run_storage_security_real_input_ingest(
        report_present=True,
        scope_validated=True,
        critical_high_open=True,
        remediation_required=False,
        retest_required=False,
        pass_evidence=True,
    )
    assert open_high["pen_test_pass_claimed"] is False
    assert open_high["critical_high_open"] is True


def test_pilot_below_go_and_freeze() -> None:
    result = run_storage_security_real_input_ingest()
    assert result["controlled_customer_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert result["production_rollout_status"] == "PRODUCTION_ROLLOUT_NO_GO"
    assert result["claim_freeze_verified"] is True
    assert storage_security_real_input_invariant_failures(result) == []


def test_demo_and_bridge() -> None:
    surface = build_storage_security_real_input_demo_surface()
    assert storage_security_real_input_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["storage_security_real_input"]["production_storage_claimed"] is False
    assert payload["storage_security_real_input"]["pen_test_pass_claimed"] is False
    assert payload["storage_security_real_input"]["fake_pilot_ready"] is False
