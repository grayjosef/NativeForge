"""Sprint 163: discovery operator continuity rollup."""

from __future__ import annotations

import ast
import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    FundingDomain,
    OpportunitySourceType,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_operator_continuity_rollup_service import (
    SCHEMA_VERSION,
    build_discovery_operator_continuity_rollup,
    build_discovery_operator_continuity_rollup_from_session,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)
from nativeforge.services.source_candidate_registry_service import (
    SCHEMA_VERSION as REGISTRY_SCHEMA,
)
from nativeforge.services.source_candidate_registry_service import (
    build_source_candidate_registry,
)
from nativeforge.services.source_coverage_plan_service import (
    SCHEMA_VERSION as PLAN_SCHEMA,
)
from nativeforge.services.source_coverage_plan_service import (
    build_source_coverage_plan,
)
from nativeforge.services.source_onboarding_decision_pack_service import (
    SCHEMA_VERSION as PACK_SCHEMA,
)
from nativeforge.services.source_onboarding_decision_pack_service import (
    build_source_onboarding_decision_pack,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _post_source(client: TestClient, oid: uuid.UUID, name: str) -> str:
    payload = {
        "source_name": name,
        "source_type": OpportunitySourceType.federal.value,
        "scope_global": True,
        "priority_level": SourcePriorityLevel.medium.value,
        "funding_domains_json": [FundingDomain.education.value],
    }
    return client.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json=payload,
        headers=_hdr(oid),
    ).json()["id"]


def test_continuity_rollup_schema_version() -> None:
    rollup = build_discovery_operator_continuity_rollup({})
    assert rollup["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION == "nf_discovery_operator_continuity_rollup_v1"


def test_continuity_rollup_stitches_sprint36_38_lineage(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(client_nf, oid, "Continuity Fed Source")

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    rollup = build_discovery_operator_continuity_rollup(sq)
    lineage = rollup["lineage"]
    assert lineage["source_coverage_plan_schema_version"] == PLAN_SCHEMA
    assert lineage["source_candidate_registry_schema_version"] == REGISTRY_SCHEMA
    assert lineage["source_onboarding_decision_pack_schema_version"] == PACK_SCHEMA
    assert rollup["coverage_continuity_summary"]["sequenced_plan_steps"] >= 1
    assert rollup["registry_continuity_summary"]["candidate_count"] >= 1
    assert rollup["onboarding_continuity_summary"]["may_activate_sources"] is False
    assert rollup["onboarding_continuity_summary"]["requires_human_approval"] is True


def test_continuity_rollup_builds_missing_child_artifacts() -> None:
    minimal = {
        "organization_id": "00000000-0000-0000-0000-000000000099",
        "generated_at": "1970-01-01T00:00:00Z",
        "posture": "adequate",
        "data_quality_score": 50,
        "source_counts": {"active": 0},
        "missing_lanes": ["tribal_government"],
        "weak_lanes": [],
    }
    rollup = build_discovery_operator_continuity_rollup(minimal)
    assert rollup["lineage"]["source_coverage_plan_schema_version"] == PLAN_SCHEMA
    assert rollup["registry_continuity_summary"]["candidate_count"] >= 1


def test_continuity_rollup_from_session_matches_direct_build(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    _post_source(client_nf, oid, "Session Rollup Source")

    fixed_now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    with SessionLocal() as s:
        sq = build_discovery_source_quality(
            s, org_id=oid, org_type="demo", now=fixed_now
        )
        direct = build_discovery_operator_continuity_rollup(sq)
        via_session = build_discovery_operator_continuity_rollup_from_session(
            s, org_id=oid, org_type="demo", now=fixed_now
        )
    assert json.dumps(direct, sort_keys=True) == json.dumps(via_session, sort_keys=True)


def test_continuity_rollup_deterministic(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    _post_source(client_nf, oid, "Determinism Source")

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")
    a = build_discovery_operator_continuity_rollup(sq)
    b = build_discovery_operator_continuity_rollup(sq)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_continuity_rollup_blocked_actions_present() -> None:
    rollup = build_discovery_operator_continuity_rollup({})
    joined = " ".join(rollup["blocked_action_summary"]).lower()
    assert "review-only" in joined
    assert "no source activation" in joined


def test_service_has_no_forbidden_imports() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src = (root / "src" / "nativeforge" / "services" / "discovery_operator_continuity_rollup_service.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(src)
    forbidden = {"subprocess", "requests", "httpx", "socket", "urllib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden


def test_regression_sprint36_38_builders_still_valid() -> None:
    minimal = {
        "organization_id": "00000000-0000-0000-0000-000000000088",
        "generated_at": "1970-01-01T00:00:00Z",
        "posture": "adequate",
        "data_quality_score": 45,
        "source_counts": {"active": 1},
        "missing_lanes": [],
        "weak_lanes": [],
    }
    plan = build_source_coverage_plan(minimal)
    reg = build_source_candidate_registry({**minimal, "source_coverage_plan": plan})
    pack = build_source_onboarding_decision_pack(
        {**minimal, "source_coverage_plan": plan, "source_candidate_registry": reg}
    )
    assert plan["schema_version"] == PLAN_SCHEMA
    assert reg["schema_version"] == REGISTRY_SCHEMA
    assert pack["schema_version"] == PACK_SCHEMA
