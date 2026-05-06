"""Sprint 1: nf_tribal_profiles API, isolation, audits, duplicate guard."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from nativeforge.db.models import NfAuditEvent, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, TribalEntityType
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import tribal_profiles as tp_repo


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _body(**overrides: object) -> dict:
    b = {
        "legal_name": "Example Tribal Government",
        "entity_type": TribalEntityType.tribal_government.value,
        "uei": "ABC123DEF456",
        "service_area_description": "Rural service area",
        "physical_address": {"line1": "1 Main", "city": "Town", "state": "OK"},
    }
    b.update(overrides)
    return b


@pytest.fixture
def client_demo(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_real_org_create_read_update_export_and_audits(
    client_demo: TestClient,
) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_demo.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_body(legal_name="Real Org Profile"),
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["legal_name"] == "Real Org Profile"
    assert data["is_demo"] is False
    assert data["entity_type"] == TribalEntityType.tribal_government.value

    r2 = client_demo.get(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        headers=_hdr(oid),
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == data["id"]

    r3 = client_demo.put(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_body(legal_name="Updated Real", entity_type=TribalEntityType.other.value),
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert r3.status_code == 200
    assert r3.json()["legal_name"] == "Updated Real"
    assert r3.json()["entity_type"] == TribalEntityType.other.value

    r4 = client_demo.get(
        f"/v1/nf/real/orgs/{oid}/tribal-profile/export",
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert r4.status_code == 200
    assert r4.json()["legal_name"] == "Updated Real"

    pid = uuid.UUID(data["id"])
    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent)
                .where(NfAuditEvent.tribal_profile_id == pid)
                .order_by(NfAuditEvent.created_at.asc())
            ).all()
        )
        actions = [e.action for e in evs]
        assert AuditAction.profile_created.value in actions
        assert AuditAction.profile_updated.value in actions
        assert AuditAction.profile_exported.value in actions


def test_demo_org_create_read_update_export(
    client_demo: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_demo.post(
        f"/v1/nf/demo/orgs/{oid}/tribal-profile",
        json=_body(legal_name="Demo Org Profile"),
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    assert r.json()["is_demo"] is True

    assert (
        client_demo.get(
            f"/v1/nf/demo/orgs/{oid}/tribal-profile",
            headers=_hdr(oid),
        ).status_code
        == 200
    )

    assert (
        client_demo.put(
            f"/v1/nf/demo/orgs/{oid}/tribal-profile",
            json=_body(legal_name="Demo Updated"),
            headers=_hdr(oid),
        ).status_code
        == 200
    )

    assert (
        client_demo.get(
            f"/v1/nf/demo/orgs/{oid}/tribal-profile/export",
            headers=_hdr(oid),
        ).status_code
        == 200
    )


def test_real_scope_cannot_see_demo_profile_row(
    client_demo: TestClient,
) -> None:
    demo_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=demo_id, org_type="demo"))
        s.commit()

    client_demo.post(
        f"/v1/nf/demo/orgs/{demo_id}/tribal-profile",
        json=_body(),
        headers=_hdr(demo_id),
    )

    with SessionLocal() as s:
        assert (
            tp_repo.get_tribal_profile_for_org(
                session=s,
                org_id=demo_id,
                org_type="real",
            )
            is None
        )


def test_demo_scope_cannot_see_real_profile_row(
    client_demo: TestClient,
) -> None:
    real_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=real_id, org_type="real"))
        s.commit()

    client_demo.post(
        f"/v1/nf/real/orgs/{real_id}/tribal-profile",
        json=_body(),
        headers=_hdr(real_id),
    )

    with SessionLocal() as s:
        assert (
            tp_repo.get_tribal_profile_for_org(
                session=s,
                org_id=real_id,
                org_type="demo",
            )
            is None
        )


def test_is_demo_mismatch_rejected_by_sqlite_trigger() -> None:
    oid = uuid.uuid4()
    pid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    """
                    INSERT INTO nf_tribal_profiles (
                      id, organization_id, is_demo, legal_name, entity_type,
                      sam_registration_status
                    ) VALUES (
                      :pid, :oid, 0, 'Bad', :etype, 'unknown'
                    )
                    """
                ),
                {
                    "pid": str(pid),
                    "oid": str(oid),
                    "etype": TribalEntityType.other.value,
                },
            )
            s.commit()


def test_duplicate_post_returns_409(client_demo: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    url = f"/v1/nf/real/orgs/{oid}/tribal-profile"
    assert client_demo.post(url, json=_body(), headers=_hdr(oid)).status_code == 201
    r2 = client_demo.post(url, json=_body(legal_name="Dup"), headers=_hdr(oid))
    assert r2.status_code == 409


def test_tribal_profile_routes_use_nf_product_paths() -> None:
    from nativeforge.api import tribal_profile_routes as m

    assert m.demo_profile_router.prefix == "/v1/nf/demo/orgs"
    assert m.real_profile_router.prefix == "/v1/nf/real/orgs"
