"""Tests: Campaign Block 84 storage ingest."""

from nativeforge.services.gate35_ingest_assembler_service import (
    build_storage_ingest_demo_surface,
    storage_ingest_demo_surface_invariant_failures,
)
from nativeforge.services.gate35_storage_ingest_service import run_storage_real_ingest
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def _full_config(**extra: bool) -> dict[str, bool]:
    base = {
        "approval_artifact_present": True,
        "metadata_config_present": True,
        "object_config_present": True,
        "signed_url_config_present": True,
        "sse_kms_config_present": True,
        "malware_scan_config_present": True,
        "backup_restore_config_present": True,
        "retention_delete_export_config_present": True,
    }
    base.update(extra)
    return base


def test_storage_ingest_gates() -> None:
    missing = run_storage_real_ingest()
    assert missing["production_storage_claim"] is False
    no_cfg = run_storage_real_ingest(
        override=_full_config(
            metadata_config_present=False,
            object_config_present=False,
            signed_url_config_present=False,
            sse_kms_config_present=False,
            malware_scan_config_present=False,
            backup_restore_config_present=False,
            retention_delete_export_config_present=False,
        )
    )
    assert no_cfg["production_storage_claim"] is False
    no_appr = run_storage_real_ingest(
        override=_full_config(approval_artifact_present=False)
    )
    assert no_appr["production_storage_claim"] is False
    no_kms = run_storage_real_ingest(
        override=_full_config(sse_kms_config_present=False)
    )
    assert "sse_kms" in no_kms["missing_gates"]
    no_mal = run_storage_real_ingest(
        override=_full_config(malware_scan_config_present=False)
    )
    assert "malware_scan" in no_mal["missing_gates"]
    no_ret = run_storage_real_ingest(
        override=_full_config(retention_delete_export_config_present=False)
    )
    assert "retention_delete_export" in no_ret["missing_gates"]
    persist = run_storage_real_ingest(
        override=_full_config(), auth_policy_tenant_audit=False
    )
    assert persist["customer_persistence_claim"] is False


def test_demo_bridge() -> None:
    surface = build_storage_ingest_demo_surface()
    assert storage_ingest_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["storage_ingest"]["production_storage_claim"] is False
