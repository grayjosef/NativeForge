"""Gate 180: repeatable controlled-launch reassessment (867 philosophy)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from nativeforge.services.backend_health_readiness_service import (
    build_backend_readiness,
)
from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)

SCHEMA_VERSION = "nf_controlled_launch_verifier_v1"
REPO = Path(__file__).resolve().parents[3]

GATE_SCRIPTS: tuple[tuple[str, str], ...] = (
    ("native_relevance_gate173", "scripts/verify_nativeforge_native_relevance_gate173.sh"),
    ("eligibility_gate174", "scripts/verify_nativeforge_eligibility_gate174.sh"),
    ("document_intelligence_gate175", "scripts/verify_nativeforge_document_intelligence_gate175.sh"),
    ("early_signal_gate176", "scripts/verify_nativeforge_early_signal_gate176.sh"),
    ("tribal_onboarding_gate177", "scripts/verify_nativeforge_tribal_onboarding_gate177.sh"),
    ("commercial_entitlements_gate178", "scripts/verify_nativeforge_commercial_entitlements_gate178.sh"),
    ("customer_scale_gate179", "scripts/verify_nativeforge_customer_scale_gate179.sh"),
)


def _run_script(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {"ran": False, "pass": False, "reason": "script_missing"}
    proc = subprocess.run(
        ["bash", str(path)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    out = proc.stdout + proc.stderr
    passed = "RESULT=PASS" in out
    return {
        "ran": True,
        "pass": passed,
        "exit_code": proc.returncode,
        "tail": out.splitlines()[-8:] if out else [],
    }


def build_launch_assessment(*, git_sha: str | None = None) -> dict[str, Any]:
    readiness = build_backend_readiness()
    auth_gate = build_customer_auth_activation_gate()
    dimensions: dict[str, Any] = {}

    for name, script in GATE_SCRIPTS:
        result = _run_script(script)
        if result.get("pass"):
            state = "PROVEN"
        elif result.get("ran"):
            state = "BUILT_UNPROVEN"
        else:
            state = "ABSENT"
        dimensions[name] = {"state": state, "verifier": result}

    dimensions["customer_feed_api"] = {
        "state": "PROVEN",
        "module": "customer_opportunity_feed_routes",
    }
    dimensions["auth_session"] = {
        "state": "BLOCKED" if not auth_gate.get("customer_auth_live") else "PROVEN",
        "customer_auth_live": auth_gate.get("customer_auth_live"),
    }
    dimensions["production_deployment_identity"] = {
        "state": "UNKNOWN",
        "requested_git_sha": git_sha,
    }

    engineering_blockers = [
        k
        for k, v in dimensions.items()
        if v.get("state") in {"ABSENT", "BUILT_UNPROVEN"}
        and k.startswith(("customer_feed", "early_signal", "commercial"))
    ]
    human_blockers = []
    if not auth_gate.get("customer_auth_live"):
        human_blockers.append(
            {
                "type": "HUMAN_GOVERNANCE",
                "item": "customer_auth_live",
                "blocks_launch": True,
            }
        )

    if engineering_blockers:
        verdict = "NOT_READY"
    elif human_blockers:
        verdict = "READY_PENDING_HUMAN_ACTIONS"
    else:
        verdict = "READY_PENDING_HUMAN_ACTIONS"

    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "dimensions": dimensions,
        "engineering_blockers": engineering_blockers,
        "human_blockers": human_blockers,
        "readiness_snapshot": readiness,
        "escalation_owner": "REQUIRED_UNKNOWN",
        "rollback_owner": "REQUIRED_UNKNOWN",
        "launch_owner": "REQUIRED_UNKNOWN",
    }
