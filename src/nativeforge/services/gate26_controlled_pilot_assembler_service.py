"""Block 58 assembler: controlled pilot master resolver surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate26_controlled_pilot_master_service import (
    build_mode_a_pilot_master_packet,
    controlled_pilot_master_invariant_failures,
)

SCHEMA_VERSION = "nf_gate26_pilot_master_assembler_v1"
DOC = "docs/operations/267_GATE26_CONTROLLED_PILOT_MASTER_RESOLVER.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_controlled_pilot_master_demo_surface() -> dict[str, Any]:
    packet = build_mode_a_pilot_master_packet()
    master = packet.get("master") or {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 58,
            "title": "Controlled pilot master GO/NO-GO resolver",
            "docs": [DOC],
            "master_resolver": True,
            "auth_gate_summary": "login_live=false; production_auth=false",
            "storage_gate_summary": "production_storage=false",
            "customer_data_policy_gate_summary": "policy_required; persistence=false",
            "tenant_session_rbac_gate_summary": "model enforced; dry-run session",
            "sca_gate": master.get("sca_gate"),
            "pen_test_gate_summary": "no_report; pen_test_passed=false",
            "authority_gate": master.get("authority_gate"),
            "source_coverage_gate": master.get("source_coverage_gate"),
            "invite_support_gate_summary": "invite not ready",
            "ux_readiness_gate": master.get("ux_readiness_gate"),
            "controlled_customer_pilot_status": master.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": master.get("production_rollout_status"),
            "allowed_claims": master.get("allowed_claims"),
            "forbidden_claims": master.get("forbidden_claims"),
            "missing_gates": master.get("missing_gates"),
            "next_owner_actions": master.get("next_owner_actions"),
            "fake_pilot_ready_banner": False,
            "fake_secure_badge": False,
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "pen_test_passed_claimed": False,
            "buyer_summary": [
                "Master pilot resolver aggregates auth, storage, policy, audit, security",
                "Mode A remains CONDITIONAL_INTERNAL_ONLY / NO_GO — not pilot GO",
                "Exact missing gates and forbidden claims are visible to operators",
                "Production rollout stays NO_GO until every production gate passes",
            ],
            "next_safe_actions": master.get("next_owner_actions") or [],
            "human_review_required": True,
            "packet": packet,
            "master": master,
        }
    )


def controlled_pilot_master_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "fake_pilot_ready_banner",
        "fake_secure_badge",
        "login_live_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    status = surface.get("controlled_customer_pilot_status")
    if status == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    if surface.get("production_rollout_status") == "GO":
        fails.append("rollout_go")
    fails.extend(
        controlled_pilot_master_invariant_failures(surface.get("master") or {})
    )
    return fails
