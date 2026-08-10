"""Operator surfacing validation rollup — scoped test inventory only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_operator_surfacing_validation_rollup_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def list_operator_surfacing_test_files() -> list[str]:
    tests_dir = Path(__file__).resolve().parents[3] / "tests"
    return sorted(p.name for p in tests_dir.glob("test_os_sprint*.py"))


def build_operator_surfacing_validation_rollup() -> dict[str, Any]:
    files = list_operator_surfacing_test_files()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scoped_test_file_count": len(files),
            "scoped_test_files": files,
            "full_suite_run": False,
            "full_suite_count": None,
            "repo_wide_ruff": "NOT_RUN_BY_DESIGN_legacy_backlog",
            "offline_only": True,
        }
    )
