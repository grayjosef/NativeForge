"""Sprint 2: nf_grant_sparks list, detail, create, update, seed catalog, scoping."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.services.grant_spark_catalog import DEMO_GRANT_SPARK_CATALOG


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _minimal_spark_body(**overrides: object) -> dict:
    b = {
        "source": GrantSparkSource.manual.value,
        "source_id": "CUSTOM-001",
        "agency": "Demo Agency",
        "opportunity_title": "Custom Opportunity",
        "award_type": GrantAwardType.grant.value,
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "custom"],
        "posted_date": date(2026, 1, 15).isoformat(),
    }
    b.update(overrides)
    return b


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_demo_catalog_has_twelve_seed_definitions() -> None:
    assert len(DEMO_GRANT_SPARK_CATALOG) == 12


def test_demo_seed_idempotent_and_lists_twelve(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r1 = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/seed-demo-catalog",
        headers=_hdr(oid),
    )
    assert r1.status_code == 200
    assert r1.json() == {"inserted": 12, "skipped": 0}

    r2 = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/seed-demo-catalog",
        headers=_hdr(oid),
    )
    assert r2.status_code == 200
    assert r2.json() == {"inserted": 0, "skipped": 12}

    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks",
        headers=_hdr(oid),
    )
    assert lst.status_code == 200
    data = lst.json()
    assert len(data) == 12
    tags = {tuple(x.get("eligibility_tags") or ()) for x in data}
    assert len(tags) >= 3
    assert any("tribal_eligible" in (x.get("eligibility_tags") or []) for x in data)


def test_demo_get_detail_and_tags(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/seed-demo-catalog",
        headers=_hdr(oid),
    )
    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks",
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(lst[0]["id"])
    one = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/{sid}",
        headers=_hdr(oid),
    )
    assert one.status_code == 200
    body = one.json()
    assert body["opportunity_title"]
    assert isinstance(body.get("eligibility_tags"), list)


def test_real_org_create_list_get_put(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_minimal_spark_body(source_id="REAL-001"),
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    spark_id = r.json()["id"]

    lst = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        headers=_hdr(oid),
    ).json()
    assert len(lst) == 1

    upd = client_nf.put(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}",
        json=_minimal_spark_body(
            source_id="REAL-001",
            opportunity_title="Updated Title",
            application_deadline=datetime(2027, 6, 1, 17, 0, tzinfo=UTC).isoformat(),
        ),
        headers=_hdr(oid),
    )
    assert upd.status_code == 200
    assert upd.json()["opportunity_title"] == "Updated Title"


def test_demo_scope_does_not_load_real_spark_row(client_nf: TestClient) -> None:
    real_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=real_id, org_type="real"))
        s.commit()
    client_nf.post(
        f"/v1/nf/real/orgs/{real_id}/grant-sparks",
        json=_minimal_spark_body(source_id="SCOPE-001"),
        headers=_hdr(real_id),
    )
    with SessionLocal() as s:
        row = gs_repo.get_grant_spark_scoped(
            session=s,
            spark_id=uuid.UUID(
                client_nf.get(
                    f"/v1/nf/real/orgs/{real_id}/grant-sparks",
                    headers=_hdr(real_id),
                ).json()[0]["id"]
            ),
            org_id=real_id,
            org_type="demo",
        )
        assert row is None


def test_duplicate_create_returns_409(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    url = f"/v1/nf/real/orgs/{oid}/grant-sparks"
    body = _minimal_spark_body(source_id="DUP-001")
    assert client_nf.post(url, json=body, headers=_hdr(oid)).status_code == 201
    r2 = client_nf.post(url, json=body, headers=_hdr(oid))
    assert r2.status_code == 409


def test_grant_spark_routes_under_v1_nf_paths() -> None:
    from nativeforge.api import grant_spark_routes as m

    assert m.demo_grant_spark_router.prefix == "/v1/nf/demo/orgs"
    assert m.real_grant_spark_router.prefix == "/v1/nf/real/orgs"
