"""Sprint 031: generate real smoke run_id."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_runner_service import generate_smoke_run_id
from nativeforge.services.nm_wa_smoke_validation_contract_service import validate_run_id


def test_generate_smoke_run_id() -> None:
    rid = generate_smoke_run_id()
    assert validate_run_id(rid)
    assert rid.startswith("nf_os_smoke_")
