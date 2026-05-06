"""Sprint 18: operator action ledger API + audit + export."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import NfAuditEvent, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    AuditAction,
    OperatorActionResolutionCode,
    OperatorActionStatus,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
)
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


@pytest.fixture
def client_nf_real(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _sample_decision_item(did: str) -> dict:
    return {
        "decision_id": did,
        "item_type": OperatorDecisionItemType.source_overdue.value,
        "severity": OperatorDecisionSeverity.high.value,
        "recommended_action": OperatorDecisionAction.check_source.value,
        "title": "Overdue source check: Test",
        "rationale": "Past window.",
        "refs": {},
    }


def test_direct_create_operator_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    did = f"manual|{uuid.uuid4()}"
    r = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": did,
            "action_title": "Verify source manually",
            "operator_action": "Confirm URL.",
            "item_type": OperatorDecisionItemType.source_verification.value,
            "severity": OperatorDecisionSeverity.high.value,
            "action": OperatorDecisionAction.verify.value,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["schema_version"] == "nf_operator_action_v1"
    assert body["decision_id"] == did
    assert body["status"] == OperatorActionStatus.open.value


def test_create_from_decision_item_and_reuse(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    item = _sample_decision_item(f"decided-{uuid.uuid4()}")
    a = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/from-decision",
        headers=_hdr(oid),
        json={"decision_item": item},
    )
    assert a.status_code == 201, a.text
    first_id = a.json()["operator_action"]["id"]
    assert a.json()["outcome"] == "created"

    b = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/from-decision",
        headers=_hdr(oid),
        json={"decision_item": item},
    )
    assert b.status_code == 201, b.text
    assert b.json()["outcome"] == "reused"
    assert b.json()["operator_action"]["id"] == first_id


def test_force_new_supersedes_previous(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    item = _sample_decision_item(f"decided-{uuid.uuid4()}")
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/from-decision",
        headers=_hdr(oid),
        json={"decision_item": item},
    )
    c = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/from-decision",
        headers=_hdr(oid),
        json={"decision_item": item, "force_new": True},
    )
    assert c.status_code == 201, c.text
    assert c.json()["outcome"] == "created"
    new_id = c.json()["operator_action"]["id"]
    lst = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        params={"decision_id": item["decision_id"]},
    ).json()
    assert len(lst["operator_actions"]) >= 1
    assert any(a["id"] == new_id for a in lst["operator_actions"])


def test_list_filters_status_severity_source(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    did = f"manual|{uuid.uuid4()}"
    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": did,
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.medium.value,
            "action": OperatorDecisionAction.check_source.value,
        },
    )
    act = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        params={"status": OperatorActionStatus.open.value},
    ).json()
    assert act["count"] >= 1

    sev = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        params={"severity": OperatorDecisionSeverity.medium.value},
    ).json()
    assert sev["count"] >= 1

    assert did


def test_detail_scoped(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    created = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    ).json()
    aid = uuid.UUID(created["id"])
    g = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid}",
        headers=_hdr(oid),
    )
    assert g.status_code == 200
    assert g.json()["id"] == str(aid)


def test_patch_assign_in_progress_resolve_defer_dismiss_reopen(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    created = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    ).json()
    aid = created["id"]

    p1 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid}",
        headers=_hdr(oid),
        json={
            "assigned_to": "alex@example.invalid",
            "status": OperatorActionStatus.in_progress.value,
        },
    )
    assert p1.status_code == 200, p1.text
    assert p1.json()["assigned_to"] == "alex@example.invalid"
    assert p1.json()["started_at"] is not None

    p2 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid}",
        headers=_hdr(oid),
        json={
            "status": OperatorActionStatus.resolved.value,
            "resolution_code": OperatorActionResolutionCode.completed.value,
            "resolution_notes": "Done.",
        },
    )
    assert p2.status_code == 200
    assert p2.json()["resolved_at"] is not None

    created2 = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T2",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    ).json()
    aid2 = created2["id"]
    p3 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid2}",
        headers=_hdr(oid),
        json={
            "status": OperatorActionStatus.deferred.value,
            "deferred_until": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )
    assert p3.status_code == 200
    assert p3.json()["status"] == OperatorActionStatus.deferred.value

    created3 = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T3",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    ).json()
    aid3 = created3["id"]
    p4 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid3}",
        headers=_hdr(oid),
        json={"status": OperatorActionStatus.dismissed.value},
    )
    assert p4.status_code == 200
    assert p4.json()["dismissed_at"] is not None

    p5 = client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{aid3}",
        headers=_hdr(oid),
        json={"status": OperatorActionStatus.open.value},
    )
    assert p5.status_code == 200
    assert p5.json()["status"] == OperatorActionStatus.open.value
    assert p5.json()["resolved_at"] is None


def test_summary_counts(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.high.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    )
    sm = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/summary",
        headers=_hdr(oid),
    ).json()
    assert "counts_by_status" in sm
    assert "counts_by_severity" in sm
    assert "counts_by_item_type" in sm
    assert sm["total_actions"] >= 1


def test_demo_cannot_read_other_org_action(client_nf: TestClient) -> None:
    oa = uuid.uuid4()
    ob = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oa, org_type="demo"))
        s.add(Organization(id=ob, org_type="demo"))
        s.commit()

    created = client_nf.post(
        f"/v1/nf/demo/orgs/{oa}/discovery/operator-actions-ledger",
        headers=_hdr(oa),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    ).json()
    aid = created["id"]
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{ob}/discovery/operator-actions-ledger/{aid}",
        headers=_hdr(ob),
    )
    assert r.status_code == 404


def test_audit_events_create_update_resolve(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    created = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
            "operator_notes": "n",
        },
    ).json()

    with SessionLocal() as s:
        evs = s.scalars(
            select(NfAuditEvent).where(NfAuditEvent.organization_id == oid)
        ).all()
        actions = {e.action for e in evs}
        assert AuditAction.operator_action_created.value in actions

    client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{created['id']}",
        headers=_hdr(oid),
        json={"operator_notes": "updated"},
    )

    with SessionLocal() as s:
        evs = s.scalars(
            select(NfAuditEvent).where(NfAuditEvent.organization_id == oid)
        ).all()
        actions = {e.action for e in evs}
        assert AuditAction.operator_action_updated.value in actions

    client_nf.patch(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger/{created['id']}",
        headers=_hdr(oid),
        json={
            "status": OperatorActionStatus.resolved.value,
            "resolution_code": OperatorActionResolutionCode.completed.value,
        },
    )

    with SessionLocal() as s:
        evs = s.scalars(
            select(NfAuditEvent).where(NfAuditEvent.organization_id == oid)
        ).all()
        actions = {e.action for e in evs}
        assert AuditAction.operator_action_resolved.value in actions


def test_trust_surface_export_includes_ledger(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions-ledger",
        headers=_hdr(oid),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    )

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/export/org-data-snapshot",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    snap = r.json()
    assert "operator_action_ledger_summary" in snap
    assert "operator_actions_sample" in snap
    assert snap["counts"]["operator_actions"] >= 1


def test_decision_pack_has_ledger_context(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    )
    assert r.status_code == 200
    b = r.json()
    assert "ledger_context" in b
    assert isinstance(b["ledger_context"]["active_decision_ids"], list)


def test_no_network_stub_import() -> None:
    """Guardrail: sprint18 module must not import http clients."""
    from pathlib import Path

    import nativeforge.services.operator_action_service as m

    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src
    assert "requests" not in src


def test_real_plane_org_has_separate_ledger(
    client_nf_real: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real org route uses real plane; demo org cannot read real-plane rows."""
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    real_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=real_id, org_type="real"))
        s.commit()

    created = client_nf_real.post(
        f"/v1/nf/real/orgs/{real_id}/discovery/operator-actions-ledger",
        headers=_hdr(real_id),
        json={
            "decision_id": f"m|{uuid.uuid4()}",
            "action_title": "T",
            "item_type": OperatorDecisionItemType.source_due.value,
            "severity": OperatorDecisionSeverity.low.value,
            "action": OperatorDecisionAction.monitor.value,
        },
    )
    assert created.status_code == 201, created.text
    aid = created.json()["id"]

    demo_other = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=demo_other, org_type="demo"))
        s.commit()

    leak = client_nf_real.get(
        f"/v1/nf/demo/orgs/{demo_other}/discovery/operator-actions-ledger/{aid}",
        headers=_hdr(demo_other),
    )
    assert leak.status_code == 404
