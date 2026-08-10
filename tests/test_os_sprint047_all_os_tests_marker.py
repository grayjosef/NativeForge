"""Sprint 047: marker that operator surfacing scoped suite exists."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_validation_rollup_service import (
    list_operator_surfacing_test_files,
)


def test_os_suite_file_count() -> None:
    # includes this file once committed; count at write time may be N-1
    assert len(list_operator_surfacing_test_files()) >= 40
