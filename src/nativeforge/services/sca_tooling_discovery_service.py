"""SCA / security tooling discovery (Block 34)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_sca_tooling_discovery_v1"
ROOT = Path(__file__).resolve().parents[3]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def discover_security_tooling() -> dict[str, Any]:
    frontend = ROOT / "frontend"
    tools = {
        "npm": shutil.which("npm") is not None,
        "pip_audit": shutil.which("pip-audit") is not None,
        "bandit": shutil.which("bandit") is not None,
        "safety": shutil.which("safety") is not None,
        "gitleaks": shutil.which("gitleaks") is not None,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "repo_root": str(ROOT),
            "frontend_dir_exists": frontend.is_dir(),
            "frontend_package_lock_exists": (frontend / "package-lock.json").is_file(),
            "frontend_package_json_exists": (frontend / "package.json").is_file(),
            "pyproject_exists": (ROOT / "pyproject.toml").is_file(),
            "uv_lock_exists": (ROOT / "uv.lock").is_file(),
            "gate13_sca_packet": "docs/operations/190_SCA_EXECUTION_READINESS_PACKET.md",
            "tools_available": tools,
            "safe_commands_recommended": [
                "cd frontend && npm audit --omit=dev --json",
                "pip-audit --progress-spinner off  # if installed",
            ],
            "install_new_tools": False,
            "dependency_mutation": False,
            "notes": [
                "Discovery only — no dependency installs",
                "pip-audit not required to be present; report blocked if missing",
            ],
        }
    )


def sca_tooling_discovery_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("install_new_tools") is True:
        fails.append("install_new_tools")
    if report.get("dependency_mutation") is True:
        fails.append("dependency_mutation")
    if not report.get("frontend_dir_exists"):
        fails.append("frontend_missing")
    return fails
