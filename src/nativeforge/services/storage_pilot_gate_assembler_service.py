"""Block 44 assembler: storage approval/provisioning + pilot gate surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.controlled_customer_pilot_gate_resolver_service import (
    controlled_customer_pilot_gate_resolver_invariant_failures,
    resolve_controlled_customer_pilot_gate,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
    storage_owner_approval_token_invariant_failures,
)
from nativeforge.services.storage_provisioning_execution_guard_service import (
    evaluate_storage_provisioning_guard,
    storage_provisioning_guard_invariant_failures,
)

SCHEMA_VERSION = "nf_storage_pilot_gate_assembler_v1"
DOCS = [
    "docs/operations/224_STORAGE_APPROVAL_AND_PROVISIONING_EXECUTION_RUNBOOK.md",
    "docs/operations/225_CONTROLLED_CUSTOMER_PILOT_GATE_RESOLVER.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_storage_pilot_gate_demo_surface() -> dict[str, Any]:
    approval = build_storage_owner_approval_token(present=False)
    guard = evaluate_storage_provisioning_guard(approval=approval)
    pilot = resolve_controlled_customer_pilot_gate(
        login_live=False,
        production_auth=False,
        storage_ready=False,
        customer_persistence_ready=False,
        full_sca_passed=True,
        pen_test_passed=False,
        owner_approval_present=False,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 44,
            "title": "Storage approval/provisioning path + controlled pilot gate",
            "docs": DOCS,
            "approval": approval,
            "owner_approval_present": False,
            "approval_scope": approval.get("approved_scope"),
            "provisioning_guard": guard,
            "dry_run_allowed": True,
            "real_provisioning_allowed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "pilot_gate": pilot,
            "controlled_customer_pilot_status": pilot.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": pilot.get("production_rollout_status"),
            "missing_gates": pilot.get("missing_gates"),
            "allowed_claims": pilot.get("allowed_claims"),
            "forbidden_claims": pilot.get("forbidden_claims"),
            "login_live_claimed": False,
            "buyer_summary": [
                "Storage owner approval token model is repo-safe (no secrets)",
                "Dry-run provisioning allowed; real provisioning blocked without approval",
                "Controlled customer pilot final gate defaults to NO_GO / internal-only",
                "Production rollout remains NO_GO",
            ],
            "next_safe_actions": [
                guard.get("next_safe_action"),
                pilot.get("next_safe_action"),
            ],
            "human_review_required": True,
        }
    )


def storage_pilot_gate_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "owner_approval_present",
        "real_provisioning_allowed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") in {
        "CONTROLLED_CUSTOMER_GO",
        "GO",
    }:
        fails.append("pilot_go")
    fails.extend(
        storage_owner_approval_token_invariant_failures(surface.get("approval") or {})
    )
    fails.extend(
        storage_provisioning_guard_invariant_failures(
            surface.get("provisioning_guard") or {}
        )
    )
    fails.extend(
        controlled_customer_pilot_gate_resolver_invariant_failures(
            surface.get("pilot_gate") or {}
        )
    )
    return fails
