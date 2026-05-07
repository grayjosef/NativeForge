"""Sprint 31: Workbench connector intelligence payload on operator decision pack."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import (
    NfDiscoveryIntakeRun,
    NfOpportunitySource,
    NfSourceCheckRun,
    Organization,
)
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    OpportunitySourceType,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_operator_workbench_service import (
    WORKBENCH_CONNECTOR_INTEL_SCHEMA_VERSION,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_operator_workbench_includes_connector_intelligence_empty_org(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    ci = body["connector_intelligence"]
    assert ci["schema_version"] == WORKBENCH_CONNECTOR_INTEL_SCHEMA_VERSION
    assert ci["rollup"]["sources_with_connector_summaries"] == 0
    assert ci["per_source_latest_connector_run"] == []


def test_connector_intelligence_surfaces_stored_source_check_summary(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Sprint31 Connector Intel",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(src["id"])

    intake_uid = uuid.uuid4()
    rs_blob = {
        "connector_result_summary_schema_version": (
            "nf_connector_source_check_result_summary_v1"
        ),
        "health_status": "degraded",
        "warning_codes": ["connector_run_empty"],
        "counts": {
            "accepted_count": 1,
            "duplicate_count": 5,
            "rejected_count": 0,
            "error_count": 0,
            "review_required_count": 4,
        },
        "manifest": {"counts": {"normalized_candidates": 6}},
        "operator_diagnostic_message": "Fixture diagnostic line.",
        "operator_escalation_recommendations": [
            {
                "operator_title": "Inspect connector batch",
                "operator_message": "Elevated duplicates versus accepts.",
            }
        ],
        "intake_run_id": str(intake_uid),
    }

    with SessionLocal() as s:
        rsrc = s.get(NfOpportunitySource, sid)
        assert rsrc is not None
        rsrc.source_health_status = SourceHealthStatus.degraded.value
        s.add(
            NfDiscoveryIntakeRun(
                id=intake_uid,
                organization_id=oid,
                is_demo=True,
                source_registry_id=sid,
                intake_mode=DiscoveryIntakeMode.structured_batch.value,
            )
        )
        run = NfSourceCheckRun(
            organization_id=oid,
            is_demo=True,
            source_registry_id=sid,
            check_mode=SourceCheckMode.manual.value,
            check_status=SourceCheckRunStatus.succeeded.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            result_summary_json=rs_blob,
        )
        s.add(run)
        s.commit()
        rid = str(run.id)

    body = client_nf.get(
        f"{base}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    ci = body["connector_intelligence"]
    assert ci["rollup"]["sources_with_connector_summaries"] == 1
    assert ci["rollup"]["empty_connector_runs"] >= 1
    assert ci["rollup"]["review_required_heavy_sources"] >= 1
    assert ci["rollup"]["duplicate_heavy_sources"] >= 1
    rows = ci["per_source_latest_connector_run"]
    assert len(rows) == 1
    row0 = rows[0]
    assert row0["source_registry_id"] == str(sid)
    assert row0["connector_health_status"] == "degraded"
    assert row0["source_check_run_id"] == rid
    assert row0["intake_run_id"] == str(intake_uid)
    assert "connector_quality" in row0["pressure_category_tags"]
    flat = ci["operator_escalation_recommendations_flat"]
    assert len(flat) >= 1
    assert flat[0]["operator_title"] == "Inspect connector batch"
    assert flat[0]["source_registry_id"] == str(sid)
