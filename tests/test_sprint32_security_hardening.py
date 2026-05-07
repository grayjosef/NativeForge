"""Sprint 32: security boundary tests.

Covers tenant/org scoping, connector intel, evidence URLs, no-network guardrails.
"""

from __future__ import annotations

import ast
import importlib.util
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from nativeforge.db.models import (
    NfDiscoveryIntakeRun,
    NfOpportunitySource,
    NfSourceCheckRun,
    Organization,
)
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    EvidencePackSubjectType,
    OpportunitySourceType,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services import discovery_evidence_pack_service as ev_pack
from nativeforge.services.discovery_operator_workbench_service import (
    build_workbench_connector_intelligence,
)

FORBIDDEN_NETWORK_TOP_LEVEL = frozenset(
    {
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "http.client",
        "urllib.request",
        "ftplib",
        "smtplib",
        "socket",
        "ssl",
    }
)

ROOT = Path(__file__).resolve().parents[1]
CONNECTOR_PKG = ROOT / "src" / "nativeforge" / "services" / "source_connectors"


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _connector_rs_blob(**overrides: Any) -> dict[str, Any]:
    base = {
        "connector_result_summary_schema_version": (
            "nf_connector_source_check_result_summary_v1"
        ),
        "health_status": "healthy",
        "warning_codes": [],
        "counts": {
            "accepted_count": 0,
            "duplicate_count": 0,
            "rejected_count": 0,
            "error_count": 0,
            "review_required_count": 0,
        },
        "operator_escalation_recommendations": [],
    }
    base.update(overrides)
    return base


def test_workbench_connector_intel_scoped_to_org_sources(
    client_nf: TestClient,
) -> None:
    """Latest connector rollup only includes registry rows for this org."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=org_a, org_type="demo"))
        s.add(Organization(id=org_b, org_type="demo"))
        s.commit()

    def _post_source(oid: uuid.UUID, name: str) -> uuid.UUID:
        r = client_nf.post(
            f"/v1/nf/demo/orgs/{oid}/discovery/sources",
            json={
                "source_name": name,
                "source_type": OpportunitySourceType.federal.value,
                "scope_global": True,
                "priority_level": SourcePriorityLevel.medium.value,
            },
            headers=_hdr(oid),
        )
        assert r.status_code == 201, r.text
        return uuid.UUID(r.json()["id"])

    sid_a = _post_source(org_a, "Org A Source")
    sid_b = _post_source(org_b, "Org B Source")

    rid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(
            NfSourceCheckRun(
                id=rid_b,
                organization_id=org_b,
                is_demo=True,
                source_registry_id=sid_b,
                check_mode=SourceCheckMode.manual.value,
                check_status=SourceCheckRunStatus.succeeded.value,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                result_summary_json=_connector_rs_blob(
                    health_status="failed",
                    operator_escalation_recommendations=[
                        {
                            "operator_title": "B-only",
                            "source_registry_id": str(uuid.uuid4()),
                        }
                    ],
                ),
            )
        )
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{org_a}/discovery/operator-workbench",
        headers=_hdr(org_a),
    ).json()
    ci = body["connector_intelligence"]
    ids_out = {r["source_check_run_id"] for r in ci["per_source_latest_connector_run"]}
    assert str(rid_b) not in ids_out
    flat = ci.get("operator_escalation_recommendations_flat") or []
    assert all("B-only" not in str(x.get("operator_title")) for x in flat)

    body_b = client_nf.get(
        f"/v1/nf/demo/orgs/{org_b}/discovery/operator-workbench",
        headers=_hdr(org_b),
    ).json()
    ci_b = body_b["connector_intelligence"]
    assert ci_b["rollup"]["sources_with_connector_summaries"] >= 1
    ids_b = {r["source_registry_id"] for r in ci_b["per_source_latest_connector_run"]}
    assert str(sid_b) in ids_b
    assert str(sid_a) not in ids_b


def test_connector_intel_strips_unscoped_intake_run_id(client_nf: TestClient) -> None:
    """Forged intake_run_id in result_summary must not surface without DB proof."""
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    src = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "Intake scope",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(src["id"])
    forged_intake = uuid.uuid4()

    with SessionLocal() as s:
        rsrc = s.get(NfOpportunitySource, sid)
        assert rsrc is not None
        rsrc.source_health_status = SourceHealthStatus.healthy.value
        s.add(
            NfSourceCheckRun(
                organization_id=oid,
                is_demo=True,
                source_registry_id=sid,
                check_mode=SourceCheckMode.manual.value,
                check_status=SourceCheckRunStatus.succeeded.value,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                result_summary_json=_connector_rs_blob(
                    intake_run_id=str(forged_intake),
                ),
            )
        )
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    row0 = body["connector_intelligence"]["per_source_latest_connector_run"][0]
    assert row0.get("intake_run_id") is None


def test_escalation_rows_force_registry_and_check_ids(client_nf: TestClient) -> None:
    operator_esc = [
        {
            "operator_title": "Esc",
            "source_registry_id": str(uuid.uuid4()),
            "source_check_run_id": str(uuid.uuid4()),
        }
    ]
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    src = client_nf.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json={
            "source_name": "Esc scope",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid),
    ).json()
    sid = uuid.UUID(src["id"])

    with SessionLocal() as s:
        run = NfSourceCheckRun(
            organization_id=oid,
            is_demo=True,
            source_registry_id=sid,
            check_mode=SourceCheckMode.manual.value,
            check_status=SourceCheckRunStatus.succeeded.value,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            result_summary_json=_connector_rs_blob(
                operator_escalation_recommendations=operator_esc,
            ),
        )
        s.add(run)
        s.commit()
        cr_id = str(run.id)

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/discovery/operator-workbench",
        headers=_hdr(oid),
    ).json()
    flat = body["connector_intelligence"]["operator_escalation_recommendations_flat"]
    assert len(flat) == 1
    assert flat[0]["source_registry_id"] == str(sid)
    assert flat[0]["source_check_run_id"] == cr_id


def test_subject_path_unknown_returns_none() -> None:
    assert ev_pack.subject_path_to_type("unknown-kind") is None
    assert (
        ev_pack.subject_path_to_type("sources")
        == EvidencePackSubjectType.opportunity_source
    )


def test_fixture_connector_not_imported_from_discovery_routes() -> None:
    routes_path = (
        ROOT / "src" / "nativeforge" / "api" / "opportunity_discovery_routes.py"
    )
    text = routes_path.read_text(encoding="utf-8")
    assert "source_check_bridge" not in text
    assert "dry_run_fixture_rows" not in text


def test_source_check_bridge_is_only_service_entrypoint_for_dry_run_chain() -> None:
    """Offline fixture wiring stays behind source_check_bridge (not HTTP routers)."""
    mod = "nativeforge.services.source_connectors.source_check_bridge"
    spec = importlib.util.find_spec(mod)
    assert spec is not None and spec.origin is not None
    assert "run_source_check_backed_connector_dry_run" in Path(spec.origin).read_text(
        encoding="utf-8"
    )


def test_source_connectors_packages_have_no_forbidden_network_imports() -> None:
    violations: list[str] = []
    for path in sorted(CONNECTOR_PKG.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base = alias.name.split(".", 1)[0]
                    if base in FORBIDDEN_NETWORK_TOP_LEVEL:
                        violations.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base = node.module.split(".", 1)[0]
                    if base in FORBIDDEN_NETWORK_TOP_LEVEL:
                        violations.append(f"{path.name}: from {node.module}")
    assert not violations, violations


def test_build_workbench_intel_filters_to_requested_registry_rows() -> None:
    """Rollups only include sources present in the supplied registry list."""
    oid = uuid.uuid4()
    sid_included = uuid.uuid4()
    sid_excluded = uuid.uuid4()
    now = datetime.now(UTC)
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        for sid, name in (
            (sid_included, "Included"),
            (sid_excluded, "ExcludedFromPayload"),
        ):
            s.add(
                NfOpportunitySource(
                    id=sid,
                    organization_id=oid,
                    is_demo=True,
                    source_name=name,
                    source_type=OpportunitySourceType.federal.value,
                    priority_level=SourcePriorityLevel.medium.value,
                )
            )
        s.add(
            NfSourceCheckRun(
                organization_id=oid,
                is_demo=True,
                source_registry_id=sid_included,
                check_mode=SourceCheckMode.manual.value,
                check_status=SourceCheckRunStatus.succeeded.value,
                started_at=now,
                completed_at=now,
                result_summary_json=_connector_rs_blob(health_status="healthy"),
            )
        )
        s.add(
            NfSourceCheckRun(
                organization_id=oid,
                is_demo=True,
                source_registry_id=sid_excluded,
                check_mode=SourceCheckMode.manual.value,
                check_status=SourceCheckRunStatus.succeeded.value,
                started_at=now,
                completed_at=now,
                result_summary_json=_connector_rs_blob(health_status="failed"),
            )
        )
        s.commit()

    with SessionLocal() as session:
        row_one = session.scalar(
            select(NfOpportunitySource).where(NfOpportunitySource.id == sid_included)
        )
        assert row_one is not None
        out = build_workbench_connector_intelligence(
            session,
            org_id=oid,
            org_type="demo",
            source_rows=[row_one],
            now=now,
            check_run_limit=100,
        )
    per = out["per_source_latest_connector_run"]
    assert len(per) == 1
    assert per[0]["source_registry_id"] == str(sid_included)
    assert all(r["source_registry_id"] != str(sid_excluded) for r in per)


def test_intake_other_org_rejected_for_intel_strip(
    client_nf: TestClient,
) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=org_a, org_type="demo"))
        s.add(Organization(id=org_b, org_type="demo"))
        s.commit()

    ra = client_nf.post(
        f"/v1/nf/demo/orgs/{org_a}/discovery/sources",
        json={
            "source_name": "A",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(org_a),
    ).json()
    sid_a = uuid.UUID(ra["id"])

    rb = client_nf.post(
        f"/v1/nf/demo/orgs/{org_b}/discovery/sources",
        json={
            "source_name": "B",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(org_b),
    ).json()
    sid_b = uuid.UUID(rb["id"])

    intake_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(
            NfDiscoveryIntakeRun(
                id=intake_b,
                organization_id=org_b,
                is_demo=True,
                source_registry_id=sid_b,
                intake_mode=DiscoveryIntakeMode.structured_batch.value,
            )
        )
        rsrc = s.get(NfOpportunitySource, sid_a)
        assert rsrc is not None
        s.add(
            NfSourceCheckRun(
                organization_id=org_a,
                is_demo=True,
                source_registry_id=sid_a,
                check_mode=SourceCheckMode.manual.value,
                check_status=SourceCheckRunStatus.succeeded.value,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                result_summary_json=_connector_rs_blob(
                    intake_run_id=str(intake_b),
                ),
            )
        )
        s.commit()

    body = client_nf.get(
        f"/v1/nf/demo/orgs/{org_a}/discovery/operator-workbench",
        headers=_hdr(org_a),
    ).json()
    row0 = body["connector_intelligence"]["per_source_latest_connector_run"][0]
    assert row0.get("intake_run_id") is None
