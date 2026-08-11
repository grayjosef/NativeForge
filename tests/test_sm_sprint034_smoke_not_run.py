"""Sprint 034: honest NOT_RUN smoke result."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_runner_service import smoke_result_not_run
from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    validate_smoke_result,
)


def test_smoke_not_run() -> None:
    r = smoke_result_not_run("browser_runtime_unavailable_in_this_environment")
    assert r["overall_status"] == "NOT_RUN"
    assert r["run_id"] is None
    assert r["not_run_reason"]
    assert validate_smoke_result(r) == []
