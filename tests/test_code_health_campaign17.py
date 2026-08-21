"""Tests: Gate 06 Block 17 code health / no-fail invariants."""

from __future__ import annotations

from pathlib import Path

from nativeforge.services.code_health_inventory_service import (
    build_code_health_inventory,
    code_health_inventory_invariant_failures,
)
from nativeforge.services.critical_path_coverage_map_service import (
    build_critical_path_coverage_map,
    critical_path_coverage_map_invariant_failures,
)
from nativeforge.services.no_fail_invariant_suite_service import (
    run_no_fail_invariant_suite,
)


def test_code_health_inventory_measures_ratio(tmp_path: Path) -> None:
    # Use real repo root for meaningful counts
    report = build_code_health_inventory(Path.cwd())
    assert code_health_inventory_invariant_failures(report) == []
    totals = report["totals"]
    assert totals["source_files"] > 50
    assert totals["test_files"] > 50
    assert totals["source_loc"] > 1000
    assert totals["test_loc"] > 1000
    assert totals["approximate_test_to_code_ratio"] > 0
    assert report["full_suite_passed"] is False
    assert report["pen_test_passed_claimed"] is False


def test_critical_path_coverage_map() -> None:
    report = build_critical_path_coverage_map()
    assert critical_path_coverage_map_invariant_failures(report) == []
    assert report["path_count"] >= 15
    assert "evidence_binder" in report["weakest_areas"]
    assert report["pen_test_ready_claimed"] is False


def test_no_fail_invariant_suite() -> None:
    result = run_no_fail_invariant_suite()
    assert result["overall_status"] == "PASS"
    assert result["fails"] == []
    assert "no_final_export_claim" in result["invariants_proven"]
    assert result["pen_test_passed_claimed"] is False
