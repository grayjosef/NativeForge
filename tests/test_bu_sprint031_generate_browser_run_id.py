"""Sprint 031: generate browser/demo run_id."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import validate_browser_run_id
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    generate_browser_smoke_run_id,
)


def test_generate_browser_run_id() -> None:
    rid = generate_browser_smoke_run_id()
    assert validate_browser_run_id(rid)
