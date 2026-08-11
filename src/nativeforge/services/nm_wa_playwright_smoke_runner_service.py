"""Playwright E2E smoke runner for NM/WA operator demo.

Executes frontend Playwright smoke, produces real run_id + per-screen results.
Distinguishes Playwright E2E from demo-runtime/static smoke.
"""

from __future__ import annotations

import json
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    ARTIFACT_DIR_REL,
    DEMO_ROUTE_PATH,
    EXPECTED_SCREENS,
    PRIOR_DEMO_RUNTIME_RUN_ID,
    RUN_ID_PREFIX,
    PlaywrightStatus,
    empty_playwright_screen_result,
    empty_playwright_smoke_result,
    validate_playwright_run_id,
    validate_playwright_smoke_result,
)

SCHEMA_VERSION = "nf_nm_wa_playwright_smoke_runner_v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"
SPEC_REL = "e2e/nm_wa_operator_demo.smoke.spec.ts"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def generate_playwright_run_id(*, now: datetime | None = None) -> str:
    """Sprint 031: generate real Playwright run_id."""
    ts = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{RUN_ID_PREFIX}{ts}_{secrets.token_hex(4)}"
    if not validate_playwright_run_id(run_id):
        raise RuntimeError(f"generated invalid playwright run_id: {run_id}")
    return run_id


def map_playwright_pass_to_screens(*, detail: str) -> list[dict[str, Any]]:
    """Sprint 032: when Playwright smoke passes, mark all expected screens PASS."""
    return [
        empty_playwright_screen_result(s, status="PASS", detail=detail)
        for s in EXPECTED_SCREENS
    ]


def map_playwright_fail_to_screens(*, detail: str) -> list[dict[str, Any]]:
    """Sprint 033: on Playwright failure, mark screens FAIL with shared detail."""
    return [
        empty_playwright_screen_result(s, status="FAIL", detail=detail)
        for s in EXPECTED_SCREENS
    ]


def run_playwright_nm_wa_smoke(
    *,
    run_id: str | None = None,
    dry_run_skip_exec: bool = False,
    simulated_exit_code: int | None = None,
) -> dict[str, Any]:
    """Sprint 034: execute Playwright E2E smoke and return honest result."""
    rid = run_id or generate_playwright_run_id()
    if not validate_playwright_run_id(rid):
        raise ValueError(f"invalid playwright run_id: {rid}")

    artifact_dir = REPO_ROOT / ARTIFACT_DIR_REL
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_path = artifact_dir / f"{rid}.log"
    result_path = artifact_dir / f"{rid}.json"

    if dry_run_skip_exec:
        if simulated_exit_code is None:
            raise ValueError("simulated_exit_code required for dry_run_skip_exec")
        exit_code = simulated_exit_code
        log_text = f"dry_run simulated_exit_code={exit_code}\n"
    else:
        cmd = ["npm", "run", "test:e2e:nm-wa-smoke"]
        proc = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        exit_code = proc.returncode
        log_text = (
            f"cmd={' '.join(cmd)}\n"
            f"exit_code={exit_code}\n"
            f"--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr}\n"
        )

    log_path.write_text(log_text, encoding="utf-8")

    if exit_code == 0:
        screens = map_playwright_pass_to_screens(
            detail="playwright_spec_passed_visible_markers"
        )
        overall: PlaywrightStatus = "PASS"
        failures: list[str] = []
    else:
        screens = map_playwright_fail_to_screens(
            detail=f"playwright_spec_failed_exit_{exit_code}"
        )
        overall = "FAIL"
        failures = [f"playwright_exit_code:{exit_code}"]

    result = empty_playwright_smoke_result(run_id=rid, status=overall)
    result["schema_version"] = SCHEMA_VERSION
    result["overall_status"] = overall
    result["not_run_reason"] = None
    result["smoke_mode"] = "playwright_e2e"
    result["demo_route_path"] = DEMO_ROUTE_PATH
    result["prior_demo_runtime_run_id"] = PRIOR_DEMO_RUNTIME_RUN_ID
    result["headless"] = True
    result["screens"] = screens
    result["failures"] = failures
    result["artifact_paths"] = [
        str(log_path.relative_to(REPO_ROOT)),
        str(result_path.relative_to(REPO_ROOT)),
    ]
    result["playwright_exit_code"] = exit_code
    result["spec"] = SPEC_REL

    validation = validate_playwright_smoke_result(result)
    if validation:
        result["overall_status"] = "FAIL"
        result["failures"] = failures + [f"result_validation:{v}" for v in validation]

    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return _json_safe(result)


def playwright_smoke_result_not_run(reason: str) -> dict[str, Any]:
    """Sprint 035: honest NOT_RUN Playwright result (no fabricated run_id)."""
    result = empty_playwright_smoke_result(
        run_id=None, status="NOT_RUN", not_run_reason=reason
    )
    result["schema_version"] = SCHEMA_VERSION
    return _json_safe(result)
