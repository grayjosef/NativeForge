"""Sprint 3: NOFO stub extraction, checklist rows, review artifact linkage."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _spark_body(**kw: object) -> dict:
    b = {
        "source": GrantSparkSource.manual.value,
        "source_id": "NOFO-TEST-001",
        "agency": "Test Agency",
        "opportunity_title": "Test NOFO Opportunity",
        "award_type": GrantAwardType.grant.value,
        "raw_nofo_text": (
            "SECTION I. Eligibility. Federally recognized tribes may apply. "
            "SECTION II. Forms. SF-424 required."
        ),
        "tribal_eligible": True,
    }
    b.update(kw)
    return b


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_extract_stub_creates_run_artifact_and_checklist(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    r = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(),
        headers=_hdr(oid),
    )
    assert r.status_code == 201
    spark_id = r.json()["id"]

    x = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    assert x.status_code == 201
    body = x.json()
    assert body["review_artifact"]["review_status"] == "draft"
    assert len(body["structured_requirements"]["_input_digest"]) == 64
    assert body["checklist_row_count"] and body["checklist_row_count"] > 0

    latest = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/latest",
        headers=_hdr(oid),
    )
    assert latest.status_code == 200
    lp = latest.json()
    assert lp["review_gate"]["is_final"] is False
    assert "plain_language_summary" in lp["structured_requirements"]["ai_summary"]

    req = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/requirements",
        headers=_hdr(oid),
    )
    assert req.status_code == 200
    assert len(req.json()["requirements"]) >= 5


def test_extraction_audit_event_has_extraction_run_id(client_nf: TestClient) -> None:
    from sqlalchemy import select

    from nativeforge.db.models import NfAuditEvent

    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    spark_id = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="AUD-001"),
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.nofo_extraction_completed.value
                )
            ).all()
        )
        assert len(evs) >= 1
        assert evs[-1].extraction_run_id is not None
        assert evs[-1].review_artifact_id is not None


def test_second_extract_adds_history_latest_is_newest(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json=_spark_body(source_id="HIST-001"),
        headers=_hdr(oid),
    ).json()["id"]
    r1 = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    ).json()
    r2 = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    ).json()
    assert r1["extraction_run"]["id"] != r2["extraction_run"]["id"]
    latest = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/latest",
        headers=_hdr(oid),
    ).json()
    assert latest["extraction_run"]["id"] == r2["extraction_run"]["id"]
