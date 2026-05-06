"""Sprint 7: trust manifest, audit visibility, review summary, org export."""

from __future__ import annotations

import uuid

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


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_trust_manifest_flags(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/trust/manifest",
        headers=_hdr(oid),
    )
    assert r.status_code == 200
    m = r.json()
    assert m["manifest_schema_version"] == "m0_trust_v1"
    assert m["submission_policy"]["automatic_submission_enabled"] is False
    assert m["submission_policy"]["grants_gov_auto_submit"] is False
    assert m["review_gate_policy"]["generated_form_previews_are_non_final"] is True
    assert m["ai_training_policy"]["train_on_customer_data"] is False
    assert m["organization_context"]["request_plane"] == "real"


def test_audit_events_and_export_audit_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    actor = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/tribal-profile",
        json={
            "legal_name": "Trust Test Tribe",
            "entity_type": "tribal_government",
        },
        headers=_hdr(oid),
    )
    spark_id = client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks",
        json={
            "source": GrantSparkSource.manual.value,
            "source_id": "TRUST-SP1",
            "agency": "HUD",
            "opportunity_title": "Capacity grant",
            "award_type": GrantAwardType.grant.value,
            "raw_nofo_text": "Eligibility: tribes.",
            "tribal_eligible": True,
        },
        headers=_hdr(oid),
    ).json()["id"]
    client_nf.post(
        f"/v1/nf/real/orgs/{oid}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )

    aud = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/trust/audit-events",
        params={"limit": 50},
        headers=_hdr(oid),
    )
    assert aud.status_code == 200
    assert len(aud.json()["events"]) >= 1

    rev = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/trust/review-summary",
        headers=_hdr(oid),
    )
    assert rev.status_code == 200
    body = rev.json()
    assert body["review_artifact_count"] >= 1
    assert "draft" in body["by_review_status"]

    exp = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/export/org-data-snapshot",
        headers=_hdr(oid),
        params={
            "audit_sample_limit": 20,
            "actor_id": str(actor),
        },
    )
    assert exp.status_code == 200
    snap = exp.json()
    assert snap["snapshot_schema_version"] == "org_data_snapshot_v1"
    assert snap["tribal_profile"]["legal_name"] == "Trust Test Tribe"
    assert snap["counts"]["grant_sparks"] == 1

    with SessionLocal() as s:
        evs = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.org_data_snapshot_exported.value,
                )
            ).all()
        )
        assert len(evs) >= 1
