"""Sprint 44: validation rollup lists scoped NM/WA test files."""

from __future__ import annotations

from nativeforge.services.nm_wa_validation_rollup_service import (
    build_nm_wa_validation_rollup,
    list_nm_wa_block_test_files,
)


def test_validation_rollup_lists_scoped_tests() -> None:
    files = list_nm_wa_block_test_files()
    assert any(name.startswith("test_nm_pilot_") for name in files)
    assert any(name.startswith("test_wa_pilot_") for name in files)
    assert any(name.startswith("test_nm_wa_") for name in files)
    rollup = build_nm_wa_validation_rollup()
    assert rollup["full_suite_run"] is False
    assert rollup["scoped_test_file_count"] == len(files)
