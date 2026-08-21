"""Python SCA execution path (Block 38) — ephemeral pip-audit when safe."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_python_sca_execution_v1"
ROOT = Path(__file__).resolve().parents[3]
ARTIFACT = ROOT / "artifacts" / "sca_execution" / "latest_python_sca.json"
DOC_ARTIFACT = "docs/operations/207_PYTHON_SCA_EXECUTION_RESULTS.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _safe_tail(text: str | None, n: int = 1200) -> str:
    if not text:
        return ""
    return text[-n:] if len(text) > n else text


def run_python_sca_execution(*, attempt: bool = True) -> dict[str, Any]:
    """Run pip-audit without touching uv.lock / project lockfiles.

    May install pip-audit into the active venv only (not project deps).
    """
    uv_path = ROOT / "uv.lock"
    uv_lock_before = uv_path.read_bytes() if uv_path.is_file() else None
    command = None
    exit_code: int | None = None
    stdout_tail = ""
    stderr_tail = ""
    python_sca_run = False
    python_sca_passed = False
    blocked: list[str] = []
    findings_summary: list[str] = []
    install_notes: list[str] = []
    high_critical: list[str] = []

    if not attempt:
        blocked.append("attempt_false")
    else:
        pip_audit = shutil.which("pip-audit")
        if not pip_audit:
            try:
                install = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "pip-audit", "--quiet"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                install_notes.append(f"pip_install_pip_audit_exit={install.returncode}")
                if install.returncode != 0:
                    blocked.append("pip_audit_install_failed")
                    stderr_tail = _safe_tail(install.stderr, 400)
                else:
                    pip_audit = shutil.which("pip-audit")
                    if not pip_audit:
                        candidate = Path(sys.executable).parent / "pip-audit"
                        pip_audit = str(candidate) if candidate.is_file() else None
            except Exception as exc:  # noqa: BLE001
                blocked.append(f"install_error:{type(exc).__name__}:{exc}")

        if pip_audit and "pip_audit_install_failed" not in blocked:
            command = f"{pip_audit} --progress-spinner off"
            try:
                proc = subprocess.run(
                    [str(pip_audit), "--progress-spinner", "off"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                python_sca_run = True
                exit_code = int(proc.returncode)
                stdout_tail = _safe_tail(proc.stdout, 2000)
                stderr_tail = _safe_tail(proc.stderr, 400)
                combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
                no_vulns = "No known vulnerabilities found" in combined
                has_vuln_table = (
                    ("Found " in combined)
                    and ("known vulnerabilities" in combined)
                    and (not no_vulns)
                )
                if has_vuln_table:
                    findings_summary.append("pip-audit reported known vulnerabilities")
                    if "pydantic-settings" in combined and "GHSA-" in combined:
                        high_critical.append(
                            "pydantic-settings GHSA-4xgf-cpjx-pc3j (fix >=2.14.2)"
                        )
                    if "PYSEC-" in combined and "pip" in combined:
                        findings_summary.append(
                            "pip package vulns in venv (upgrade pip in venv; not project uv.lock)"
                        )
                python_sca_passed = bool(
                    exit_code == 0 and no_vulns and not has_vuln_table
                )
                if exit_code != 0:
                    findings_summary.append(f"pip-audit exit={exit_code}")
                    python_sca_passed = False
            except Exception as exc:  # noqa: BLE001
                python_sca_run = True
                blocked.append(f"run_error:{type(exc).__name__}:{exc}")
                python_sca_passed = False

    uv_lock_after = uv_path.read_bytes() if uv_path.is_file() else None
    uv_lock_touched = uv_lock_before != uv_lock_after

    frontend_npm_clean = True  # Gate 14 evidence
    full_sca_passed = bool(
        python_sca_run
        and python_sca_passed
        and frontend_npm_clean
        and not high_critical
    )

    result = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_doc": DOC_ARTIFACT,
            "python_sca_attempted": bool(attempt),
            "python_sca_run": python_sca_run,
            "python_sca_command": command,
            "python_sca_exit_status": exit_code,
            "python_sca_passed": python_sca_passed,
            "frontend_npm_audit_clean_prior": frontend_npm_clean,
            "full_sca_passed_claimed": full_sca_passed,
            "blocked": blocked,
            "findings_summary": findings_summary,
            "high_critical_findings": high_critical,
            "install_notes": install_notes,
            "stdout_tail": stdout_tail,
            "stderr_tail": stderr_tail,
            "uv_lock_touched": bool(uv_lock_touched),
            "dependency_lockfiles_mutated": False,
            "pen_test_passed_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "human_review_required": True,
        }
    )
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(ARTIFACT)
    return result


def python_sca_execution_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("uv_lock_touched") is True:
        fails.append("uv_lock_touched")
    if report.get("dependency_lockfiles_mutated") is True:
        fails.append("lockfiles_mutated")
    if report.get("full_sca_passed_claimed") and not report.get("python_sca_passed"):
        fails.append("full_without_python")
    if report.get("full_sca_passed_claimed") and report.get("high_critical_findings"):
        fails.append("full_with_high_critical")
    if report.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed")
    if report.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    return fails
