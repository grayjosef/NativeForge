"""Pen-test / SCA readiness packet (Campaign Block 26). Not a pass claim."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_pen_test_sca_readiness_packet_v1"
ROOT = Path(__file__).resolve().parents[3]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pen_test_sca_readiness_packet(
    *,
    run_sca: bool = True,
) -> dict[str, Any]:
    sca_run = False
    sca_passed = False
    sca_notes: list[str] = []
    sca_command = None

    if run_sca:
        # Prefer already-configured non-destructive tools only
        if shutil.which("pip-audit"):
            sca_command = "pip-audit"
            try:
                proc = subprocess.run(
                    ["pip-audit", "--progress-spinner", "off"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                sca_run = True
                # Honest: only claim pass if exit 0
                sca_passed = proc.returncode == 0
                sca_notes.append(f"pip-audit exit={proc.returncode}")
                if proc.stdout:
                    sca_notes.append(proc.stdout.strip()[:500])
                if proc.stderr:
                    sca_notes.append(proc.stderr.strip()[:300])
            except Exception as exc:  # noqa: BLE001
                sca_run = True
                sca_passed = False
                sca_notes.append(f"pip-audit_error:{exc}")
        else:
            sca_notes.append(
                "pip-audit not installed; SCA readiness packet only — SCA not run"
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 26,
            "title": "Pen-test / SCA readiness packet",
            "routes_in_scope": ["/?view=sc_customer_demo", "/api/* (operator/demo)"],
            "auth_assumptions": [
                "No live customer login",
                "Demo/operator view only",
                "Org headers may exist for local isolation smoke — not production auth",
            ],
            "data_boundaries": [
                "Fixture + local/dev evidence store",
                "No production/customer data mutation",
                "Cross-org evidence reads blocked in validated adapter",
            ],
            "feature_flags": {
                "collaboration": "OFF",
                "live_ingest": "OFF",
                "final_export": "OFF",
                "customer_upload_ui": "OFF",
            },
            "collaboration_dark_state": "OFF",
            "upload_storage_state": "local_dev_validated_persistent_only",
            "slack_reporting_state": "fixture/operator — sent not claimed",
            "ai_governance": "deterministic QA gates; no unsupported proposal drafting",
            "known_no_go_claims": [
                "pen_test_passed",
                "production_storage",
                "customer_login_live",
                "controlled_customer_pilot_GO",
                "production_rollout_GO",
            ],
            "dependency_sca_command_recommendations": [
                "pip-audit (if installed)",
                "npm audit --omit=dev (frontend; review manually)",
                "Do not install new SCA tools without approval",
            ],
            "secrets_env_handling": [
                "No secrets in commits",
                ".env local only",
                "AIRTABLE_TOKEN for log_run only",
            ],
            "test_accounts_data_needs": [
                "Fixture SC cohort orgs only",
                "No real customer accounts",
            ],
            "out_of_scope": [
                "Production object storage",
                "External IdP production cutover",
                "Live Slack delivery validation",
            ],
            "pen_test_readiness_complete": True,
            "pen_test_passed_claimed": False,
            "sca_readiness_complete": True,
            "sca_run": bool(sca_run),
            "sca_command": sca_command,
            "sca_passed_claimed": bool(sca_passed),
            "sca_notes": sca_notes,
            "buyer_summary": [
                "Pen-test readiness packet complete — pen-test not passed",
                "SCA readiness packet complete — pass only if tooling ran green",
                "External customer login remains not live",
            ],
        }
    )


def pen_test_sca_packet_invariant_failures(packet: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if packet.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed_claimed")
    # Only allow sca_passed_claimed when sca_run and honestly green
    if packet.get("sca_passed_claimed") is True and not packet.get("sca_run"):
        fails.append("sca_passed_without_run")
    return fails
