"""Sprint 046: operator surfacing validation rollup inventory."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_validation_rollup_service import (
    build_operator_surfacing_validation_rollup,
)


def test_validation_rollup_lists_os_tests() -> None:
    r = build_operator_surfacing_validation_rollup()
    assert r["scoped_test_file_count"] >= 40
    assert r["full_suite_run"] is False
    assert any(n.startswith("test_os_sprint") for n in r["scoped_test_files"])
