"""Repo-local code/test inventory (Campaign Block 17). No secrets; read-only."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_code_health_inventory_v1"

# Paths relative to repo root — never walk secrets dirs
_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        "artifacts",
        "htmlcov",
        ".tox",
    }
)


@dataclass(frozen=True)
class CategoryStats:
    file_count: int
    line_count: int


def _should_skip(path: Path) -> bool:
    return any(part in _SKIP_DIR_NAMES for part in path.parts)


def _count_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def _collect(root: Path, *, patterns: tuple[str, ...]) -> CategoryStats:
    files: list[Path] = []
    for pattern in patterns:
        for p in root.rglob(pattern):
            if p.is_file() and not _should_skip(p.relative_to(root)):
                files.append(p)
    # de-dupe
    uniq = sorted(set(files))
    lines = sum(_count_lines(p) for p in uniq)
    return CategoryStats(file_count=len(uniq), line_count=lines)


def build_code_health_inventory(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path.cwd()).resolve()
    py_src = _collect(root / "src", patterns=("*.py",))
    py_tests = _collect(root / "tests", patterns=("*.py",))
    fe_src = _collect(
        root / "frontend" / "src",
        patterns=("*.ts", "*.tsx", "*.css"),
    )
    fe_tests = CategoryStats(
        file_count=0,
        line_count=0,
    )
    # Frontend tests: *.test.ts(x) + e2e
    fe_unit = _collect(
        root / "frontend" / "src",
        patterns=("*.test.ts", "*.test.tsx"),
    )
    fe_e2e = _collect(root / "frontend" / "e2e", patterns=("*.ts",))
    fe_tests = CategoryStats(
        file_count=fe_unit.file_count + fe_e2e.file_count,
        line_count=fe_unit.line_count + fe_e2e.line_count,
    )
    services = _collect(root / "src" / "nativeforge" / "services", patterns=("*.py",))
    pages = _collect(root / "frontend" / "src" / "pages", patterns=("*.tsx",))
    smoke_scripts = _collect(root / "scripts", patterns=("*smoke*.sh",))
    campaign_smokes = _collect(
        root / "scripts", patterns=("campaign_block*_smoke_verify.sh",)
    )
    playwright_specs = _collect(root / "frontend" / "e2e", patterns=("*.spec.ts",))
    ops_docs = _collect(root / "docs" / "operations", patterns=("*.md",))

    src_loc = py_src.line_count + fe_src.line_count
    test_loc = py_tests.line_count + fe_tests.line_count
    ratio = round(test_loc / src_loc, 4) if src_loc else 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_block": 17,
        "repo_root": str(root),
        "python_source": asdict(py_src),
        "python_tests": asdict(py_tests),
        "frontend_source": asdict(fe_src),
        "frontend_tests": asdict(fe_tests),
        "frontend_unit_tests": asdict(fe_unit),
        "frontend_e2e_specs": asdict(fe_e2e),
        "service_modules": asdict(services),
        "frontend_pages": asdict(pages),
        "smoke_scripts": asdict(smoke_scripts),
        "campaign_block_smoke_scripts": asdict(campaign_smokes),
        "playwright_specs": asdict(playwright_specs),
        "operations_docs": asdict(ops_docs),
        "totals": {
            "source_files": py_src.file_count + fe_src.file_count,
            "test_files": py_tests.file_count + fe_tests.file_count,
            "source_loc": src_loc,
            "test_loc": test_loc,
            "approximate_test_to_code_ratio": ratio,
        },
        "notes": [
            "Inventory is approximate LOC (newline-based); not coverage %.",
            "artifacts/, .venv/, node_modules/ excluded.",
            "Secrets and env vars are never included.",
            "Full-suite green is NOT claimed by this inventory.",
            "Pen-test pass is NOT claimed by this inventory.",
        ],
        "full_suite_run": False,
        "full_suite_passed": False,
        "pen_test_passed_claimed": False,
    }


def code_health_inventory_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("pen_test_passed_claimed") is True:
        fails.append("pen_test_passed_claimed")
    totals = report.get("totals") or {}
    if (totals.get("source_files") or 0) < 1:
        fails.append("no_source_files")
    if (totals.get("test_files") or 0) < 1:
        fails.append("no_test_files")
    # Never claim full suite green via inventory alone
    if report.get("full_suite_passed") is True and report.get("full_suite_run") is not True:
        fails.append("full_suite_passed_without_run")
    return fails


def write_code_health_inventory_report(
    report: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = report if report is not None else build_code_health_inventory()
    out = path or Path("docs/operations/149_CODE_HEALTH_TEST_POSTURE_REPORT.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    totals = doc.get("totals") or {}
    lines = [
        "# Code Health / Test Posture Report (Gate 06 / Block 17)",
        "",
        f"Schema: `{doc.get('schema_version')}`",
        "",
        "## Totals",
        "",
        f"- Source files: **{totals.get('source_files')}**",
        f"- Test files: **{totals.get('test_files')}**",
        f"- Source LOC (approx): **{totals.get('source_loc')}**",
        f"- Test LOC (approx): **{totals.get('test_loc')}**",
        f"- Approximate test-to-code ratio: **{totals.get('approximate_test_to_code_ratio')}**",
        "",
        "## Breakdown",
        "",
        f"- Python source: {doc.get('python_source')}",
        f"- Python tests: {doc.get('python_tests')}",
        f"- Frontend source: {doc.get('frontend_source')}",
        f"- Frontend tests: {doc.get('frontend_tests')}",
        f"- Service modules: {doc.get('service_modules')}",
        f"- Frontend pages: {doc.get('frontend_pages')}",
        f"- Smoke scripts: {doc.get('smoke_scripts')}",
        f"- Campaign block smokes: {doc.get('campaign_block_smoke_scripts')}",
        f"- Playwright specs: {doc.get('playwright_specs')}",
        "",
        "## Honesty flags",
        "",
        f"- full_suite_run: `{doc.get('full_suite_run')}`",
        f"- full_suite_passed: `{doc.get('full_suite_passed')}`",
        f"- pen_test_passed_claimed: `{doc.get('pen_test_passed_claimed')}`",
        "",
        "## Notes",
        "",
    ]
    for n in doc.get("notes") or []:
        lines.append(f"- {n}")
    lines.append("")
    lines.append("## Machine-readable JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(doc, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
