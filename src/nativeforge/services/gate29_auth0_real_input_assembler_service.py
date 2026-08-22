"""Block 63 assembler: Auth0 real-input ingest surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate29_auth0_real_input_service import (
    auth0_real_input_invariant_failures,
    run_auth0_real_input_ingest,
)

SCHEMA_VERSION = "nf_gate29_auth0_real_input_assembler_v1"
DOC = "docs/operations/284_GATE29_AUTH0_REAL_INPUT_INGEST.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_auth0_real_input_demo_surface() -> dict[str, Any]:
    result = run_auth0_real_input_ingest()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 63,
            "title": "Auth0/OIDC real-input ingest",
            "docs": [DOC],
            "real_input_detector": True,
            "mode": result.get("mode"),
            "synthetic_rehearsal_artifacts_ignored": True,
            "real_owner_auth0_inputs_present": False,
            "secret_present_redacted": False,
            "live_validation_enabled": False,
            "live_validation_attempted": False,
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "controlled_pilot_auth_ready": False,
            "mode_b_executed_claimed": False,
            "missing_gates": result.get("missing_gates"),
            "no_secret_validation": True,
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Real-input detector exists; Gate 28 synthetic fixtures are ignored",
                "Auth0 OOB config is absent; live validation was not attempted",
                "login_live and production_auth remain false",
                "Exact missing gates remain visible for the owner",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Do not treat rehearsal or this prompt as Auth0 approval",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def auth0_real_input_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "controlled_pilot_auth_ready",
        "mode_b_executed_claimed",
        "real_owner_auth0_inputs_present",
        "live_validation_attempted",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if not surface.get("synthetic_rehearsal_artifacts_ignored"):
        fails.append("synthetic_not_ignored")
    fails.extend(auth0_real_input_invariant_failures(surface.get("result") or {}))
    return fails
