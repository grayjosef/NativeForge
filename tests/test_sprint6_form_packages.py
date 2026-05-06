"""Sprint 6: form packages + SF-424 preview from profile/spark/NOFO/pursuit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _profile() -> dict:
    return {
        "legal_name": "Preview Tribe Nation",
        "entity_type": "tribal_government",
        "uei": "UEI123456789",
        "ein": "12-3456789",
        "physical_address": {
            "line1": "100 Council Rd",
            "city": "Anadarko",
            "state": "OK",
            "zip": "73005",
        },
        "grants_manager": {"name": "Pat Doe", "email": "grants@example.org"},
    }


def _spark(sid: str) -> dict:
    dl = datetime.now(UTC) + timedelta(days=45)
    return {
        "source": GrantSparkSource.manual.value,
        "source_id": sid,
        "agency": "HUD",
        "opportunity_title": "Tribal housing capacity",
        "award_type": GrantAwardType.grant.value,
        "cfda_assistance_listing": "14.134",
        "opportunity_number": "HUD-TEST-001",
        "raw_nofo_text": "Eligibility: tribal governments.",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _open_pursuit(client_nf: TestClient, oid: uuid.UUID) -> tuple[str, str]:
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json=_profile(),
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark("FPKG-1"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    pursuit_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/pursuit",
        headers=_hdr(oid),
    ).json()["id"]
    return spark_id, pursuit_id


def test_form_package_sf424_preview(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    _, pursuit_id = _open_pursuit(client_nf, oid)

    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/form-package",
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["package_engine"] == "sf424_preview_v1"
    assert len(body["input_digest"]) == 64
    prev = body["sf424_preview"]
    assert prev["fields"]["8a_legal_name"]["value"] == "Preview Tribe Nation"
    assert prev["fields"]["10_federal_agency"]["value"] == "HUD"
    assert prev["fields"]["9_type_of_applicant"]["value"]["code"] == "F"

    dup = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/form-package",
        headers=_hdr(oid),
    )
    assert dup.status_code == 409

    g = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/form-package",
        headers=_hdr(oid),
    )
    assert g.status_code == 200
    assert g.json()["input_digest"] == body["input_digest"]

    reg = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/form-package/regenerate",
        headers=_hdr(oid),
    )
    assert reg.status_code == 200
    assert reg.json()["input_digest"] == body["input_digest"]

    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.form_package_created.value,
                )
            ).all()
        )
        assert len(evs) >= 1


def test_get_form_package_missing_returns_404(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    _, pursuit_id = _open_pursuit(client_nf, oid)
    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/pursuits/{pursuit_id}/form-package",
        headers=_hdr(oid),
    )
    assert r.status_code == 404
