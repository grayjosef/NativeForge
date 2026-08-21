"""Gate 10 Block 26 assembler: pilot auth spike + pen-test packet + Monday closeout."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.external_pilot_auth_spike_service import (
    build_external_pilot_auth_spike,
    external_pilot_auth_spike_invariant_failures,
)
from nativeforge.services.pen_test_sca_readiness_packet_service import (
    build_pen_test_sca_readiness_packet,
    pen_test_sca_packet_invariant_failures,
)

SCHEMA_VERSION = "nf_gate10_closeout_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_gate10_closeout_demo_surface() -> dict[str, Any]:
    spike = build_external_pilot_auth_spike()
    # Prefer not to block demo on SCA tooling; still report honestly
    packet = build_pen_test_sca_readiness_packet(run_sca=False)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 26,
            "title": "External pilot / pen-test readiness + Monday closeout",
            "external_pilot_auth_spike": spike,
            "pen_test_sca_packet": packet,
            "buyer_summary": [
                "Local/dev persistent evidence storage validated (Gate 10 Block 25)",
                "External pilot auth path scoped — login not live",
                "Pen-test / SCA readiness packets complete — neither claimed passed",
                "Monday demo GO; controlled customer pilot NO_GO; production NO_GO",
            ],
            "monday_demo_status": "GO",
            "internal_pilot_status": "CONDITIONAL_GO",
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "production_multi_tenant_claimed": False,
            "pen_test_passed_claimed": False,
            "sca_passed_claimed": False,
            "upload_persistence_scope": "local_dev_only",
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "final_allowed_claims": [
                "Monday buyer demo GO",
                "Local/dev validated persistent evidence storage",
                "Evidence create/read/link/review/reject/archive in local/dev",
                "External pilot auth path scoped",
                "Pen-test readiness packet complete",
                "SCA readiness packet complete",
            ],
            "final_forbidden_claims": [
                "Pen-test passed",
                "SCA passed (unless tooling actually green)",
                "External customer login live",
                "Production auth / multi-tenant complete",
                "Production storage / customer data persistence",
                "Controlled customer pilot GO",
                "Submission-ready / final export",
                "Collaboration live",
            ],
            "final_fallback_path": (
                "Static bridge JSON frontend/src/demo/sc_customer_demo.json "
                "via /?view=sc_customer_demo"
            ),
            "next_safe_actions": list(spike.get("next_safe_actions") or []),
            "live_ingest_claimed": False,
            "collaboration_matching_claimed": False,
            "final_export_claimed": False,
        }
    )


def gate10_closeout_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "production_multi_tenant_claimed",
        "pen_test_passed_claimed",
        "sca_passed_claimed",
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "live_ingest_claimed",
        "collaboration_matching_claimed",
        "final_export_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("customer_pilot_go")
    if surface.get("production_rollout_status") == "GO":
        fails.append("production_go")
    fails.extend(
        external_pilot_auth_spike_invariant_failures(
            surface.get("external_pilot_auth_spike") or {}
        )
    )
    fails.extend(
        pen_test_sca_packet_invariant_failures(
            surface.get("pen_test_sca_packet") or {}
        )
    )
    return fails
