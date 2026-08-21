"""Tests: Campaign Block 48 storage approval ingest + pilot rerun."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.gate21_storage_pilot_assembler_service import (
    build_gate21_storage_pilot_demo_surface,
    gate21_storage_pilot_demo_surface_invariant_failures,
)
from nativeforge.services.gate21_storage_pilot_rerun_service import (
    gate21_storage_pilot_rerun_invariant_failures,
    run_gate21_storage_pilot_rerun,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.storage_approval_token_ingest_service import (
    ingest_storage_owner_approval_token,
    storage_approval_token_ingest_invariant_failures,
)


def test_prompt_alone_is_not_approval(tmp_path: Path) -> None:
    missing = tmp_path / "no_token.json"
    result = ingest_storage_owner_approval_token(approval_path=missing)
    assert result["owner_storage_approval_present"] is False
    assert result["prompt_alone_is_not_approval"] is True
    assert result["production_storage_claimed"] is False
    assert storage_approval_token_ingest_invariant_failures(result) == []


def test_approval_with_secrets_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"approval_present": True, "client_secret": "nope"}),
        encoding="utf-8",
    )
    result = ingest_storage_owner_approval_token(approval_path=path)
    assert result["ingest_status"] == "REJECTED_SECRETS"
    assert result["owner_storage_approval_present"] is False


def test_rerun_keeps_claims_false() -> None:
    rerun = run_gate21_storage_pilot_rerun()
    assert rerun["production_storage_claimed"] is False
    assert rerun["pen_test_passed"] is False
    assert rerun["final_controlled_pilot_status"] != "CONTROLLED_CUSTOMER_GO"
    assert gate21_storage_pilot_rerun_invariant_failures(rerun) == []


def test_demo_and_bridge() -> None:
    surface = build_gate21_storage_pilot_demo_surface()
    assert gate21_storage_pilot_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["gate21_storage_pilot"]["owner_storage_approval_present"] is False
