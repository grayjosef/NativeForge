"""Block 34 assembler: SCA execution / security remediation surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.sca_execution_runner_service import (
    run_sca_execution,
    sca_execution_invariant_failures,
)
from nativeforge.services.sca_tooling_discovery_service import (
    discover_security_tooling,
    sca_tooling_discovery_invariant_failures,
)

SCHEMA_VERSION = "nf_sca_security_loop_assembler_v1"
ROOT = Path(__file__).resolve().parents[3]
LATEST = ROOT / "artifacts" / "sca_execution" / "latest_sca_execution.json"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _load_cached_execution() -> dict[str, Any] | None:
    if not LATEST.is_file():
        return None
    try:
        return json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_sca_security_loop_demo_surface(*, run_checks: bool = False) -> dict[str, Any]:
    discovery = discover_security_tooling()
    if run_checks:
        execution = run_sca_execution(run_checks=True)
    else:
        execution = _load_cached_execution() or run_sca_execution(run_checks=False)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 34,
            "title": "SCA execution / security remediation loop",
            "tooling_discovery": discovery,
            "sca_execution": execution,
            "buyer_summary": [
                "Security tooling discovery completed without new installs",
                (
                    "SCA checks executed"
                    if execution.get("sca_run")
                    else "SCA checks blocked or not run"
                ),
                (
                    "frontend npm audit (omit=dev) clean"
                    if execution.get("npm_audit_clean")
                    else "frontend npm audit not clean or not run"
                ),
                (
                    "Full SCA passed (npm + pip-audit)"
                    if execution.get("sca_passed_claimed")
                    else "Full SCA not claimed passed — pip-audit and/or findings incomplete"
                ),
                "Pen-test remains not passed; controlled pilot remains NO_GO",
                "No uv.lock mutation; no broad dependency upgrades in this gate",
            ],
            "sca_run": bool(execution.get("sca_run")),
            "sca_passed_claimed": bool(execution.get("sca_passed_claimed")),
            "npm_audit_clean": bool(execution.get("npm_audit_clean")),
            "pip_audit_clean": bool(execution.get("pip_audit_clean")),
            "high_critical_findings": list(
                execution.get("high_critical_findings") or []
            ),
            "blocked_checks": list(execution.get("blocked_checks") or []),
            "unresolved_findings": list(execution.get("unresolved_findings") or []),
            "remediated_items": list(execution.get("remediated_items") or []),
            "pen_test_passed_claimed": False,
            "uv_lock_touched": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "human_review_required": True,
            "docs": [
                "docs/operations/190_SCA_EXECUTION_READINESS_PACKET.md",
                "docs/operations/195_SCA_EXECUTION_RESULTS.md",
            ],
        }
    )


def sca_security_loop_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "pen_test_passed_claimed",
        "uv_lock_touched",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    fails.extend(
        sca_tooling_discovery_invariant_failures(surface.get("tooling_discovery") or {})
    )
    fails.extend(sca_execution_invariant_failures(surface.get("sca_execution") or {}))
    if surface.get("sca_passed_claimed") and surface.get("high_critical_findings"):
        fails.append("passed_with_high_critical")
    return fails
