"""Authenticated Discovery API reads persisted Grants.gov sparks."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.domain.enums import OpportunitySourceType
from nativeforge.main import create_app
from nativeforge.services.grants_gov_corpus_ingest_service import (
    ingest_grants_gov_search2_payload,
)
from nativeforge.services.opportunity_discovery_service import compute_duplicate_key
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-000000000001"
FIXTURE_HIT = {
    "id": "355824",
    "number": "MP-CPI-25-001",
    "title": "Making America Healthy Again by Addressing Dementia Disparities",
    "agency": "Office of the Assistant Secretary for Health",
    "agencyCode": "HHS-OPHS",
    "openDate": "08/01/2024",
    "oppStatus": "forecasted",
    "docType": "synopsis",
}


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    yield soh.session_headers(uuid.UUID(DEMO))


def _seed_one_spark() -> None:
    from nativeforge.db.models import Organization
    from nativeforge.db.session import SessionLocal

    payload = {
        "errorcode": 0,
        "data": {"oppHits": [FIXTURE_HIT]},
    }
    import json

    body = json.dumps(payload).encode()
    sha = "c" * 64
    session = SessionLocal()
    org = session.get(Organization, uuid.UUID(DEMO))
    if org is None:
        org = Organization(id=uuid.UUID(DEMO), org_type="demo")
        session.add(org)
        session.flush()
    ingest_grants_gov_search2_payload(
        session,
        session,
        organization_id=uuid.UUID(DEMO),
        org=org,
        org_type="demo",
        source_id="nf-seed-2026-api-grants-gov-search2",
        body_bytes=body,
        payload_sha256=sha,
        attempt_id="discovery-api-test",
    )
    session.commit()
    session.close()


def test_unauthenticated_grant_sparks_is_not_found(client) -> None:
    path = f"/v1/nf/demo/orgs/{DEMO}/grant-sparks"
    assert client.get(path).status_code in (401, 403, 404)


def test_authenticated_demo_lists_persisted_spark(client, demo_session) -> None:
    _seed_one_spark()
    path = f"/v1/nf/demo/orgs/{DEMO}/grant-sparks"
    response = client.get(path, headers=demo_session)
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    numbers = {str(r.get("opportunity_number") or "") for r in rows}
    assert "MP-CPI-25-001" in numbers
    dup = compute_duplicate_key(
        source_url="https://www.grants.gov/search-results-detail/355824",
        publisher_name=FIXTURE_HIT["agency"],
        opportunity_number="MP-CPI-25-001",
        opportunity_title=FIXTURE_HIT["title"],
        opportunity_source_type=OpportunitySourceType.federal,
    )
    assert any(str(r.get("duplicate_key") or "") == dup for r in rows)


def test_wrong_org_session_cannot_read_demo_sparks(client, demo_session) -> None:
    _seed_one_spark()
    path = f"/v1/nf/demo/orgs/{OTHER}/grant-sparks"
    response = client.get(path, headers=demo_session)
    assert response.status_code in (403, 404)
