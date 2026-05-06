"""M0 full-chain proof: tribal profile through trust manifest, audit, export."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import AuditAction, GrantAwardType, GrantSparkSource
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


def _profile() -> dict:
    return {
        "legal_name": "M0 Full-Chain Tribe",
        "entity_type": "tribal_government",
        "uei": "UEIM0FULLCHAIN01",
        "ein": "98-7654321",
        "physical_address": {
            "line1": "1 Sovereignty Rd",
            "city": "Tahlequah",
            "state": "OK",
            "zip": "74464",
        },
        "grants_manager": {"name": "Alex Runner", "email": "grants@m0fc.example"},
    }


def _spark(source_id: str) -> dict:
    dl = datetime.now(UTC) + timedelta(days=50)
    return {
        "source": GrantSparkSource.manual.value,
        "source_id": source_id,
        "agency": "HUD",
        "opportunity_title": "M0 full-chain housing opportunity",
        "award_type": GrantAwardType.grant.value,
        "cfda_assistance_listing": "14.134",
        "opportunity_number": "M0-FC-001",
        "raw_nofo_text": (
            "SECTION I. Eligibility: federally recognized tribes. "
            "SECTION II. Forms: SF-424 required."
        ),
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _run_m0_chain(
    client_nf: TestClient,
    *,
    plane: str,
    org_type: str,
    source_id: str,
) -> None:
    assert plane in ("real", "demo")
    assert org_type in ("real", "demo")

    oid = uuid.uuid4()
    actor = uuid.uuid4()
    base = f"/v1/nf/{plane}/orgs/{oid}"

    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type=org_type))
        s.commit()

    pr = client_nf.post(f"{base}/tribal-profile", json=_profile(), headers=_hdr(oid))
    assert pr.status_code in (200, 201), pr.text

    spark_res = client_nf.post(
        f"{base}/grant-sparks",
        json=_spark(source_id),
        headers=_hdr(oid),
    )
    assert spark_res.status_code == 201, spark_res.text
    spark_id = spark_res.json()["id"]

    ex = client_nf.post(
        f"{base}/grant-sparks/{spark_id}/nofo/extract-stub",
        headers=_hdr(oid),
    )
    assert ex.status_code == 201, ex.text
    body_ex = ex.json()
    assert body_ex["checklist_row_count"] and body_ex["checklist_row_count"] > 0
    assert "_input_digest" in body_ex["structured_requirements"]

    req = client_nf.get(
        f"{base}/grant-sparks/{spark_id}/nofo/requirements",
        headers=_hdr(oid),
    )
    assert req.status_code == 200, req.text
    requirements = req.json()["requirements"]
    assert len(requirements) >= 1

    sc = client_nf.post(
        f"{base}/grant-sparks/{spark_id}/score",
        headers=_hdr(oid),
    )
    assert sc.status_code == 201, sc.text

    pu = client_nf.post(
        f"{base}/grant-sparks/{spark_id}/pursuit",
        json={"notes": "M0 full-chain pursuit."},
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert pu.status_code == 201, pu.text
    pursuit_id = pu.json()["id"]

    detail = client_nf.get(f"{base}/pursuits/{pursuit_id}", headers=_hdr(oid))
    assert detail.status_code == 200, detail.text
    djson = detail.json()
    assert len(djson["tasks"]) >= 1
    kinds = {e["kind"] for e in djson["calendar_events"]}
    assert "application_deadline" in kinds

    fp = client_nf.post(
        f"{base}/pursuits/{pursuit_id}/form-package",
        headers=_hdr(oid),
        params={"actor_id": str(actor)},
    )
    assert fp.status_code == 201, fp.text
    pkg = fp.json()
    assert pkg["package_engine"] == "sf424_preview_v1"
    legal = pkg["sf424_preview"]["fields"]["8a_legal_name"]["value"]
    assert legal == "M0 Full-Chain Tribe"

    mf = client_nf.get(f"{base}/trust/manifest", headers=_hdr(oid))
    assert mf.status_code == 200, mf.text
    manifest = mf.json()
    assert manifest["manifest_schema_version"] == "m0_trust_v1"
    assert manifest["submission_policy"]["automatic_submission_enabled"] is False
    assert (
        manifest["review_gate_policy"]["generated_form_previews_are_non_final"] is True
    )
    plane_label = "real" if plane == "real" else "demo"
    assert manifest["organization_context"]["request_plane"] == plane_label

    aud = client_nf.get(
        f"{base}/trust/audit-events",
        params={"limit": 100},
        headers=_hdr(oid),
    )
    assert aud.status_code == 200, aud.text
    aud_body = aud.json()
    assert len(aud_body["events"]) >= 1

    rev = client_nf.get(f"{base}/trust/review-summary", headers=_hdr(oid))
    assert rev.status_code == 200, rev.text
    rev_body = rev.json()
    assert rev_body["review_artifact_count"] >= 1

    snap_res = client_nf.get(
        f"{base}/export/org-data-snapshot",
        headers=_hdr(oid),
        params={
            "audit_sample_limit": 50,
            "actor_id": str(actor),
            "include_sf424_previews": False,
        },
    )
    assert snap_res.status_code == 200, snap_res.text
    snap = snap_res.json()

    assert snap["snapshot_schema_version"] == "org_data_snapshot_v1"
    assert snap["organization"]["id"] == str(oid)
    assert snap["organization"]["org_type"] == org_type
    assert snap["tribal_profile"]["legal_name"] == "M0 Full-Chain Tribe"
    assert len(snap["grant_sparks"]) == 1
    assert len(snap["pursuits"]) == 1
    assert len(snap["spark_scores"]) == 1
    assert len(snap["nofo_extraction_runs"]) == 1
    assert len(snap["form_packages"]) == 1
    assert snap["counts"]["grant_sparks"] == 1
    assert snap["counts"]["pursuits"] == 1
    assert snap["counts"]["spark_scores"] == 1
    assert snap["counts"]["nofo_extraction_runs"] == 1
    assert snap["counts"]["form_packages"] == 1
    assert snap["counts"]["review_artifacts"] >= 1
    assert "trust_manifest_summary" in snap
    sub_pol = snap["trust_manifest_summary"]["submission_policy"]
    assert sub_pol["automatic_submission_enabled"] is False
    assert len(snap["audit_events_sample"]) >= 1

    # Export writes an audit row for the snapshot (may appear in sample or DB only).
    from sqlalchemy import select

    from nativeforge.db.models import NfAuditEvent

    with SessionLocal() as s:
        exported = list(
            s.scalars(
                select(NfAuditEvent).where(
                    NfAuditEvent.action == AuditAction.org_data_snapshot_exported.value,
                )
            ).all()
        )
        assert len(exported) >= 1


def test_m0_full_chain_real_org(client_nf: TestClient) -> None:
    _run_m0_chain(
        client_nf,
        plane="real",
        org_type="real",
        source_id="M0-FC-REAL-001",
    )


def test_m0_full_chain_demo_org(client_nf: TestClient) -> None:
    _run_m0_chain(
        client_nf,
        plane="demo",
        org_type="demo",
        source_id="M0-FC-DEMO-001",
    )
