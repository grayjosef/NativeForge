"""SCA execution runner — non-destructive checks only (Block 34)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from nativeforge.services.sca_tooling_discovery_service import discover_security_tooling

SCHEMA_VERSION = "nf_sca_execution_runner_v1"
ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = ROOT / "artifacts" / "sca_execution"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _summarize_npm_audit(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("metadata") or {}
    vulns = meta.get("vulnerabilities") or {}
    return {
        "info": int(vulns.get("info") or 0),
        "low": int(vulns.get("low") or 0),
        "moderate": int(vulns.get("moderate") or 0),
        "high": int(vulns.get("high") or 0),
        "critical": int(vulns.get("critical") or 0),
        "total": int(vulns.get("total") or 0),
    }


def run_sca_execution(*, run_checks: bool = True) -> dict[str, Any]:
    discovery = discover_security_tooling()
    checks: list[dict[str, Any]] = []
    high_critical: list[str] = []
    blocked: list[str] = []
    remediated: list[str] = []
    unresolved: list[str] = []

    sca_run = False
    any_fail = False

    if not run_checks:
        blocked.append("run_checks_false")
    else:
        # npm audit (frontend production deps)
        if discovery["tools_available"].get("npm") and discovery.get(
            "frontend_dir_exists"
        ):
            try:
                proc = subprocess.run(
                    ["npm", "audit", "--omit=dev", "--json"],
                    cwd=str(ROOT / "frontend"),
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                sca_run = True
                parsed: dict[str, Any] = {}
                try:
                    parsed = json.loads(proc.stdout or "{}")
                except json.JSONDecodeError:
                    parsed = {
                        "parse_error": True,
                        "stdout_tail": (proc.stdout or "")[-500],
                    }
                summary = (
                    _summarize_npm_audit(parsed)
                    if not parsed.get("parse_error")
                    else {}
                )
                high = int(summary.get("high") or 0)
                critical = int(summary.get("critical") or 0)
                if high or critical:
                    any_fail = True
                    high_critical.append(f"npm_audit high={high} critical={critical}")
                    unresolved.append(
                        "frontend npm audit high/critical — review before dependency upgrades"
                    )
                # npm audit exits non-zero when vulns found — not automatically "passed"
                checks.append(
                    {
                        "command": "npm audit --omit=dev --json",
                        "cwd": "frontend",
                        "exit_code": proc.returncode,
                        "summary": summary,
                        "status": "findings"
                        if (high or critical or proc.returncode != 0)
                        else "clean",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                sca_run = True
                any_fail = True
                blocked.append(f"npm_audit_error:{exc}")
                checks.append(
                    {
                        "command": "npm audit --omit=dev --json",
                        "exit_code": -1,
                        "status": "error",
                        "error": str(exc),
                    }
                )
        else:
            blocked.append("npm_unavailable")

        # pip-audit if present
        if discovery["tools_available"].get("pip_audit"):
            try:
                proc = subprocess.run(
                    ["pip-audit", "--progress-spinner", "off"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                sca_run = True
                if proc.returncode != 0:
                    any_fail = True
                    high_critical.append(f"pip-audit exit={proc.returncode}")
                    unresolved.append("pip-audit reported findings or failed")
                checks.append(
                    {
                        "command": "pip-audit --progress-spinner off",
                        "exit_code": proc.returncode,
                        "status": "clean" if proc.returncode == 0 else "findings",
                        "stdout_tail": (proc.stdout or "")[-800],
                        "stderr_tail": (proc.stderr or "")[-400],
                    }
                )
            except Exception as exc:  # noqa: BLE001
                sca_run = True
                any_fail = True
                blocked.append(f"pip_audit_error:{exc}")
        else:
            blocked.append("pip-audit_not_installed")

        for name in ("bandit", "safety", "gitleaks"):
            if not discovery["tools_available"].get(name):
                blocked.append(f"{name}_not_installed")

    npm_clean = any(
        c.get("command", "").startswith("npm audit") and c.get("status") == "clean"
        for c in checks
    )
    pip_audit_clean = any(
        c.get("command", "").startswith("pip-audit") and c.get("status") == "clean"
        for c in checks
    )
    # Full SCA pass requires both frontend npm audit and Python pip-audit clean.
    # Partial success is recorded honestly without a full pass claim.
    if any(c.get("status") == "findings" for c in checks):
        any_fail = True
    sca_passed_claimed = bool(
        sca_run and not any_fail and not high_critical and npm_clean and pip_audit_clean
    )
    if "pip-audit_not_installed" in blocked:
        unresolved.append(
            "pip-audit not installed — Python dependency SCA incomplete; "
            "do not claim full SCA passed"
        )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "discovery": discovery,
            "sca_run": sca_run,
            "checks_run": checks,
            "npm_audit_clean": npm_clean,
            "pip_audit_clean": pip_audit_clean,
            "sca_passed_claimed": sca_passed_claimed,
            "high_critical_findings": high_critical,
            "blocked_checks": blocked,
            "remediated_items": remediated,
            "unresolved_findings": unresolved,
            "pen_test_passed_claimed": False,
            "uv_lock_touched": False,
            "dependency_upgrades_applied": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "human_review_required": True,
        }
    )
    path = ARTIFACT_DIR / "latest_sca_execution.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result


def sca_execution_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed_claimed")
    if report.get("uv_lock_touched") is True:
        fails.append("uv_lock_touched")
    if report.get("dependency_upgrades_applied") is True:
        fails.append("dependency_upgrades_applied")
    if report.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if report.get("sca_passed_claimed") is True and not report.get("sca_run"):
        fails.append("passed_without_run")
    if report.get("sca_passed_claimed") is True and report.get(
        "high_critical_findings"
    ):
        fails.append("passed_with_high_critical")
    return fails
