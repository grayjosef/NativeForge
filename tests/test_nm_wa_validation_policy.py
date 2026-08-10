"""Sprint 45: validation rollup offline / scoped-ruff policy flags."""

from __future__ import annotations

from nativeforge.services.nm_wa_validation_rollup_service import (
    build_nm_wa_validation_rollup,
)


def test_validation_policy_flags() -> None:
    rollup = build_nm_wa_validation_rollup()
    assert rollup["offline_only"] is True
    assert rollup["scoped_ruff_policy"] == "touched_python_files_only"
    assert rollup["full_suite_count"] is None
