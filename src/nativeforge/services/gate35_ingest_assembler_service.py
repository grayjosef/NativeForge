"""Gate 35 assemblers (Blocks 83–86)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate35_auth0_ingest_service import (
    auth0_ingest_invariant_failures,
    run_auth0_real_ingest,
)
from nativeforge.services.gate35_pentest_ingest_service import (
    pentest_ingest_invariant_failures,
    run_pentest_ingest,
)
from nativeforge.services.gate35_pilot_resolver_service import (
    pilot_resolver_invariant_failures,
    run_gate35_bundle,
)
from nativeforge.services.gate35_storage_ingest_service import (
    run_storage_real_ingest,
    storage_ingest_invariant_failures,
)

SCHEMA_AUTH = "nf_gate35_auth_assembler_v1"
SCHEMA_STOR = "nf_gate35_stor_assembler_v1"
SCHEMA_PT = "nf_gate35_pt_assembler_v1"
SCHEMA_PILOT = "nf_gate35_pilot_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_ingest_demo_surface() -> dict[str, Any]:
    result = run_auth0_real_ingest()
    return _json_safe(
        {
            "schema_version": SCHEMA_AUTH,
            "campaign_block": 83,
            "title": "Auth0/OIDC real-input ingest",
            "real_artifacts_present": False,
            "login_live_claim": False,
            "production_auth_claim": False,
            "live_validation_attempted": False,
            "next_owner_action": "Provide OIDC issuer/client/secret/callback OOB",
            "buyer_summary": [
                "Owner Auth0 artifacts absent; Mode A blocked_owner_input",
                "login_live and production_auth remain false",
            ],
            "next_safe_actions": ["Do not claim login live"],
            "result": result,
        }
    )


def auth0_ingest_demo_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("login_live_claim") is True:
        fails.append("login_live")
    fails.extend(auth0_ingest_invariant_failures(surface.get("result") or {}))
    return fails


def build_storage_ingest_demo_surface() -> dict[str, Any]:
    result = run_storage_real_ingest()
    return _json_safe(
        {
            "schema_version": SCHEMA_STOR,
            "campaign_block": 84,
            "title": "Storage real-input ingest",
            "approval_artifact_present": False,
            "production_storage_claim": False,
            "customer_persistence_claim": False,
            "next_owner_action": "Provide storage approval token + OOB config",
            "buyer_summary": [
                "Storage approval/config absent; production storage false",
                "Customer persistence remains false",
            ],
            "next_safe_actions": ["Do not claim production storage"],
            "result": result,
        }
    )


def storage_ingest_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("production_storage_claim") is True:
        fails.append("prod_storage")
    fails.extend(storage_ingest_invariant_failures(surface.get("result") or {}))
    return fails


def build_pentest_ingest_demo_surface() -> dict[str, Any]:
    result = run_pentest_ingest()
    return _json_safe(
        {
            "schema_version": SCHEMA_PT,
            "campaign_block": 85,
            "title": "Pen-test evidence ingest",
            "report_reference_present": False,
            "pen_test_pass_claim": False,
            "controlled_pilot_security_ready": False,
            "production_rollout_security_ready": False,
            "next_owner_action": "Vendor: pen-test report, scope, findings, pass evidence",
            "buyer_summary": [
                "Pen-test report absent; blocked_external_vendor",
                "Pen-test pass remains false; rollout security false",
            ],
            "next_safe_actions": ["Do not claim pen-test passed"],
            "result": result,
        }
    )


def pentest_ingest_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("pen_test_pass_claim") is True:
        fails.append("pentest_pass")
    fails.extend(pentest_ingest_invariant_failures(surface.get("result") or {}))
    return fails


def build_pilot_resolver_demo_surface() -> dict[str, Any]:
    bundle = run_gate35_bundle()
    result = bundle["pilot"]
    return _json_safe(
        {
            "schema_version": SCHEMA_PILOT,
            "campaign_block": 86,
            "title": "Post-input pilot resolver",
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "limited_external_validation_status": result.get(
                "limited_external_validation_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "allowed_claims": result.get("allowed_claims"),
            "forbidden_claims": result.get("forbidden_claims"),
            "remaining_blockers": result.get("remaining_blockers"),
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Resolver rerun: CONDITIONAL_INTERNAL_ONLY",
                "No owner/vendor artifacts; no claim unlock",
            ],
            "next_safe_actions": result.get("remaining_blockers"),
            "result": result,
            "bundle": bundle,
        }
    )


def pilot_resolver_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(pilot_resolver_invariant_failures(surface.get("result") or {}))
    return fails
