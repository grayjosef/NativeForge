"""LA block: scale federal activation + batch hardening tests."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.scaled_federal_corpus_persist_service import (
    build_grant_dedup_key,
    persist_batch_fetch_to_scaled_corpus,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    build_canonical_opportunity_id,
    upsert_tier1_opportunities,
)
from nativeforge.services.tier1_batch_federal_activation_service import (
    Tier1BatchConfirmationBody,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_BATCH_URL = (
    f"/v1/nf/demo/orgs/{_DEMO_ORG}/discovery/source-ingestion/tier1-batch-live-pull"
)
_CONFIRMATION = {
    "operator_handle": "test-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "batch_tier1_public_activation_acknowledged": True,
}


def _hdr() -> dict[str, str]:
    return {"X-NF-Org-Id": str(_DEMO_ORG)}


@pytest.fixture
def la_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_APP_ENV", "staging")
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    monkeypatch.setenv("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED", "true")
    monkeypatch.setenv("NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED", "true")
    get_settings.cache_clear()
    with SessionLocal() as s:
        if s.get(Organization, _DEMO_ORG) is None:
            s.add(Organization(id=_DEMO_ORG, org_type="demo"))
            s.commit()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_ac1_missing_batch_confirmation_returns_422(la_client: TestClient) -> None:
    r = la_client.post(
        _BATCH_URL,
        headers=_hdr(),
        params={
            "nf_live_source_ingestion": "true",
            "nf_real_resolver_validation": "true",
        },
        json={
            "operator_handle": "test-operator",
            "human_activation_acknowledged": True,
            "public_only_acknowledged": True,
        },
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "batch_tier1_public_activation_acknowledged" in str(detail)


def test_ac1_false_acknowledgement_returns_422(la_client: TestClient) -> None:
    r = la_client.post(
        _BATCH_URL,
        headers=_hdr(),
        params={
            "nf_live_source_ingestion": "true",
            "nf_real_resolver_validation": "true",
        },
        json={
            **_CONFIRMATION,
            "batch_tier1_public_activation_acknowledged": False,
        },
    )
    assert r.status_code == 422
    assert "batch_tier1_public_activation_acknowledged" in str(r.json()["detail"])


def test_ac5_kill_switch_halts_batch(la_client: TestClient) -> None:
    la_client.post(
        f"/v1/nf/demo/orgs/{_DEMO_ORG}/operator/activation/governed-action",
        headers={**_hdr(), "X-NF-Actor-Role": "operator"},
        json={
            "governed_action": "activation:toggle",
            "toggle": "kill_switch",
            "value": True,
        },
    )
    r = la_client.post(
        _BATCH_URL,
        headers=_hdr(),
        params={
            "nf_live_source_ingestion": "true",
            "nf_real_resolver_validation": "true",
        },
        json=_CONFIRMATION,
    )
    assert r.status_code == 403
    assert "kill_switch" in r.json()["detail"]


def test_ac3_reingest_dedupes_canonical_opportunity_id() -> None:
    payload = {
        "adapter_key": "grants_gov_federal",
        "opportunity_number": "TEST-001",
        "grants_gov_opportunity_id": 999001,
        "opportunity_title": "Dedup test grant",
        "agency": "TEST",
        "real_fetch": True,
        "fetch_mode": "live",
    }
    first = upsert_tier1_opportunities([payload])
    second = upsert_tier1_opportunities(
        [payload],
        existing_ids=set(first["inserted_ids"]),
    )
    assert first["inserted_count"] == 1
    assert second["inserted_count"] == 0
    assert second["updated_count"] == 1
    assert build_canonical_opportunity_id(payload) == "grants_gov:999001"


def test_ac3_corpus_skip_on_reingest(tmp_path) -> None:
    corpus_path = tmp_path / "grants.json"
    batch_fetch = {
        "per_source": [{"seed_id": "nf-seed-2026-fed-001", "empty_honestly": False}],
        "raw_payloads": [
            {
                "source_seed_id": "nf-seed-2026-fed-001",
                "opportunity_number": "FED-001",
                "grants_gov_opportunity_id": 12345,
                "opportunity_title": "Test Grant",
                "agency": "BIA",
                "eligibility_text": "Tribal governments",
                "real_fetch": True,
                "fetch_mode": "live",
            }
        ],
    }
    first = persist_batch_fetch_to_scaled_corpus(
        batch_fetch,
        corpus_path=corpus_path,
    )
    second = persist_batch_fetch_to_scaled_corpus(
        batch_fetch,
        corpus_path=corpus_path,
    )
    assert first["inserted_count"] >= 1
    assert second["skipped_duplicate_count"] >= 1
    assert second["inserted_count"] == 0


def test_ac4_no_live_nofo_dedup_key_distinct() -> None:
    grant_a = {
        "grant_id": "la-real-025",
        "source_seed_id": "nf-seed-2026-fed-025",
        "opportunity_number": "FED-025",
        "no_live_nofo": True,
        "grants_gov_opportunity_id": None,
    }
    grant_b = {
        "grant_id": "la-real-026",
        "source_seed_id": "nf-seed-2026-fed-026",
        "opportunity_number": "FED-026",
        "no_live_nofo": True,
        "grants_gov_opportunity_id": None,
    }
    assert build_grant_dedup_key(grant_a) != build_grant_dedup_key(grant_b)


@pytest.mark.skipif(
    not __import__("os").environ.get("NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED"),
    reason="staging flags not set — skip live cohort tests",
)
def test_tier1_batch_confirmation_body_validates() -> None:
    body = Tier1BatchConfirmationBody.model_validate(_CONFIRMATION)
    assert body.batch_tier1_public_activation_acknowledged is True
    json.dumps(body.model_dump())
