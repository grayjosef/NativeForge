"""Sprint 17: Discovery Operator Workbench / operator decision pack API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import (
    NfDiscoveryIntakeRun,
    NfOpportunitySource,
    Organization,
)
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    DiscoveryIntakeRunStatus,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.services.discovery_operator_workbench_service import (
    DECISION_PACK_SCHEMA_VERSION,
)


def _severity_rank(label: str) -> int:
    return {
        OperatorDecisionSeverity.critical.value: 5,
        OperatorDecisionSeverity.high.value: 4,
        OperatorDecisionSeverity.medium.value: 3,
        OperatorDecisionSeverity.low.value: 2,
        OperatorDecisionSeverity.info.value: 1,
    }[label]


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _assert_decision_pack_shape(body: dict) -> None:
    assert body["schema_version"] == DECISION_PACK_SCHEMA_VERSION
    assert uuid.UUID(body["organization_id"])
    assert isinstance(body["is_demo"], bool)
    assert body["generated_at"]
    assert isinstance(body["decision_score"], int)
    assert isinstance(body["summary"], dict)
    assert isinstance(body["freshness_summary"], dict)
    assert isinstance(body["coverage_gap_summary"], dict)
    assert isinstance(body["open_review_items"], list)
    assert isinstance(body["quality_risk_signals"], dict)
    assert isinstance(body["sources_due"], list)
    assert isinstance(body["sources_overdue"], list)
    assert isinstance(body["sources_failing"], list)
    assert isinstance(body["coverage_gaps"], list)
    assert isinstance(body["source_recommendations"], list)
    assert isinstance(body["operator_next_actions_from_coverage"], list)
    assert isinstance(body["recent_intake_runs"], list)
    assert isinstance(body["intake_runs_flagged"], list)
    assert isinstance(body["decision_items"], list)
    assert isinstance(body["priority_next_actions"], list)
    lc = body["ledger_context"]
    assert isinstance(lc, dict)
    assert isinstance(lc.get("open_operator_actions"), int)
    assert isinstance(lc.get("active_decision_ids"), list)
    assert isinstance(lc.get("resolved_recently_count"), int)
    if body["decision_items"]:
        di0 = body["decision_items"][0]
        assert "has_active_operator_action" in di0
        assert "operator_action_id" in di0
    export = body["decision_summary_export"]
    assert isinstance(export, dict)
    assert export["decision_pack_schema_version"] == DECISION_PACK_SCHEMA_VERSION
    brief = body["operator_brief"]
    assert brief == export


def test_operator_decision_pack_schema_version(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    assert r.json()["schema_version"] == "nf_discovery_operator_decision_pack_v1"
    _assert_decision_pack_shape(r.json())


def test_operator_workbench_alias_matches_decision_pack(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    a = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    ).json()
    b = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    assert a["schema_version"] == b["schema_version"]
    assert a["decision_score"] == b["decision_score"]
    assert [x["decision_id"] for x in a["decision_items"]] == [
        x["decision_id"] for x in b["decision_items"]
    ]


def test_operator_actions_returns_ranked_actions_only(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    slim = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-actions",
        headers=_hdr(oid),
    ).json()
    assert slim.keys() <= {
        "schema_version",
        "organization_id",
        "is_demo",
        "generated_at",
        "decision_score",
        "summary",
        "priority_next_actions",
        "operator_actions",
        "decision_items",
    }
    assert slim["operator_actions"] == slim["priority_next_actions"]
    assert "coverage_gaps" not in slim
    assert "open_review_items" not in slim


def test_open_review_item_emits_review_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        rev_repo.create_review_item(
            s,
            org=org,
            review_item_type=DiscoveryReviewItemType.manual_review.value,
            review_status=DiscoveryReviewQueueStatus.open.value,
            priority=10,
            reason_codes_json=[],
            recommended_action=None,
        )
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 100},
    ).json()
    hits = [
        x
        for x in body["decision_items"]
        if x["item_type"] == OperatorDecisionItemType.review_item.value
        and x["recommended_action"] == OperatorDecisionAction.review.value
    ]
    assert len(hits) >= 1


def test_overdue_source_emits_check_source_action(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Overdue Sprint17",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    past = datetime.now(UTC) - timedelta(days=10)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(sid))
        assert row is not None
        row.next_check_due_at = past
        s.commit()

    body = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    overdue_hits = [
        x
        for x in body["decision_items"]
        if x["item_type"] == OperatorDecisionItemType.source_overdue.value
        and sid in json.dumps(x["refs"])
    ]
    assert len(overdue_hits) >= 1
    assert (
        overdue_hits[0]["recommended_action"]
        == OperatorDecisionAction.check_source.value
    )


def test_failing_severity_above_degraded_above_due(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"

    def _post(name: str, **extra: object) -> str:
        payload = {
            "source_name": name,
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.high.value,
        }
        payload.update(extra)
        return client_nf.post(
            f"{base}/discovery/sources",
            json=payload,
            headers=_hdr(oid),
        ).json()["id"]

    sid_due = _post("Due Only LowPri", priority_level=SourcePriorityLevel.low.value)
    sid_deg = _post("Degraded Probe")
    sid_fail = _post("Failing Probe")

    far_past = datetime.now(UTC) - timedelta(days=30)
    with SessionLocal() as s:
        due_row = s.get(NfOpportunitySource, uuid.UUID(sid_due))
        assert due_row is not None
        due_row.next_check_due_at = far_past
        deg_row = s.get(NfOpportunitySource, uuid.UUID(sid_deg))
        assert deg_row is not None
        deg_row.source_health_status = SourceHealthStatus.degraded.value
        fail_row = s.get(NfOpportunitySource, uuid.UUID(sid_fail))
        assert fail_row is not None
        fail_row.source_health_status = SourceHealthStatus.failing.value
        s.commit()

    body = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()

    def _sev_for(sid: str) -> str:
        for x in body["decision_items"]:
            refs = x.get("refs") or {}
            if refs.get("source_registry_id") == sid:
                return str(x["severity"])
        raise AssertionError(f"no decision row for source {sid}")

    sev_due = _sev_for(sid_due)
    sev_deg = _sev_for(sid_deg)
    sev_fail = _sev_for(sid_fail)
    assert _severity_rank(sev_fail) > _severity_rank(sev_deg)
    assert _severity_rank(sev_deg) > _severity_rank(sev_due)


def test_high_priority_unverified_emits_verification_action(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "HP Unverified Sprint17",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.high.value,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    )

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    hits = [
        x
        for x in body["decision_items"]
        if x["item_type"] == OperatorDecisionItemType.source_verification.value
        and x["recommended_action"] == OperatorDecisionAction.verify.value
    ]
    assert len(hits) >= 1


def test_coverage_gap_emits_expand_coverage_family(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    actions = {
        x["recommended_action"]
        for x in body["decision_items"]
        if x["item_type"]
        in (
            OperatorDecisionItemType.coverage_gap.value,
            OperatorDecisionItemType.source_recommendation.value,
        )
    }
    assert OperatorDecisionAction.expand_coverage.value in actions or (
        OperatorDecisionAction.monitor.value in actions
    )


def test_problematic_intake_run_emits_intake_attention(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Intake Parent",
            "source_type": OpportunitySourceType.state.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(src["id"])

    with SessionLocal() as s:
        run = NfDiscoveryIntakeRun(
            organization_id=oid,
            is_demo=True,
            source_registry_id=sid,
            run_status=DiscoveryIntakeRunStatus.completed.value,
            intake_mode=DiscoveryIntakeMode.manual.value,
            candidate_count=10,
            accepted_count=2,
            duplicate_count=2,
            rejected_count=4,
            error_count=0,
        )
        s.add(run)
        s.commit()
        rid = str(run.id)

    body = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200, "intake_run_limit": 50},
    ).json()
    hits = [
        x
        for x in body["decision_items"]
        if x["item_type"] == OperatorDecisionItemType.intake_run_attention.value
        and rid in json.dumps(x["refs"])
    ]
    assert len(hits) >= 1


def test_severity_filter(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    full = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    assert len(full["decision_items"]) >= 1
    pick = full["decision_items"][0]["severity"]
    filt = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"severity": pick, "limit": 200},
    ).json()
    for x in filt["decision_items"]:
        assert x["severity"] == pick
    for x in filt["priority_next_actions"]:
        assert x["severity"] == pick


def test_item_type_filter(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    full = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    types_present = {x["item_type"] for x in full["decision_items"]}
    pick = next(iter(types_present))
    filt = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"item_type": pick, "limit": 200},
    ).json()
    for x in filt["decision_items"]:
        assert x["item_type"] == pick


def test_action_filter(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    full = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"limit": 200},
    ).json()
    actions_present = {x["recommended_action"] for x in full["decision_items"]}
    pick = next(iter(actions_present))
    filt = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"action": pick, "limit": 200},
    ).json()
    for x in filt["decision_items"]:
        assert x["recommended_action"] == pick


def test_source_registry_filter(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Filter Target",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.high.value,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = src["id"]

    filt = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={"source_registry_id": sid, "limit": 200},
    ).json()
    for x in filt["decision_items"]:
        refs = x.get("refs") or {}
        assert refs.get("source_registry_id") == sid


def test_ranking_is_deterministic(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    params = {"limit": 80}
    a = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params=params,
    ).json()
    b = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params=params,
    ).json()
    assert [x["decision_id"] for x in a["decision_items"]] == [
        x["decision_id"] for x in b["decision_items"]
    ]


def test_demo_plane_rejects_real_org_header_operator_pack(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_real_plane_rejects_demo_org_header_operator_pack(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    )
    assert r.status_code == 403


def test_cross_org_summary_counts_do_not_leak(client_nf: TestClient) -> None:
    oid_a = uuid.uuid4()
    oid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_a, org_type="demo"))
        s.add(Organization(id=oid_b, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid_a}/discovery/sources",
        json={
            "source_name": "ORG_A_SECRET_SOURCE_SPRINT17",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
        },
        headers=_hdr(oid_a),
    )

    body_b = client_nf.get(
        f"/v1/nf/demo/orgs/{oid_b}/discovery/operator-decision-pack",
        headers=_hdr(oid_b),
    ).json()
    assert body_b["summary"]["counts"]["sources_due"] == 0
    blob = json.dumps(body_b)
    assert "ORG_A_SECRET_SOURCE_SPRINT17" not in blob


def test_org_export_includes_operator_decision_fields(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    exp = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/export/org-data-snapshot",
        headers=_hdr(oid),
        params={"audit_sample_limit": 3},
    )
    assert exp.status_code == 200, exp.text
    snap = exp.json()
    assert snap["operator_decision_pack_summary"]["schema_version"] == (
        DECISION_PACK_SCHEMA_VERSION
    )
    assert snap["operator_workbench_summary"] == snap["operator_decision_pack_summary"]
    assert len(snap["operator_priority_actions_sample"]) <= 50
    assert snap["counts"]["operator_priority_actions"] >= 0


def test_include_snapshots_false_strips_source_snapshot(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Snap Strip",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
        },
        headers=_hdr(oid),
    ).json()
    past = datetime.now(UTC) - timedelta(days=5)
    with SessionLocal() as s:
        row = s.get(NfOpportunitySource, uuid.UUID(src["id"]))
        assert row is not None
        row.next_check_due_at = past
        s.commit()

    on = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={
            "limit": 50,
            "include_snapshots": True,
            "item_type": OperatorDecisionItemType.source_overdue.value,
        },
    ).json()
    off = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        headers=_hdr(oid),
        params={
            "limit": 50,
            "include_snapshots": False,
            "item_type": OperatorDecisionItemType.source_overdue.value,
        },
    ).json()
    assert len(on["decision_items"]) >= 1
    assert all("source_snapshot" in x for x in on["decision_items"])
    assert not any("source_snapshot" in x for x in off["decision_items"])


def test_operator_decision_pack_real_schema(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="real"))
        s.commit()

    r = client_nf.get(
        f"/v1/nf/real/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    )
    assert r.status_code == 200, r.text
    _assert_decision_pack_shape(r.json())


def test_decision_items_use_operator_enums(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-decision-pack",
        headers=_hdr(oid),
    ).json()
    types = {OperatorDecisionItemType(x["item_type"]) for x in body["decision_items"]}
    assert types <= set(OperatorDecisionItemType)
    sev = {OperatorDecisionSeverity(x["severity"]) for x in body["decision_items"]}
    assert sev <= set(OperatorDecisionSeverity)
    act = {
        OperatorDecisionAction(x["recommended_action"]) for x in body["decision_items"]
    }
    assert act <= set(OperatorDecisionAction)


def test_operator_workbench_service_has_no_http_clients() -> None:
    import nativeforge.services.discovery_operator_workbench_service as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src and "requests" not in src


def test_trust_surface_export_has_no_external_http_clients() -> None:
    import nativeforge.services.trust_surface_service as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "httpx" not in src and "requests" not in src
