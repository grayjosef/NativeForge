"""Sprint 29: connector operator escalation recommendations + source-check wiring."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from nativeforge.db.models import NfOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    GrantAwardType,
    OpportunitySourceType,
    SourceCheckMode,
    SourceCheckRunStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import operator_actions as oa_repo
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import ConnectorSourceConfig
from nativeforge.services.source_connectors.connector_operator_escalation import (
    CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION,
    build_connector_operator_escalation_recommendations,
    escalation_recommendations_json_safe,
)
from nativeforge.services.source_connectors.fixture_corpus import load_category_rows
from nativeforge.services.source_connectors.source_check_bridge import (
    run_source_check_backed_connector_dry_run,
)

CONNECTOR_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "nativeforge"
    / "services"
    / "source_connectors"
)
_FORBIDDEN = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "socket",
    "openai",
    "anthropic",
    "boto3",
    "google.generative",
)


def _seed_org_and_source() -> tuple[uuid.UUID, uuid.UUID]:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        src = create_opportunity_source(
            s,
            org=org,
            body=OpportunitySourcePayload(
                source_name="Sprint 29 connector source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _fixture_row(*, suffix: str = "001") -> dict[str, Any]:
    dl = datetime.now(UTC) + timedelta(days=60)
    return {
        "opportunity_title": f"S29 provenance opportunity {suffix}",
        "agency": "Illustrative Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": f"S29-{suffix}",
        "source_url": f"https://example.test/s29/{suffix}",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


def _cfg(*, cid: str = "s29") -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id=cid,
        source_name="s29",
        publisher_name="Illustrative Agency",
    )


def test_healthy_run_no_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="healthy",
        warning_codes=[],
        normalization_errors=0,
        accepted_count=3,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=0,
        operator_diagnostic_message="ok",
        source_check_run_status=SourceCheckRunStatus.succeeded.value,
        manifest={"connector_run_id": "run-1"},
    )
    assert esc == []
    no_warn = build_connector_operator_escalation_recommendations(
        source_registry_id=None,
        source_check_run_id=None,
        intake_run_id=None,
        connector_id=None,
        health_status="healthy",
        warning_codes=[],
        normalization_errors=0,
        accepted_count=1,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=0,
        manifest=None,
    )
    assert all(not r.get("should_create_action") for r in no_warn)


def test_intake_failure_high_priority() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="failed",
        warning_codes=["intake_candidate_errors"],
        normalization_errors=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0,
        error_count=2,
        review_required_count=0,
        operator_diagnostic_message="Errors during intake",
        source_check_run_status=SourceCheckRunStatus.succeeded_with_warnings.value,
        manifest={},
    )
    assert len(esc) == 1
    r = esc[0]
    assert r["escalation_type"] == "connector_run_failed"
    assert r["priority"] == "high"
    assert r["should_create_action"] is True
    assert r["source_check_run_id"] == "660e8400-e29b-41d4-a716-446655440001"


def test_stale_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="stale",
        warning_codes=["source_check_overdue"],
        normalization_errors=0,
        accepted_count=2,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=0,
        manifest={},
    )
    assert len(esc) == 1
    assert esc[0]["escalation_type"] == "source_freshness_verification"
    assert esc[0]["should_create_action"] is True


def test_empty_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id=None,
        connector_id="c1",
        health_status="empty",
        warning_codes=["connector_run_empty"],
        normalization_errors=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=0,
        manifest={},
    )
    assert esc[0]["escalation_type"] == "source_coverage_verification"


def test_duplicate_degraded_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id=None,
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="degraded",
        warning_codes=["duplicate_only_intake"],
        normalization_errors=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=2,
        error_count=0,
        review_required_count=0,
        manifest={},
    )
    types = {e["escalation_type"] for e in esc}
    assert "dedupe_source_overlap" in types


def test_review_heavy_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="degraded",
        warning_codes=["review_required_heavy"],
        normalization_errors=0,
        accepted_count=2,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=2,
        manifest={},
    )
    assert any(e["escalation_type"] == "native_relevance_rule_precision" for e in esc)


def test_normalization_escalation() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id=None,
        connector_id="c1",
        health_status="failed",
        warning_codes=["fixture_normalization_failed"],
        normalization_errors=2,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0,
        error_count=0,
        review_required_count=0,
        manifest={},
    )
    assert len(esc) == 1
    assert esc[0]["escalation_type"] == "normalization_mapping_failure"
    assert esc[0]["priority"] == "high"


def test_escalation_json_roundtrip() -> None:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id="550e8400-e29b-41d4-a716-446655440000",
        source_check_run_id="660e8400-e29b-41d4-a716-446655440001",
        intake_run_id="770e8400-e29b-41d4-a716-446655440002",
        connector_id="c1",
        health_status="failed",
        warning_codes=[],
        normalization_errors=0,
        accepted_count=0,
        duplicate_count=0,
        rejected_count=0,
        error_count=3,
        review_required_count=0,
        manifest={"connector_run_id": "x"},
    )
    raw = escalation_recommendations_json_safe(esc)
    parsed = json.loads(raw)
    assert isinstance(parsed, list)
    assert parsed[0]["schema_version"] == CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION


def test_source_check_summary_includes_escalations_bridge() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row()],
            connector_config=_cfg(),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert rs.get("operator_escalation_recommendations") == []
    assert rs.get("connector_operator_escalation_schema_version") == (
        CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION
    )
    assert out.get("connector_operator_escalations") == []
    assert rs["source_check_run_id"] == out["source_check_run"]["id"]
    assert rs["intake_run_id"] == out["intake_run"]["id"]
    assert rs["connector_id"] == "s29"


def test_bridge_duplicate_degraded_and_review_fixture() -> None:
    oid, sid = _seed_org_and_source()
    row = _fixture_row(suffix="dup29")
    cfg = _cfg(cid="s29_dup")
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[row],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out2 = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[row],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rs = cast(dict[str, Any], out2["source_check_run"]["result_summary_json"])
    esc = rs["operator_escalation_recommendations"]
    assert any(e["escalation_type"] == "dedupe_source_overlap" for e in esc)

    rows_rr = load_category_rows("keyword_only_false_positive") + load_category_rows(
        "ambiguous_eligibility_case"
    )
    oid2, sid2 = _seed_org_and_source()
    with SessionLocal() as s:
        org = s.get(Organization, oid2)
        assert org is not None
        out_rr = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid2,
            fixture_rows=rows_rr,
            connector_config=_cfg(cid="s29_rr"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()
    rs_rr = cast(dict[str, Any], out_rr["source_check_run"]["result_summary_json"])
    esc_rr = rs_rr["operator_escalation_recommendations"]
    assert any(
        e["escalation_type"] == "native_relevance_rule_precision" for e in esc_rr
    )


def test_bridge_stale_ids_and_normalization() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        reg = s.get(NfOpportunitySource, sid)
        assert reg is not None
        reg.last_checked_at = datetime.now(UTC) - timedelta(days=100)
        reg.check_interval_days = 1
        reg.next_check_due_at = None
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row(suffix="st")],
            connector_config=_cfg(cid="s29_stale"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    esc = rs["operator_escalation_recommendations"]
    assert any(e["escalation_type"] == "source_freshness_verification" for e in esc)
    assert esc[0].get("source_registry_id") == str(sid)

    oid2, sid2 = _seed_org_and_source()
    bad_rows = [
        {
            "opportunity_title": "",
            "agency": "X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        }
    ]
    with SessionLocal() as s:
        org = s.get(Organization, oid2)
        assert org is not None
        out_bad = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid2,
            fixture_rows=bad_rows,
            connector_config=_cfg(cid="s29_bad"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rs_bad = cast(dict[str, Any], out_bad["source_check_run"]["result_summary_json"])
    assert any(
        e["escalation_type"] == "normalization_mapping_failure"
        for e in rs_bad["operator_escalation_recommendations"]
    )
    assert rs_bad.get("intake_run_id") is None
    assert (
        out_bad["connector_operator_escalations"][0]["source_check_run_id"]
        == (out_bad["source_check_run"]["id"])
    )


def test_create_operator_actions_optional_creates_row() -> None:
    oid, sid = _seed_org_and_source()
    bad_rows = [
        {
            "opportunity_title": "",
            "agency": "X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        }
    ]
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=bad_rows,
            connector_config=_cfg(cid="s29_persist"),
            check_mode=SourceCheckMode.manual.value,
            create_operator_actions=True,
        )
        s.commit()

    created = out.get("operator_actions_created") or []
    assert len(created) >= 1
    aid = uuid.UUID(str(created[0]["id"]))
    with SessionLocal() as s:
        row = oa_repo.get_operator_action_scoped(
            s,
            action_id=aid,
            org_id=oid,
            org_type="demo",
        )
        assert row is not None
        assert row.source_check_run_id is not None


@pytest.mark.parametrize(
    "path",
    [
        CONNECTOR_ROOT / "connector_operator_escalation.py",
    ],
)
def test_no_forbidden_network_imports(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for bad in _FORBIDDEN:
        assert f"import {bad}" not in text
        assert f"from {bad}" not in text
