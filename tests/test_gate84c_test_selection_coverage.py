"""Gate 84C — the test-selection coverage guard.

Gate 84B measured the full suite for the first time and found six deterministic
failures behind a regression number that had read "0 failed" for several gates.
None was order-dependent; the recurring scoped `-k` simply never selected them.

This pins the guard that stops that recurring.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_nativeforge_test_selection_coverage.sh"

# The six that have already rotted invisibly once.
CRITICAL_NODE_IDS = (
    "tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1",
    "tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout",
    "tests/test_sprint197_eligibility_fit_assessment_dimension_vocabulary.py"
    "::test_fit_dimensions_are_the_declared_set",
    "tests/test_sprint222_matching_readiness_readiness_evaluator.py"
    "::test_incomplete_profile_blocked_readiness",
    "tests/test_sprint4202_gate37_production_grade_hardening.py"
    "::test_busy_preview_port_blocks_serve",
    "tests/test_sprint4202_gate37_production_grade_hardening.py"
    "::test_verifier_fail_when_server_down",
)


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The script exists and is runnable
# --------------------------------------------------------------------------


def test_script_exists() -> None:
    assert SCRIPT.is_file()


def test_script_is_executable() -> None:
    """Committed with the exec bit - a Windows-side edit clears it, and a
    verifier nobody can run is a verifier that never runs."""
    assert os.access(SCRIPT, os.X_OK), "chmod +x and git update-index --chmod=+x"


def test_script_is_tracked_as_executable_in_git() -> None:
    result = subprocess.run(
        ["git", "ls-files", "-s", str(SCRIPT.relative_to(ROOT))],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if not result.stdout.strip():
        pytest.skip("script not yet tracked by git")
    assert result.stdout.split()[0] == "100755", result.stdout.strip()


def test_script_uses_strict_mode() -> None:
    assert "set -euo pipefail" in _script_text()


# --------------------------------------------------------------------------
# It guards the critical tests
# --------------------------------------------------------------------------


@pytest.mark.parametrize("node_id", CRITICAL_NODE_IDS)
def test_critical_test_is_listed_in_the_guard(node_id: str) -> None:
    assert node_id in _script_text(), f"{node_id} is not guarded"


@pytest.mark.parametrize("node_id", CRITICAL_NODE_IDS)
def test_critical_test_actually_exists(node_id: str) -> None:
    """A guarded node id that no longer exists is a silent loss of coverage."""
    path, _, name = node_id.partition("::")
    source = (ROOT / path).read_text(encoding="utf-8")
    assert f"def {name}(" in source, f"{node_id} not found - renamed or removed?"


def test_guard_fails_when_a_critical_test_is_unselected() -> None:
    """The failure path is the point of the script, so it is asserted."""
    text = _script_text()
    assert "status=FAIL not reached by the gate -k" in text
    assert "status=FAIL not collected (renamed or removed?)" in text
    assert 'exit "$FAIL"' in text
    assert "RESULT=FAIL" in text


def test_guard_reports_collected_and_selected_counts() -> None:
    text = _script_text()
    assert "check=collected" in text
    assert "check=selected_by_gate_expression" in text
    assert "check=unselected" in text


def test_guard_rejects_a_collapsed_selection() -> None:
    """A selection that matches almost nothing is a broken expression."""
    text = _script_text()
    assert "selection_breadth" in text
    assert "-lt 50" in text


def test_guard_expression_covers_the_keywords_added_by_this_gate() -> None:
    text = _script_text()
    for keyword in ("fit_dimension", "readiness", "gate37"):
        assert f"or {keyword} or" in text, keyword


# --------------------------------------------------------------------------
# End to end
# --------------------------------------------------------------------------


def test_guard_passes_end_to_end() -> None:
    """Runs the real script. Slow - it collects the suite twice."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    assert "RESULT=PASS" in result.stdout, result.stdout[-3000:]
    assert result.returncode == 0

    for node_id in CRITICAL_NODE_IDS:
        name = node_id.rsplit("::", 1)[1]
        assert f"check=critical_selected:{name} status=PASS" in result.stdout

    match = re.search(r"check=collected status=PASS total=(\d+)", result.stdout)
    assert match, result.stdout[-2000:]
    assert int(match.group(1)) > 7000, "suite collection looks truncated"
