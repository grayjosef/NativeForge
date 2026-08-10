"""NM/WA block validation rollup — scoped test inventory (no full suite claim)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_nm_wa_validation_rollup_v1"

_TEST_GLOBS = (
    "test_nm_pilot_*.py",
    "test_wa_pilot_*.py",
    "test_nm_wa_*.py",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def list_nm_wa_block_test_files() -> list[str]:
    tests_dir = Path(__file__).resolve().parents[3] / "tests"
    names: list[str] = []
    for pattern in _TEST_GLOBS:
        names.extend(sorted(p.name for p in tests_dir.glob(pattern)))
    return sorted(set(names))


def build_nm_wa_validation_rollup() -> dict[str, Any]:
    """Sprint 44: validation rollup of NM/WA block test files."""
    files = list_nm_wa_block_test_files()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scoped_test_file_count": len(files),
            "scoped_test_files": files,
            "full_suite_run": False,
            "full_suite_count": None,
            "repo_wide_ruff": "NOT_RUN_BY_DESIGN_legacy_backlog",
            "scoped_ruff_policy": "touched_python_files_only",
            "offline_only": True,
        }
    )
