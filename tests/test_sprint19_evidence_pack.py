"""Sprint 19: discovery evidence pack schema, warnings, audit toggle, isolation, export."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryIntakeMode,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    EvidencePackWarningType,
    GrantAwardType,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import discovery_review_items as rev_repo


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


EVIDENCE_SCHEMA = "nf_discovery_evidence_pack_v1"


def _seed_discovery_chain(
    client_nf: TestClient, *, demo: bool
) -> tuple[uuid.UUID, dict]:
    """Returns (org_id, refs dict with sid, run_id, cand_id, spark_id, rev_id, oa_id)."""
    oid = uuid.uuid4()
    plane = "demo" if demo else "real"
    base = f"/v1/nf/{plane}/orgs/{oid}"
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo" if demo else "real"))
        s.commit()

    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Evidence Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(src["id"])

    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    ).json()
    rid = uuid.UUID(run["id"])

    dl = datetime.now(UTC) + timedelta(days=30)
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        json={
            "candidates": [
                {
                    "opportunity_title": "Evidence sprint candidate",
                    "agency": "Agency X",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": f"EV-{uuid.uuid4().hex[:8]}",
                    "source_url": "https://example.gov/evidence",
                    "tribal_eligible": True,
                    "application_deadline": dl.isoformat(),
                },
            ]
        },
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text
    lst = client_nf.get(
        f"{base}/discovery/intake-runs/{rid}/candidates",
        headers=_hdr(oid),
    ).json()
    cand_row = next(c for c in lst if c["candidate_status"] == "accepted")
    cid = uuid.UUID(cand_row["id"])

    sparks = client_nf.get(f"{base}/discovery/sparks", headers=_hdr(oid)).json()
    spark_id = uuid.UUID(sparks[0]["id"])

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        rev = rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.candidate_quality.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=3,
            reason_codes_json=["evidence_pack_test"],
            quality_score=45,
            confidence_score=40,
            duplicate_risk_score=75,
            recommended_action=None,
            review_notes=None,
            assigned_to=None,
            source_registry_id=sid,
            intake_run_id=rid,
            intake_candidate_id=cid,
            grant_spark_id=spark_id,
            resolved_at=None,
        )
        s.commit()
        rev_id = rev.id

    did = f"dp-{uuid.uuid4().hex[:12]}"
    dec_item = {
        "decision_id": did,
        "title": "Evidence follow-up",
        "item_type": OperatorDecisionItemType.review_item.value,
        "severity": OperatorDecisionSeverity.medium.value,
        "operator_action": "Review intake evidence",
        "refs": {
            "source_registry_id": str(sid),
            "review_item_id": str(rev_id),
            "intake_run_id": str(rid),
            "grant_spark_id": str(spark_id),
        },
    }
    oa = client_nf.post(
        f"{base}/discovery/operator-actions-ledger/from-decision",
        json={"decision_item": dec_item},
        headers=_hdr(oid),
    ).json()["operator_action"]
    oa_id = uuid.UUID(oa["id"])

    return oid, {
        "sid": sid,
        "rid": rid,
        "cid": cid,
        "spark_id": spark_id,
        "rev_id": rev_id,
        "oa_id": oa_id,
        "base": base,
    }


def test_evidence_pack_source_schema(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/sources/{refs['sid']}",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == EVIDENCE_SCHEMA
    assert body["subject"]["subject_type"] == "opportunity_source"
    assert body["subject"]["subject_id"] == str(refs["sid"])
    types = {w["warning_type"] for w in body["trust_warnings"]}
    assert EvidencePackWarningType.unverified_source.value in types


def test_evidence_pack_intake_candidate_linked_run_source(
    client_nf: TestClient,
) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/intake-candidates/{refs['cid']}",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == EVIDENCE_SCHEMA
    linked = body["linked_records"]
    assert linked["intake_run"]["id"] == str(refs["rid"])
    assert linked["opportunity_source"]["id"] == str(refs["sid"])
    assert (
        body["quality_summary"].get("quality_schema_version")
        == "nf_discovery_quality_v1"
    )


def test_evidence_pack_grant_spark_provenance(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/grant-sparks/{refs['spark_id']}",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schema_version"] == EVIDENCE_SCHEMA
    assert body["linked_records"]["grant_spark"]["id"] == str(refs["spark_id"])
    assert body["quality_summary"]


def test_evidence_pack_review_item_links(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/review-items/{refs['rev_id']}",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    lr = body["linked_records"]
    assert lr["discovery_review_item"]["id"] == str(refs["rev_id"])
    assert lr["intake_candidate"]["id"] == str(refs["cid"])
    assert lr["grant_spark"]["id"] == str(refs["spark_id"])
    assert lr["opportunity_source"]["id"] == str(refs["sid"])


def test_evidence_pack_operator_action_decision_json(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/operator-actions/{refs['oa_id']}",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    ds = body["decision_summary"]
    assert ds.get("decision_id")
    assert ds.get("source_decision_item_json") is not None
    linked = body["linked_records"]["operator_action"]
    assert linked["refs"]["review_item_id"] == str(refs["rev_id"])
    assert linked["refs"]["source_registry_id"] == str(refs["sid"])


def test_warnings_stale_and_failed_source(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    with SessionLocal() as s:
        from nativeforge.db.models import NfOpportunitySource

        row = s.get(NfOpportunitySource, refs["sid"])
        assert row is not None
        row.source_health_status = SourceHealthStatus.degraded.value
        row.last_check_status = SourceLastCheckStatus.failed.value
        s.commit()

    r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/sources/{refs['sid']}",
        headers=_hdr(oid),
    ).json()
    types = {w["warning_type"] for w in r["trust_warnings"]}
    assert EvidencePackWarningType.stale_source.value in types
    assert EvidencePackWarningType.failed_source_checks.value in types


def test_warnings_unresolved_review_and_operator_action(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    rev_r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/review-items/{refs['rev_id']}",
        headers=_hdr(oid),
    ).json()
    rev_types = {w["warning_type"] for w in rev_r["trust_warnings"]}
    assert EvidencePackWarningType.unresolved_review_item.value in rev_types

    oa_r = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/operator-actions/{refs['oa_id']}",
        headers=_hdr(oid),
    ).json()
    oa_types = {w["warning_type"] for w in oa_r["trust_warnings"]}
    assert EvidencePackWarningType.unresolved_operator_action.value in oa_types


def test_audit_trail_toggle(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    client_nf.get(
        f"{refs['base']}/grant-sparks/{refs['spark_id']}/discovery-quality",
        params={"create_review_item": "false"},
        headers=_hdr(oid),
    )
    on = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/grant-sparks/{refs['spark_id']}",
        params={"include_audit_trail": "true"},
        headers=_hdr(oid),
    ).json()
    off = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/grant-sparks/{refs['spark_id']}",
        params={"include_audit_trail": "false"},
        headers=_hdr(oid),
    ).json()
    assert isinstance(on["audit_trail"], list)
    assert off["audit_trail"] == []


def test_audit_events_include_discovery_actions(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    pack = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/sources/{refs['sid']}",
        params={"audit_limit": "80"},
        headers=_hdr(oid),
    ).json()
    actions = {e["action"] for e in pack["audit_trail"]}
    assert AuditAction.discovery_intake_run_completed.value in actions


def test_demo_vs_real_plane_forbidden(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    bad = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/evidence-pack/sources/{refs['sid']}",
        headers=_hdr(oid),
    )
    assert bad.status_code == 403

    oid2 = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid2, org_type="real"))
        s.commit()
    src = client_nf.post(
        f"/v1/nf/real/orgs/{oid2}/discovery/sources",
        json={
            "source_name": "Real Source",
            "source_type": OpportunitySourceType.state.value,
            "scope_global": True,
        },
        headers=_hdr(oid2),
    ).json()
    sid2 = src["id"]
    bad2 = client_nf.get(
        f"/v1/nf/demo/orgs/{oid2}/discovery/evidence-pack/sources/{sid2}",
        headers=_hdr(oid2),
    )
    assert bad2.status_code == 403


def test_cross_org_isolation_404(client_nf: TestClient) -> None:
    oid_a, refs = _seed_discovery_chain(client_nf, demo=True)
    oid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_b, org_type="demo"))
        s.commit()

    leak = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_b}/discovery/evidence-pack/sources/{refs['sid']}",
        headers=_hdr(oid_b),
    )
    assert leak.status_code == 404


def test_export_includes_evidence_summary(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    exp = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/export/org-data-snapshot",
        headers=_hdr(oid),
    )
    assert exp.status_code == 200, exp.text
    snap = exp.json()
    assert snap["evidence_pack_summary"]["schema_version"] == EVIDENCE_SCHEMA
    assert "evidence_subjects_available" in snap["counts"]
    assert snap["counts"]["evidence_subjects_available"] >= 1


def test_generic_evidence_pack_route(client_nf: TestClient) -> None:
    oid, refs = _seed_discovery_chain(client_nf, demo=True)
    explicit = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/sources/{refs['sid']}",
        headers=_hdr(oid),
    ).json()
    generic = client_nf.get(
        f"{refs['base']}/discovery/evidence-pack/intake-runs/{refs['rid']}",
        headers=_hdr(oid),
    ).json()
    assert explicit["subject"]["subject_type"] == "opportunity_source"
    assert generic["subject"]["subject_type"] == "intake_run"
    assert generic["subject"]["subject_id"] == str(refs["rid"])
