"""Playwright E2E smoke runner for SC Monday customer demo."""

from __future__ import annotations

import json
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sc_monday_playwright_smoke_runner_v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
SPEC_REL = "e2e/sc_customer_demo.smoke.spec.ts"
ARTIFACT_DIR_REL = "artifacts/sc_monday_playwright_smoke"
DEMO_ROUTE_PATH = "/?view=sc_customer_demo"
RUN_ID_PREFIX = "nf_sc_monday_playwright_"

EXPECTED_SCREENS: tuple[str, ...] = (
    "sc_profiles_visible",
    "sc_opportunities_visible",
    "federal_opportunities_visible",
    "combined_state_federal_workflow",
    "buyer_what_nf_did",
    "buyer_attention",
    "buyer_next_actions",
    "missing_data_display",
    "human_review_display",
    "provenance_evidence_display",
    "no_live_ingest_claim",
    "no_final_eligibility_claim",
    "honest_flags_visible",
    "review_table_visible",
)


def generate_sc_playwright_run_id(*, now: datetime | None = None) -> str:
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{RUN_ID_PREFIX}{ts}_{secrets.token_hex(4)}"


def run_playwright_sc_monday_smoke(
    *,
    run_id: str | None = None,
    dry_run_skip_exec: bool = False,
) -> dict[str, Any]:
    rid = run_id or generate_sc_playwright_run_id()
    artifact_dir = REPO_ROOT / ARTIFACT_DIR_REL
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / f"{rid}.log"
    result_path = artifact_dir / f"{rid}.json"

    if dry_run_skip_exec:
        overall = "NOT_RUN"
        screens = [
            {"surface": s, "status": "NOT_RUN", "detail": "dry_run_skip_exec"}
            for s in EXPECTED_SCREENS
        ]
        exit_code = None
        detail = "dry_run_skip_exec"
    else:
        proc = subprocess.run(
            ["npx", "playwright", "test", SPEC_REL],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        log_path.write_text(proc.stdout + "\n" + proc.stderr, encoding="utf-8")
        exit_code = proc.returncode
        if exit_code == 0:
            overall = "PASS"
            detail = "playwright_spec_passed_visible_markers"
            screens = [
                {"surface": s, "status": "PASS", "detail": detail}
                for s in EXPECTED_SCREENS
            ]
        else:
            overall = "FAIL"
            detail = f"playwright_exit={exit_code}"
            screens = [
                {"surface": s, "status": "FAIL", "detail": detail}
                for s in EXPECTED_SCREENS
            ]

    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "overall_status": overall,
        "smoke_mode": "playwright_e2e",
        "demo_route_path": DEMO_ROUTE_PATH,
        "headless": True,
        "exit_code": exit_code,
        "surfaces": screens,
        "failures": [s["surface"] for s in screens if s["status"] == "FAIL"],
        "artifact_log": str(log_path.relative_to(REPO_ROOT)),
        "artifact_json": str(result_path.relative_to(REPO_ROOT)),
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
