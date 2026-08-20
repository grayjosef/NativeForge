"""Demo-runtime smoke for SC Monday customer demo (static bridge / vitest lane)."""

from __future__ import annotations

import json
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sc_monday_demo_runtime_smoke_v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
ARTIFACT_DIR_REL = "artifacts/sc_monday_browser_smoke"
DEMO_ROUTE_PATH = "/?view=sc_customer_demo"
RUN_ID_PREFIX = "nf_sc_monday_browser_"

EXPECTED_SCREENS: tuple[str, ...] = (
    "sc_profiles_visible",
    "sc_opportunities_visible",
    "federal_opportunities_visible",
    "combined_workflow_visible",
    "curated_current_labels_visible",
    "no_live_ingest_claim",
    "buyer_story_visible",
    "missing_data_visible",
    "human_review_visible",
    "provenance_visible",
    "nofo_not_overclaimed",
    "proposal_not_overclaimed",
)


def generate_run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{RUN_ID_PREFIX}{ts}_{secrets.token_hex(4)}"


def run_sc_monday_demo_runtime_smoke(
    *, dry_run_skip_exec: bool = False
) -> dict[str, Any]:
    rid = generate_run_id()
    artifact_dir = REPO_ROOT / ARTIFACT_DIR_REL
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifact_dir / f"{rid}.json"

    if dry_run_skip_exec:
        screens = [
            {"screen": s, "status": "NOT_RUN", "detail": "dry_run_skip_exec"}
            for s in EXPECTED_SCREENS
        ]
        overall = "NOT_RUN"
        playwright_status = "NOT_RUN"
    else:
        # Demo-runtime = static vitest coverage of page + payload honesty.
        proc = subprocess.run(
            [
                "npm",
                "test",
                "--",
                "--run",
                "src/pages/ScCustomerDemoPage.test.tsx",
                "src/scCustomerDemoSurface.test.ts",
            ],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        (artifact_dir / f"{rid}.log").write_text(
            proc.stdout + "\n" + proc.stderr, encoding="utf-8"
        )
        ok = proc.returncode == 0
        detail = (
            "demo_runtime_static_vitest" if ok else f"vitest_exit={proc.returncode}"
        )
        screens = [
            {
                "screen": s,
                "status": "PASS" if ok else "FAIL",
                "detail": detail,
            }
            for s in EXPECTED_SCREENS
        ]
        overall = "PASS" if ok else "FAIL"
        playwright_status = "NOT_RUN"

    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": rid,
        "overall_status": overall,
        "smoke_mode": "demo_runtime_static_vitest",
        "demo_route_path": DEMO_ROUTE_PATH,
        "playwright_status": playwright_status,
        "screens": screens,
        "failures": [s["screen"] for s in screens if s["status"] == "FAIL"],
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
