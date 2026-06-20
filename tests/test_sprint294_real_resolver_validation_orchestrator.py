"""Sprint 294: real-resolver validation orchestrator."""

from __future__ import annotations

import uuid

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.services.real_resolver_validation_orchestrator_service import (
    run_real_resolver_validation_block,
)
from nativeforge.services.real_tier1_live_fetch_service import (
    fixture_tier1_live_fetch,
    reset_real_tier1_fetch_rate_limit,
)
from nativeforge.services.real_url_resolver_service import (
    reset_real_url_resolver_rate_limit,
)
from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_CONFIRM = {
    "operator_handle": "staging-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "single_source_only_acknowledged": True,
}


def _mock_fetch(url: str, method: str) -> dict[str, object]:
    return {"http_status": 200, "body_snippet": "public", "final_url": url}


@pytest.fixture
def staging_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    reset_real_url_resolver_rate_limit()
    reset_real_tier1_fetch_rate_limit()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()


def test_full_validation_block(staging_gates: None) -> None:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        result = run_real_resolver_validation_block(
            s,
            org=org,
            operator_confirmation=_CONFIRM,
            url_fetcher=_mock_fetch,
            tier1_fetcher=fixture_tier1_live_fetch,
        )
        s.commit()
    assert result["fed001_activation"]["seed_id"] == NF9_AUTHORIZED_SEED_ID
    assert result["stop_after_fed001"] is True
